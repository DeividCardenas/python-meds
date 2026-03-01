"""Bulk Quotation Service — Hospital Drug List → Best Prices.

Given a CSV/Excel file containing a hospital's drug list (one row per drug,
identified only by free-text name), this service:

1. Parses each drug name through the drug_parser pipeline.
2. Matches each parsed drug against the genhospi_catalog DB (matching_engine).
3. For every successful match retrieves all published supplier prices from
   genhospi_pricing (precios_proveedor table).
4. Selects the **most-recently published price** as the best price for quoting.
5. Persists the full result set as JSONB in the cotizaciones_lote table.
6. Produces an exportable DataFrame (CSV or Excel) for the end user.

Design decisions
----------------
- Input is matched by NAME only (not CUM code).  Hospitals frequently have
  incorrect CUM/ATC codes in their formularies; the free-text name via
  drug_parser + matching_engine is more reliable.
- "Best price" is defined as the most recently published price
  (fecha_publicacion DESC).  This ensures quotes reflect current market prices.
- Each drug row in the result always returns ALL available supplier prices so
  the user can compare alternatives even when the system picks the best one.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import polars as pl
from sqlmodel import select

from app.models.cotizacion import CotizacionLote
from app.models.pricing import PrecioProveedor, Proveedor
from app.services.drug_parser import parse
from app.services.matching_engine import match_drug

logger = logging.getLogger(__name__)

# Column name candidates for the drug-name column in the hospital CSV.
# Tried in order; the first match wins.  Falls back to the first column.
_NOMBRE_COLUMNS = [
    "nombre", "Nombre", "NOMBRE",
    "medicamento", "Medicamento", "MEDICAMENTO",
    "producto", "Producto", "PRODUCTO",
    "description", "name",
]


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------

def _read_nombres(file_path: str) -> list[str]:
    """
    Read drug names from a CSV or Excel file.

    Accepts a single 'nombre' column (as in the Sanitas formulary) or any
    file where the first recognized column contains the drug names.
    Empty / whitespace-only rows are silently skipped.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in {".xlsx", ".xls"}:
        df = pl.read_excel(path)
    elif suffix in {".tsv", ".txt"}:
        df = pl.read_csv(path, separator="\t", infer_schema_length=0)
    else:
        df = pl.read_csv(path, infer_schema_length=0)

    name_col: str | None = None
    for candidate in _NOMBRE_COLUMNS:
        if candidate in df.columns:
            name_col = candidate
            break
    if name_col is None:
        name_col = df.columns[0]

    return [
        v.strip()
        for v in df[name_col].cast(pl.Utf8).to_list()
        if v is not None and str(v).strip()
    ]


# ---------------------------------------------------------------------------
# Price lookup
# ---------------------------------------------------------------------------

async def _get_precios_para_cum(
    pricing_session: Any,
    cum_code: str,
    proveedor_map: dict[str, tuple[str, str]],  # proveedor_id → (nombre, codigo)
) -> list[dict[str, Any]]:
    """
    Return all published prices for *cum_code* ordered by fecha_publicacion DESC.

    The first item is the most recently published price (= best price for quoting).
    ``proveedor_map`` is a pre-loaded dict to avoid N+1 queries.
    """
    stmt = (
        select(PrecioProveedor)
        .where(PrecioProveedor.cum_code == cum_code)
        .order_by(PrecioProveedor.fecha_publicacion.desc())
        .limit(20)
    )
    rows = (await pricing_session.exec(stmt)).all()

    result: list[dict[str, Any]] = []
    for precio in rows:
        pid = str(precio.proveedor_id) if precio.proveedor_id else None
        nombre_prov, codigo_prov = proveedor_map.get(pid, ("Desconocido", None)) if pid else ("Desconocido", None)
        result.append({
            "proveedor_id":        pid,
            "proveedor_nombre":    nombre_prov,
            "proveedor_codigo":    codigo_prov,
            "precio_unitario":     float(precio.precio_unitario)     if precio.precio_unitario     is not None else None,
            "precio_unidad":       float(precio.precio_unidad)       if precio.precio_unidad       is not None else None,
            "precio_presentacion": float(precio.precio_presentacion) if precio.precio_presentacion is not None else None,
            "porcentaje_iva":      float(precio.porcentaje_iva)      if precio.porcentaje_iva      is not None else None,
            "vigente_desde":       str(precio.vigente_desde)         if precio.vigente_desde       else None,
            "vigente_hasta":       str(precio.vigente_hasta)         if precio.vigente_hasta       else None,
            "fecha_publicacion":   precio.fecha_publicacion.isoformat() if precio.fecha_publicacion else None,
        })
    return result


async def _build_proveedor_map(pricing_session: Any) -> dict[str, tuple[str, str]]:
    """Pre-load all proveedores into a dict for O(1) lookup during price assembly."""
    proveedores = (await pricing_session.exec(select(Proveedor))).all()
    return {
        str(p.id): (p.nombre, p.codigo)
        for p in proveedores
    }


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------

