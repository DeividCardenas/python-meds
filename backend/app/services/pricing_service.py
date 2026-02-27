from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import polars as pl
from sqlalchemy import func, text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.medicamento import CargaStatus, Medicamento
from app.models.pricing import ProveedorArchivo, StagingPrecioProveedor
from app.services.normalizer import normalize_dataframe_column, normalize_pharma_text
from app.services.supplier_detector import detectar_proveedor

logger = logging.getLogger(__name__)

# Confidence threshold above which a match is auto-approved without human review
AUTO_APPROVE_THRESHOLD: float = 0.99

# Standard field names that the column mapper understands
STANDARD_FIELDS = ["cum_code", "precio_unitario", "descripcion", "vigente_desde", "vigente_hasta"]

# Heuristic patterns for auto-detecting which supplier column maps to which
# standard field.  Each pattern is tried against the *lower-cased* column name.
_AUTO_DETECT_PATTERNS: dict[str, list[str]] = {
    "cum_code": [r"cum", r"codigo\s*cum", r"c[oó]digo.*cum", r"axapta"],  # "Código Axapta" is used by MEGALABS for CUM-like product codes
    "precio_unitario": [r"precio.*unit", r"unit.*price", r"precio\s*umd", r"precio"],
    "descripcion": [r"descripci[oó]n", r"producto", r"nombre", r"description"],
    "vigente_desde": [r"vigente?\s*desde", r"valid\s*from", r"fecha\s*inicio"],
    "vigente_hasta": [r"vigente?\s*hasta", r"valid\s*to", r"fecha\s*fin", r"fecha\s*vencimiento"],
}


def _read_dataframe(file_path: str) -> pl.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pl.read_excel(path)
    if suffix in {".tsv", ".txt"}:
        return pl.read_csv(path, separator="\t", infer_schema_length=0)
    return pl.read_csv(path, infer_schema_length=0)


def detectar_columnas(file_path: str) -> list[str]:
    """Return the list of column headers found in *file_path* without loading all rows."""
    df = _read_dataframe(file_path)
    return df.columns


