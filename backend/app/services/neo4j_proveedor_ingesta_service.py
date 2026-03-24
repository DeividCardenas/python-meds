"""
Servicio esqueleto para cruce de archivos de proveedor contra Golden Record Neo4j.

Arquitectura operativa
1) Leer archivo de proveedor con Polars.
2) Estandarizar campos (cum, precio, porcentaje, descripcion).
3) Resolver CUMs existentes en Neo4j por lotes.
4) Particionar registros en:
   - match exitoso contra (:Medicamento_Oficial)
   - cuarentena en (:Medicamento_Huerfano)
5) Persistir masivamente con Cypher UNWIND + MERGE.
"""

from __future__ import annotations

import hashlib
import re
import logging
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable

import polars as pl
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

PROVEEDOR_INGESTA_CHUNK_SIZE = int(os.getenv("PROVEEDOR_INGESTA_CHUNK_SIZE", "5000"))
ORPHAN_AUTO_HOMOLOGATE_THRESHOLD = float(os.getenv("ORPHAN_AUTO_HOMOLOGATE_THRESHOLD", "0.93"))
ORPHAN_AUTO_HOMOLOGATE_MARGIN = float(os.getenv("ORPHAN_AUTO_HOMOLOGATE_MARGIN", "0.10"))


MATCHED_COTIZACIONES_CYPHER = """
UNWIND $rows AS row
MERGE (c:Cotizacion_Proveedor {
  id_documento: row.id_documento,
  proveedor: row.proveedor,
  fecha: date(row.fecha)
})
ON CREATE SET c.created_at = datetime()
SET c.updated_at = datetime(),
    c.estado_documento = 'PROCESADO'

WITH c, row
MATCH (m:Medicamento_Oficial {cum: row.cum})
MERGE (d:Detalle_Cotizacion_Proveedor {row_key: row.row_key})
ON CREATE SET d.created_at = datetime()
SET d.updated_at = datetime(),
    d.id_documento = row.id_documento,
    d.proveedor = row.proveedor,
    d.fecha = date(row.fecha),
    d.cum_recibido = row.cum,
    d.centro_distribucion = coalesce(row.centro_distribucion, ''),
    d.texto_original = coalesce(row.texto_original, ''),
    d.laboratorio_raw = coalesce(row.laboratorio_raw, ''),
    d.principio_activo_raw = coalesce(row.principio_activo_raw, ''),
    d.precio_proveedor = row.precio_proveedor,
    d.porcentaje_aumento = row.porcentaje_aumento,
    d.moneda = coalesce(row.moneda, 'COP'),
    d.fuente_archivo = row.fuente_archivo

MERGE (c)-[:TIENE_DETALLE]->(d)
MERGE (d)-[dr:COTIZADO_A]->(m)
SET dr.precio_proveedor = row.precio_proveedor,
    dr.porcentaje_aumento = row.porcentaje_aumento,
    dr.moneda = coalesce(row.moneda, 'COP'),
    dr.fuente_archivo = row.fuente_archivo,
    dr.updated_at = datetime(),
    dr.centro_distribucion = coalesce(row.centro_distribucion, '')

MERGE (c)-[r:COTIZADO_A]->(m)
SET r.updated_at = datetime()
"""