async def cotizar_lista(
    file_path: str,
    hospital_id: str,
    lote_id: UUID,
    catalog_session_factory: Any,
    pricing_session_factory: Any,
) -> dict[str, Any]:
    """
    Full pipeline: read file → parse → match → price lookup → persist results.

    Parameters
    ----------
    file_path            : Absolute path to the uploaded CSV/Excel file.
    hospital_id          : Hospital identifier for synonym-dict scoping.
    lote_id              : PK of the CotizacionLote row to update on completion.
    catalog_session_factory : Factory for genhospi_catalog async sessions.
    pricing_session_factory : Factory for genhospi_pricing async sessions.

    Returns
    -------
    A summary dict with aggregate statistics.
    """
    nombres = _read_nombres(file_path)
    logger.info(
        "cotizar_lista: %d medicamentos  hospital=%s  lote=%s",
        len(nombres), hospital_id, lote_id,
    )

    resultado: list[dict[str, Any]] = []

    async with catalog_session_factory() as catalog_session:
        async with pricing_session_factory() as pricing_session:

            # Pre-load provider names once — avoids N+1 queries per drug
            proveedor_map = await _build_proveedor_map(pricing_session)

            for nombre in nombres:
                try:
                    # ── Parse ──────────────────────────────────────────────
                    parsed = parse(nombre)

                    # ── Match against catalog ───────────────────────────────
                    match = await match_drug(catalog_session, parsed, hospital_id)

                    # ── Fetch prices ────────────────────────────────────────
                    precios: list[dict[str, Any]] = []
                    if match.cum_id:
                        precios = await _get_precios_para_cum(
                            pricing_session, match.cum_id, proveedor_map
                        )

                    # Best price = index 0 (already sorted DESC by fecha_publicacion)
                    mejor_precio = precios[0] if precios else None

                    resultado.append({
                        "nombre_input":       nombre,
                        "parse_warnings":     match.parser_warnings or [],
                        "match_stage":        match.stage.value,
                        "match_confidence":   round(match.confidence, 4),
                        "cum_id":             match.cum_id,
                        "nombre_matcheado":   match.db_principio_activo,
                        "forma_farmaceutica": match.db_forma,
                        "concentracion":      match.db_concentracion,
                        "reject_reason":      match.reject_reason.value if match.reject_reason else None,
                        "inn_score":          round(match.inn_score, 4) if match.inn_score is not None else None,
                        "precios_count":      len(precios),
                        "mejor_precio":       mejor_precio,
                        "todos_precios":      precios,
                    })

                except Exception as exc:
                    logger.error("cotizar_lista: error en '%s': %s", nombre, exc, exc_info=True)
                    resultado.append({
                        "nombre_input":       nombre,
                        "parse_warnings":     [str(exc)],
                        "match_stage":        "ERROR",
                        "match_confidence":   0.0,
                        "cum_id":             None,
                        "nombre_matcheado":   None,
                        "forma_farmaceutica": None,
                        "concentracion":      None,
                        "reject_reason":      "PROCESSING_ERROR",
                        "inn_score":          None,
                        "precios_count":      0,
                        "mejor_precio":       None,
                        "todos_precios":      [],
                    })

    # ── Summary stats ────────────────────────────────────────────────────────
    total      = len(resultado)
    con_match  = sum(1 for r in resultado if r["match_stage"] not in ("NO_MATCH", "ERROR"))
    con_precio = sum(1 for r in resultado if r["precios_count"] > 0)

    resumen: dict[str, Any] = {
        "total":        total,
        "con_match":    con_match,
        "sin_match":    total - con_match,
        "con_precio":   con_precio,
        "sin_precio":   total - con_precio,
        "tasa_match":   round(con_match  / total, 4) if total > 0 else 0.0,
        "tasa_precio":  round(con_precio / total, 4) if total > 0 else 0.0,
    }

    # ── Persist results ──────────────────────────────────────────────────────
    async with pricing_session_factory() as session:
        lote: CotizacionLote | None = await session.get(CotizacionLote, lote_id)
        if lote:
            lote.status           = "COMPLETED"
            lote.resultado        = resultado
            lote.resumen          = resumen
            lote.fecha_completado = datetime.utcnow()
            session.add(lote)
            await session.commit()

    logger.info("cotizar_lista: lote=%s completado  resumen=%s", lote_id, resumen)
    return resumen


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def exportar_resultado(
    resultado: list[dict[str, Any]],
    formato: str = "csv",
) -> bytes:
    """
    Convert the quote result list to a flat CSV or Excel file.

    The output contains one row per drug with the BEST (most-recent) price
    expanded into individual columns, plus a 'num_proveedores' column showing
    how many supplier prices are available.

    Parameters
    ----------
    resultado : list of result row dicts from ``cotizar_lista``.
    formato   : "csv" (default) or "excel".
    """
    rows: list[dict[str, Any]] = []
    for r in resultado:
        mejor: dict[str, Any] = r.get("mejor_precio") or {}
        iva_raw = mejor.get("porcentaje_iva")
        rows.append({
            "nombre_input":        r["nombre_input"],
            "match_estado":        r["match_stage"],
            "match_confianza":     r["match_confidence"],
            "cum_id":              r.get("cum_id") or "",
            "principio_activo":    r.get("nombre_matcheado") or "",
            "forma_farmaceutica":  r.get("forma_farmaceutica") or "",
            "concentracion":       r.get("concentracion") or "",
            "proveedor_mejor":     mejor.get("proveedor_nombre") or "",
            "precio_unitario":     mejor.get("precio_unitario"),
            "precio_unidad_min":   mejor.get("precio_unidad"),
            "precio_presentacion": mejor.get("precio_presentacion"),
            "iva_pct":             round(float(iva_raw) * 100, 2) if iva_raw is not None else None,
            "vigente_desde":       mejor.get("vigente_desde") or "",
            "vigente_hasta":       mejor.get("vigente_hasta") or "",
            "fecha_precio":        mejor.get("fecha_publicacion") or "",
            "num_proveedores":     r["precios_count"],
            "sin_precio":          "SI" if not r.get("mejor_precio") else "NO",
            "sin_match":           "SI" if r["match_stage"] in ("NO_MATCH", "ERROR") else "NO",
        })

    df = pl.DataFrame(rows, infer_schema_length=len(rows) or 1)

    if formato == "excel":
        buffer = io.BytesIO()
        df.write_excel(buffer)
        return buffer.getvalue()

    return df.write_csv().encode("utf-8")