def sugerir_mapeo_automatico(columnas: list[str]) -> dict[str, str]:
    """
    Heuristically map raw supplier column names to our standard field names.
    Returns a partial dict – only fields where a confident match was found.
    """
    mapping: dict[str, str] = {}
    for col in columnas:
        col_lower = col.lower()
        for field, patterns in _AUTO_DETECT_PATTERNS.items():
            if field in mapping:
                continue
            for pattern in patterns:
                if re.search(pattern, col_lower):
                    mapping[field] = col
                    break
    return mapping


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text_val = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            from datetime import datetime as _dt

            return _dt.strptime(text_val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    raw = str(value).strip().replace(" ", "")
    if not raw:
        return None
    # Handle both comma-decimal (European) and dot-decimal (US) formats
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


async def buscar_sugerencias_cum(
    session: AsyncSession,
    texto: str,
    limite: int = 3,
) -> list[dict[str, Any]]:
    """
    Return up to *limite* CUM code suggestions for the given free-text
    description using PostgreSQL full-text search with trigram ranking.
    Leverages the GIN trgm index on ``medicamentos.nombre_limpio``.

    The input text is first normalized via the Polars-powered
    :func:`~app.services.normalizer.normalize_pharma_text` pipeline so that
    pharmaceutical noise (packaging, form suffixes, accent variations) does
    not reduce recall.
    """
    if not texto or not texto.strip():
        return []

    # Pillar 1: Polars-powered normalization before hitting the DB
    normalized = normalize_pharma_text(texto)
    if not normalized:
        return []

    # FTS with similarity fallback
    tsvector_expr = func.to_tsvector("simple", func.lower(Medicamento.nombre_limpio))
    tsquery_expr = func.plainto_tsquery("simple", normalized)
    rank_expr = func.ts_rank_cd(tsvector_expr, tsquery_expr).label("rank")
    similarity_expr = func.similarity(func.lower(Medicamento.nombre_limpio), normalized).label("similarity")

    stmt = (
        select(
            Medicamento.id_cum,
            Medicamento.nombre_limpio,
            Medicamento.principio_activo,
            Medicamento.laboratorio,
            rank_expr,
            similarity_expr,
        )
        .where(
            tsvector_expr.op("@@")(tsquery_expr)
            | (similarity_expr > text("0.2"))
        )
        .order_by(rank_expr.desc(), similarity_expr.desc())
        .limit(limite)
    )

    rows = (await session.exec(stmt)).all()
    return [
        {
            "id_cum": row.id_cum,
            "nombre": row.nombre_limpio,
            "principio_activo": row.principio_activo,
            "laboratorio": row.laboratorio,
            # Pillar 4: similarity score ∈ [0,1] used as confidence signal
            "score": float(row.similarity),
        }
        for row in rows
        if row.id_cum
    ]


async def procesar_archivo_proveedor(
    archivo_id: str,
    file_path: str,
    mapeo: dict[str, str],
    session_factory: Any,
) -> dict[str, Any]:
    """
    ETL pipeline for a supplier price file.

    1. Reads the file using the confirmed *mapeo* (standard_field → column_name).
    2. Applies Polars-powered text normalization (Pillar 1) to descriptions.
    3. Extracts core business fields from each row.
    4. For rows without a CUM code, runs fuzzy CUM resolution.
    5. Pillar 3 – Missing Data Protocol: when validity dates are absent the
       row is flagged ``fecha_vigencia_indefinida=True`` instead of raising
       an error, treating the price as having an open-ended validity period.
    6. Pillar 4 – Confidence scoring: rows whose best similarity score
       exceeds ``AUTO_APPROVE_THRESHOLD`` are auto-approved (estado_homologacion
       set to "APROBADO") without human review.
    7. Inserts everything into ``staging_precios_proveedor`` with the full
       raw row stored in the JSONB vault.

    Returns a summary dict with totals.
    """
    archivo_uuid = UUID(archivo_id)

    async with session_factory() as session:
        archivo: ProveedorArchivo | None = await session.get(ProveedorArchivo, archivo_uuid)
        if archivo is None:
            raise ValueError(f"ProveedorArchivo {archivo_id} not found")
        archivo.status = CargaStatus.PROCESSING
        session.add(archivo)
        await session.commit()

    try:
        df = _read_dataframe(file_path)

        cum_col = mapeo.get("cum_code")
        precio_col = mapeo.get("precio_unitario")
        desc_col = mapeo.get("descripcion")
        desde_col = mapeo.get("vigente_desde")
        hasta_col = mapeo.get("vigente_hasta")

        # Pillar 1: Apply Polars normalizer to the description column upfront
        # so every subsequent operation works on clean text.
        if desc_col and desc_col in df.columns:
            df = normalize_dataframe_column(df, desc_col)
            desc_normalized_col = f"{desc_col}_normalized"
        else:
            desc_normalized_col = None

        rows_dicts = df.to_dicts()

        staging_rows: list[dict[str, Any]] = []

        for idx, row in enumerate(rows_dicts):
            # Serialize all values to strings for safe JSONB storage
            datos_raw: dict[str, Any] = {k: (None if v is None else str(v)) for k, v in row.items()}

            cum_code: str | None = None
            if cum_col and row.get(cum_col):
                raw_cum = str(row[cum_col]).strip()
                if raw_cum:
                    cum_code = raw_cum

            precio = _parse_decimal(row.get(precio_col)) if precio_col else None

            # Prefer the Polars-normalized description for matching; fall back
            # to the raw column when the normalizer column is not available.
            if desc_normalized_col and row.get(desc_normalized_col):
                descripcion = str(row[desc_normalized_col]).strip() or None
            elif desc_col and row.get(desc_col):
                descripcion = str(row[desc_col]).strip() or None
            else:
                descripcion = None

            # Pillar 3 – Missing Data Protocol
            # When validity date columns are not mapped OR the values are
            # absent/unparseable, set fecha_vigencia_indefinida=True and store
            # None for the date fields rather than failing the row.
            vigente_desde = _parse_date(row.get(desde_col)) if desde_col else None
            vigente_hasta = _parse_date(row.get(hasta_col)) if hasta_col else None
            fecha_vigencia_indefinida = vigente_desde is None and vigente_hasta is None

            # Skip completely empty rows
            if not cum_code and not precio and not descripcion:
                continue

            # Pillar 4 – Confidence scoring
            # Rows with a direct CUM code are treated as exact matches (1.0).
            # Rows without a CUM code start at None; the score is set after
            # fuzzy resolution below.
            confianza_score: Decimal | None = Decimal("1.0") if cum_code else None
            estado = "APROBADO" if cum_code else "PENDIENTE"

            staging_rows.append(
                {
                    "id": uuid4(),
                    "archivo_id": archivo_uuid,
                    "fila_numero": idx + 1,
                    "cum_code": cum_code,
                    "precio_unitario": precio,
                    "descripcion_raw": descripcion,
                    "vigente_desde": vigente_desde,
                    "vigente_hasta": vigente_hasta,
                    "fecha_vigencia_indefinida": fecha_vigencia_indefinida,
                    "confianza_score": confianza_score,
                    "estado_homologacion": estado,
                    "datos_raw": datos_raw,
                    "sugerencias_cum": None,
                }
            )

        # Resolve CUM suggestions for rows missing a CUM code
        rows_needing_resolution = [r for r in staging_rows if not r["cum_code"] and r["descripcion_raw"]]
        if rows_needing_resolution:
            async with session_factory() as session:
                for row in rows_needing_resolution:
                    sugerencias = await buscar_sugerencias_cum(session, row["descripcion_raw"])
                    row["sugerencias_cum"] = sugerencias

                    # Pillar 4 – Auto-approve when best similarity score is
                    # above the threshold; otherwise leave as PENDIENTE for
                    # human-in-the-loop review.
                    if sugerencias:
                        best_score = max((s["score"] for s in sugerencias), default=0.0)
                        row["confianza_score"] = Decimal(str(round(best_score, 4)))
                        if best_score >= AUTO_APPROVE_THRESHOLD:
                            row["cum_code"] = sugerencias[0]["id_cum"]
                            row["estado_homologacion"] = "APROBADO"

        # Batch insert staging rows
        if staging_rows:
            async with session_factory() as session:
                for row in staging_rows:
                    staging_obj = StagingPrecioProveedor(
                        id=row["id"],
                        archivo_id=row["archivo_id"],
                        fila_numero=row["fila_numero"],
                        cum_code=row["cum_code"],
                        precio_unitario=row["precio_unitario"],
                        descripcion_raw=row["descripcion_raw"],
                        vigente_desde=row["vigente_desde"],
                        vigente_hasta=row["vigente_hasta"],
                        fecha_vigencia_indefinida=row["fecha_vigencia_indefinida"],
                        confianza_score=row["confianza_score"],
                        estado_homologacion=row["estado_homologacion"],
                        datos_raw=row["datos_raw"],
                        sugerencias_cum=row["sugerencias_cum"],
                    )
                    session.add(staging_obj)
                await session.commit()

        con_cum = sum(1 for r in staging_rows if r["cum_code"])
        sin_cum = len(staging_rows) - con_cum
        auto_aprobados = sum(1 for r in staging_rows if r["estado_homologacion"] == "APROBADO")
        indefinite_dates = sum(1 for r in staging_rows if r["fecha_vigencia_indefinida"])
        resumen: dict[str, Any] = {
            "total_filas": len(rows_dicts),
            "staging_insertados": len(staging_rows),
            "con_cum": con_cum,
            "sin_cum_requieren_resolucion": sin_cum,
            "auto_aprobados": auto_aprobados,
            "fechas_indefinidas": indefinite_dates,
        }

        async with session_factory() as session:
            archivo = await session.get(ProveedorArchivo, archivo_uuid)
            if archivo:
                archivo.status = CargaStatus.COMPLETED
                archivo.errores_log = resumen
                session.add(archivo)
                await session.commit()

        return resumen

    except Exception:
        async with session_factory() as session:
            archivo = await session.get(ProveedorArchivo, archivo_uuid)
            if archivo:
                archivo.status = CargaStatus.FAILED
                session.add(archivo)
                await session.commit()
        raise