ORPHAN_CUARENTENA_CYPHER = """
UNWIND $rows AS row
MERGE (c:Cotizacion_Proveedor {
  id_documento: row.id_documento,
  proveedor: row.proveedor,
  fecha: date(row.fecha)
})
ON CREATE SET c.created_at = datetime()
SET c.updated_at = datetime(),
    c.estado_documento = 'PROCESADO_CON_HUERFANOS'

MERGE (h:Medicamento_Huerfano {
    orphan_key: row.orphan_key
})
ON CREATE SET h.created_at = datetime(),
              h.estado_revision = 'Pendiente'
SET h.updated_at = datetime(),
        h.id_documento = row.id_documento,
        h.proveedor = row.proveedor,
        h.cum_recibido = row.cum_recibido,
    h.texto_original = row.texto_original,
    h.laboratorio_raw = coalesce(row.laboratorio_raw, ''),
    h.principio_activo_raw = coalesce(row.principio_activo_raw, ''),
    h.ultima_fecha = date(row.fecha)

MERGE (d:Detalle_Cotizacion_Proveedor {row_key: row.row_key})
ON CREATE SET d.created_at = datetime()
SET d.updated_at = datetime(),
    d.id_documento = row.id_documento,
    d.proveedor = row.proveedor,
    d.fecha = date(row.fecha),
    d.cum_recibido = row.cum_recibido,
    d.centro_distribucion = coalesce(row.centro_distribucion, ''),
    d.texto_original = coalesce(row.texto_original, ''),
    d.laboratorio_raw = coalesce(row.laboratorio_raw, ''),
    d.principio_activo_raw = coalesce(row.principio_activo_raw, ''),
    d.precio_proveedor = row.precio_proveedor,
    d.porcentaje_aumento = row.porcentaje_aumento,
    d.moneda = coalesce(row.moneda, 'COP')

MERGE (c)-[:TIENE_DETALLE]->(d)
MERGE (d)-[dr:COTIZA_HUERFANO]->(h)
SET dr.precio_proveedor = row.precio_proveedor,
    dr.porcentaje_aumento = row.porcentaje_aumento,
    dr.moneda = coalesce(row.moneda, 'COP'),
    dr.updated_at = datetime(),
    dr.centro_distribucion = coalesce(row.centro_distribucion, '')

MERGE (c)-[r:COTIZA_HUERFANO]->(h)
SET r.updated_at = datetime()
"""


CREATE_FT_MEDICAMENTO_PRODUCTO_INDEX = """
CREATE FULLTEXT INDEX medicamento_oficial_producto_ft IF NOT EXISTS
FOR (m:Medicamento_Oficial)
ON EACH [m.producto]
"""


FIND_ORPHANS_FOR_DOCUMENT_CYPHER = """
MATCH (h:Medicamento_Huerfano {id_documento: $id_documento, proveedor: $proveedor})
WHERE coalesce(h.estado_revision, 'Pendiente') = 'Pendiente'
RETURN
    h.orphan_key AS orphan_key,
    h.cum_recibido AS cum_recibido,
    h.id_documento AS id_documento,
    h.proveedor AS proveedor,
    coalesce(h.texto_original, '') AS texto_original,
    coalesce(h.laboratorio_raw, '') AS laboratorio_raw,
    coalesce(h.principio_activo_raw, '') AS principio_activo_raw
"""


QUERY_MEDICAMENTO_CANDIDATES_CYPHER = """
CALL db.index.fulltext.queryNodes('medicamento_oficial_producto_ft', $query_text, {limit: $limit})
YIELD node, score
OPTIONAL MATCH (l:Laboratorio)-[:FABRICADO_POR]->(node)
OPTIONAL MATCH (p:Principio_Activo)-[:CONTIENE_PRINCIPIO]->(node)
RETURN
    node.cum AS cum,
    coalesce(node.producto, '') AS producto,
    score AS score_ft,
    coalesce(l.nombre, '') AS laboratorio,
    collect(DISTINCT coalesce(p.nombre, '')) AS principios
ORDER BY score_ft DESC
"""


APPLY_HOMOLOGACION_CYPHER = """
MATCH (h:Medicamento_Huerfano {
    orphan_key: $orphan_key
})
MATCH (m:Medicamento_Oficial {cum: $cum_sugerido})
MERGE (h)-[r:HOMOLOGADO_A]->(m)
SET r.score = $score,
        r.margen = $margen,
        r.metodo = 'auto_homologacion_v1',
        r.updated_at = datetime(),
        h.estado_revision = 'AutoAprobado',
        h.cum_sugerido = $cum_sugerido,
        h.score_homologacion = $score,
        h.margen_homologacion = $margen,
        h.metodo_homologacion = 'auto_homologacion_v1',
        h.updated_at = datetime(),
        h.homologado_en = datetime()
"""


FIND_EXISTING_CUMS_CYPHER = """
UNWIND $cums AS cum
MATCH (m:Medicamento_Oficial {cum: cum})
RETURN collect(m.cum) AS encontrados
"""


@dataclass(slots=True)
class ProveedorIngestaStats:
    total_rows: int = 0
    matched_rows: int = 0
    orphan_rows: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "matched_rows": self.matched_rows,
            "orphan_rows": self.orphan_rows,
        }


class Neo4jProveedorIngestaService:
    def __init__(
        self,
        *,
        neo4j_uri: str = NEO4J_URI,
        neo4j_user: str = NEO4J_USER,
        neo4j_password: str = NEO4J_PASSWORD,
        neo4j_database: str = NEO4J_DATABASE,
        chunk_size: int = PROVEEDOR_INGESTA_CHUNK_SIZE,
    ) -> None:
        self._driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self._database = neo4j_database
        self._chunk_size = max(500, chunk_size)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jProveedorIngestaService":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _read_dataframe(file_path: str | Path) -> pl.DataFrame:
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext in {".xlsx", ".xls"}:
            return pl.read_excel(path)
        if ext in {".tsv", ".txt"}:
            return pl.read_csv(path, separator="\t", infer_schema_length=0)
        return pl.read_csv(path, infer_schema_length=0)

    @staticmethod
    def _parse_decimal(value: Any) -> float | None:
        if value is None:
            return None
        raw = str(value).strip().replace(" ", "")
        if not raw:
            return None
        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                raw = raw.replace(".", "").replace(",", ".")
            else:
                raw = raw.replace(",", "")
        elif "," in raw:
            raw = raw.replace(",", ".")
        try:
            return float(Decimal(raw))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def transform_proveedor_dataframe(
        df: pl.DataFrame,
        *,
        id_documento: str,
        proveedor: str,
        fecha_documento: date,
        column_map: dict[str, str],
    ) -> pl.DataFrame:
        """Normaliza el archivo del proveedor a un esquema único para UNWIND."""
        cum_col = column_map.get("cum", "cum")
        precio_col = column_map.get("precio_proveedor", "precio")
        aumento_col = column_map.get("porcentaje_aumento", "porcentaje_aumento")
        texto_col = column_map.get("texto_original", "descripcion")
        moneda_col = column_map.get("moneda", "moneda")
        laboratorio_col = column_map.get("laboratorio", "laboratorio")
        principio_col = column_map.get("principio_activo", "principio_activo")
        centro_col = column_map.get("centro_distribucion", "centro_distribucion")

        required = [cum_col, precio_col]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Columnas requeridas no encontradas en archivo proveedor: {missing}")

        transformed = (
            df.with_columns(
                [
                    pl.col(cum_col).cast(pl.Utf8).fill_null("").str.strip_chars().alias("cum"),
                    pl.col(precio_col)
                    .map_elements(Neo4jProveedorIngestaService._parse_decimal, return_dtype=pl.Float64)
                    .alias("precio_proveedor"),
                    pl.col(aumento_col)
                    .map_elements(Neo4jProveedorIngestaService._parse_decimal, return_dtype=pl.Float64)
                    .alias("porcentaje_aumento")
                    if aumento_col in df.columns
                    else pl.lit(None, dtype=pl.Float64).alias("porcentaje_aumento"),
                    pl.col(texto_col).cast(pl.Utf8).fill_null("").str.strip_chars().alias("texto_original")
                    if texto_col in df.columns
                    else pl.lit("", dtype=pl.Utf8).alias("texto_original"),
                    pl.col(moneda_col).cast(pl.Utf8).fill_null("COP").str.strip_chars().alias("moneda")
                    if moneda_col in df.columns
                    else pl.lit("COP", dtype=pl.Utf8).alias("moneda"),
                    pl.col(laboratorio_col).cast(pl.Utf8).fill_null("").str.strip_chars().alias("laboratorio_raw")
                    if laboratorio_col in df.columns
                    else pl.lit("", dtype=pl.Utf8).alias("laboratorio_raw"),
                    pl.col(principio_col).cast(pl.Utf8).fill_null("").str.strip_chars().alias("principio_activo_raw")
                    if principio_col in df.columns
                    else pl.lit("", dtype=pl.Utf8).alias("principio_activo_raw"),
                    pl.col(centro_col).cast(pl.Utf8).fill_null("").str.strip_chars().alias("centro_distribucion")
                    if centro_col in df.columns
                    else pl.lit("", dtype=pl.Utf8).alias("centro_distribucion"),
                ]
            )
            .with_columns(
                [
                    pl.lit(id_documento).alias("id_documento"),
                    pl.lit(proveedor).alias("proveedor"),
                    pl.lit(fecha_documento.isoformat()).alias("fecha"),
                    pl.lit("archivo_proveedor").alias("fuente_archivo"),
                ]
            )
            .filter(pl.col("precio_proveedor").is_not_null())
        )

        return transformed.select(
            [
                "id_documento",
                "proveedor",
                "fecha",
                "cum",
                "precio_proveedor",
                "porcentaje_aumento",
                "texto_original",
                "laboratorio_raw",
                "principio_activo_raw",
                "centro_distribucion",
                "moneda",
                "fuente_archivo",
            ]
        )

    def _fetch_existing_cums(self, cums: list[str]) -> set[str]:
        if not cums:
            return set()
        with self._driver.session(database=self._database) as session:
            result = session.run(FIND_EXISTING_CUMS_CYPHER, cums=cums)
            row = result.single()
            if not row:
                return set()
            encontrados = row.get("encontrados") or []
            return {str(x) for x in encontrados}

    @staticmethod
    def _normalize_text(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower())
        return re.sub(r"[^a-z0-9%./+\- ]+", " ", cleaned).strip()

    @staticmethod
    def _extract_dose_tokens(text: str) -> set[str]:
        normalized = Neo4jProveedorIngestaService._normalize_text(text)
        tokens = re.findall(r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|ug|g|ml|ui|iu|%)\b", normalized)
        return {t.replace(" ", "") for t in tokens}

    @staticmethod
    def _extract_principio_tokens(text: str) -> set[str]:
        normalized = Neo4jProveedorIngestaService._normalize_text(text).upper()
        parts = re.split(r"\s*(?:\+|/|\bY\b|\bCON\b|;)\s*", normalized)
        compact = {re.sub(r"\s+", " ", p).strip() for p in parts}
        return {p for p in compact if len(p) >= 4}

    @staticmethod
    def _build_orphan_key(row: dict[str, Any]) -> str:
        # Aporta identidad estable para evitar colisiones cuando el CUM viene vacio o repetido.
        payload = "|".join(
            [
                str(row.get("id_documento") or "").strip().lower(),
                str(row.get("proveedor") or "").strip().lower(),
                str(row.get("fecha") or "").strip(),
                str(row.get("cum") or row.get("cum_recibido") or "").strip().lower(),
                Neo4jProveedorIngestaService._normalize_text(str(row.get("texto_original") or "")),
                Neo4jProveedorIngestaService._normalize_text(str(row.get("laboratorio_raw") or "")),
                Neo4jProveedorIngestaService._normalize_text(str(row.get("principio_activo_raw") or "")),
                str(row.get("precio_proveedor") if row.get("precio_proveedor") is not None else ""),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _ensure_reconciliation_indexes(self) -> None:
        with self._driver.session(database=self._database) as session:
            session.run(CREATE_FT_MEDICAMENTO_PRODUCTO_INDEX)

    def _fetch_orphans_for_document(self, id_documento: str, proveedor: str) -> list[dict[str, Any]]:
        with self._driver.session(database=self._database) as session:
            rows = session.run(
                FIND_ORPHANS_FOR_DOCUMENT_CYPHER,
                id_documento=id_documento,
                proveedor=proveedor,
            )
            return [dict(r) for r in rows]

    def _query_candidate_medicamentos(self, query_text: str, limit: int = 8) -> list[dict[str, Any]]:
        if not query_text.strip():
            return []

        # Lucene query parser (db.index.fulltext.queryNodes) falla con
        # caracteres especiales sin escapar. Usamos una query segura por tokens.
        safe = re.sub(r"[^a-zA-Z0-9 ]+", " ", query_text)
        safe = re.sub(r"\s+", " ", safe).strip()
        if not safe:
            return []

        # Limitar longitud evita consultas costosas o ambiguas en textos largos.
        safe = " ".join(safe.split(" ")[:18])

        with self._driver.session(database=self._database) as session:
            rows = session.run(
                QUERY_MEDICAMENTO_CANDIDATES_CYPHER,
                query_text=safe,
                limit=limit,
            )
            return [dict(r) for r in rows]

    def _score_candidate(self, orphan: dict[str, Any], candidate: dict[str, Any]) -> float:
        orphan_text = self._normalize_text(str(orphan.get("texto_original") or ""))
        cand_product = self._normalize_text(str(candidate.get("producto") or ""))
        base_similarity = SequenceMatcher(None, orphan_text, cand_product).ratio()

        orphan_dose = self._extract_dose_tokens(orphan_text)
        cand_dose = self._extract_dose_tokens(cand_product)
        if orphan_dose and cand_dose:
            dose_score = len(orphan_dose.intersection(cand_dose)) / max(len(orphan_dose), len(cand_dose))
        elif orphan_dose:
            dose_score = 0.0
        else:
            dose_score = 0.5

        orphan_lab = self._normalize_text(str(orphan.get("laboratorio_raw") or ""))
        cand_lab = self._normalize_text(str(candidate.get("laboratorio") or ""))
        lab_score = 1.0 if orphan_lab and cand_lab and orphan_lab in cand_lab else (0.0 if orphan_lab else 0.5)

        orphan_principios = self._extract_principio_tokens(str(orphan.get("principio_activo_raw") or ""))
        cand_principios_raw = candidate.get("principios") or []
        cand_principios = self._extract_principio_tokens("; ".join(str(x) for x in cand_principios_raw))
        if orphan_principios and cand_principios:
            principio_score = len(orphan_principios.intersection(cand_principios)) / max(len(orphan_principios), len(cand_principios))
        elif orphan_principios:
            principio_score = 0.0
        else:
            principio_score = 0.5

        ft_score = float(candidate.get("score_ft") or 0.0)
        ft_score = min(max(ft_score / 5.0, 0.0), 1.0)

        return (
            (base_similarity * 0.45)
            + (dose_score * 0.25)
            + (lab_score * 0.15)
            + (principio_score * 0.10)
            + (ft_score * 0.05)
        )

    def _apply_homologacion(
        self,
        *,
        orphan_key: str,
        cum_sugerido: str,
        score: float,
        margen: float,
    ) -> None:
        with self._driver.session(database=self._database) as session:
            session.run(
                APPLY_HOMOLOGACION_CYPHER,
                orphan_key=orphan_key,
                cum_sugerido=cum_sugerido,
                score=round(score, 6),
                margen=round(margen, 6),
            )

    def homologar_huerfanos_documento(self, *, id_documento: str, proveedor: str) -> dict[str, int]:
        """Auto-homologa huerfanos de un documento solo con confianza alta y margen claro."""
        self._ensure_reconciliation_indexes()
        orphans = self._fetch_orphans_for_document(id_documento=id_documento, proveedor=proveedor)

        reviewed = 0
        auto_assigned = 0
        skipped_low_confidence = 0

        for orphan in orphans:
            reviewed += 1
            query_text = str(orphan.get("texto_original") or "").strip()
            candidates = self._query_candidate_medicamentos(query_text=query_text, limit=8)
            if not candidates:
                skipped_low_confidence += 1
                continue

            scored: list[tuple[float, dict[str, Any]]] = []
            for candidate in candidates:
                cand_cum = str(candidate.get("cum") or "").strip()
                if not cand_cum:
                    continue
                score = self._score_candidate(orphan, candidate)
                scored.append((score, candidate))

            if not scored:
                skipped_low_confidence += 1
                continue

            scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best_candidate = scored[0]
            second_score = scored[1][0] if len(scored) > 1 else 0.0
            margin = best_score - second_score

            if best_score < ORPHAN_AUTO_HOMOLOGATE_THRESHOLD or margin < ORPHAN_AUTO_HOMOLOGATE_MARGIN:
                skipped_low_confidence += 1
                continue

            orphan_key = str(orphan.get("orphan_key") or "").strip()
            if not orphan_key:
                skipped_low_confidence += 1
                continue

            self._apply_homologacion(
                orphan_key=orphan_key,
                cum_sugerido=str(best_candidate.get("cum") or ""),
                score=best_score,
                margen=margin,
            )
            auto_assigned += 1

        return {
            "orphans_reviewed": reviewed,
            "auto_assigned": auto_assigned,
            "kept_pending": skipped_low_confidence,
        }

    @staticmethod
    def _split_matched_vs_orphan(
        rows: list[dict[str, Any]],
        existing_cums: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        matched: list[dict[str, Any]] = []
        orphan: list[dict[str, Any]] = []

        for row in rows:
            cum = str(row.get("cum") or "").strip()
            if cum and cum in existing_cums:
                row_copy = dict(row)
                row_copy["row_key"] = Neo4jProveedorIngestaService._build_row_key(row_copy)
                matched.append(row_copy)
                continue

            orphan.append(
                {
                    "id_documento": row.get("id_documento"),
                    "proveedor": row.get("proveedor"),
                    "fecha": row.get("fecha"),
                    "cum_recibido": cum,
                    "orphan_key": Neo4jProveedorIngestaService._build_orphan_key(row),
                    "row_key": Neo4jProveedorIngestaService._build_row_key(row),
                    "texto_original": row.get("texto_original"),
                    "laboratorio_raw": row.get("laboratorio_raw"),
                    "principio_activo_raw": row.get("principio_activo_raw"),
                    "centro_distribucion": row.get("centro_distribucion"),
                    "precio_proveedor": row.get("precio_proveedor"),
                    "porcentaje_aumento": row.get("porcentaje_aumento"),
                    "moneda": row.get("moneda"),
                }
            )

        return matched, orphan

    @staticmethod
    def _build_row_key(row: dict[str, Any]) -> str:
        # Identidad por fila para preservar granularidad (por ejemplo, por centro).
        payload = "|".join(
            [
                str(row.get("id_documento") or "").strip().lower(),
                str(row.get("proveedor") or "").strip().lower(),
                str(row.get("fecha") or "").strip(),
                str(row.get("cum") or row.get("cum_recibido") or "").strip().lower(),
                str(row.get("centro_distribucion") or "").strip().lower(),
                Neo4jProveedorIngestaService._normalize_text(str(row.get("texto_original") or "")),
                str(row.get("precio_proveedor") if row.get("precio_proveedor") is not None else ""),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def split_matched_vs_orphan(
        rows: list[dict[str, Any]],
        existing_cums: set[str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Método público para separar filas válidas y huérfanas."""
        return Neo4jProveedorIngestaService._split_matched_vs_orphan(rows, existing_cums)

    def _run_unwind_merge(self, query: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        with self._driver.session(database=self._database) as session:
            session.run(query, rows=rows)

    @staticmethod
    def _chunked(rows: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
        return [rows[i : i + chunk_size] for i in range(0, len(rows), chunk_size)]

    def ingestar_archivo_proveedor(
        self,
        *,
        file_path: str | Path,
        id_documento: str,
        proveedor: str,
        fecha_documento: date,
        column_map: dict[str, str],
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, int]:
        """
        Flujo principal de cruce proveedor vs Golden Record.

        - Lee archivo con Polars.
        - Normaliza esquema.
        - Busca CUMs válidos en Neo4j.
        - Inserta match exitoso y huérfanos por UNWIND+MERGE.
        """
        df = self._read_dataframe(file_path)
        transformed = self.transform_proveedor_dataframe(
            df,
            id_documento=id_documento,
            proveedor=proveedor,
            fecha_documento=fecha_documento,
            column_map=column_map,
        )
        rows = transformed.to_dicts()
        total_rows = len(rows)

        if progress_callback is not None:
            progress_callback(0, total_rows)

        unique_cums = sorted({str(r.get("cum") or "").strip() for r in rows if str(r.get("cum") or "").strip()})
        existing_cums = self._fetch_existing_cums(unique_cums)

        matched_rows, orphan_rows = self._split_matched_vs_orphan(rows, existing_cums)

        processed_rows = 0

        for chunk in self._chunked(matched_rows, self._chunk_size):
            self._run_unwind_merge(MATCHED_COTIZACIONES_CYPHER, chunk)
            processed_rows += len(chunk)
            if progress_callback is not None:
                progress_callback(processed_rows, total_rows)

        for chunk in self._chunked(orphan_rows, self._chunk_size):
            self._run_unwind_merge(ORPHAN_CUARENTENA_CYPHER, chunk)
            processed_rows += len(chunk)
            if progress_callback is not None:
                progress_callback(processed_rows, total_rows)

        if progress_callback is not None and processed_rows < total_rows:
            progress_callback(total_rows, total_rows)

        stats = ProveedorIngestaStats(
            total_rows=len(rows),
            matched_rows=len(matched_rows),
            orphan_rows=len(orphan_rows),
        )

        # Fase 2: auto-homologacion conservadora de huerfanos recien creados.
        reconciliation = self.homologar_huerfanos_documento(id_documento=id_documento, proveedor=proveedor)
        logger.info(
            "Ingesta proveedor completada documento=%s proveedor=%s total=%s matched=%s orphan=%s",
            id_documento,
            proveedor,
            stats.total_rows,
            stats.matched_rows,
            stats.orphan_rows,
        )
        result = stats.to_dict()
        result.update(reconciliation)
        return result
