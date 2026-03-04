from __future__ import annotations

from typing import Optional

import strawberry

from app.graphql.types.cotizacion import (
    PrecioItemNode,
    CotizacionFilaNode,
    ResumenCotizacionNode,
    CotizacionLoteNode,
)
from app.models.cotizacion import CotizacionLote


def _precio_dict_to_node(d: dict) -> PrecioItemNode:
    return PrecioItemNode(
        proveedor_id=d.get("proveedor_id"),
        proveedor_nombre=d.get("proveedor_nombre") or "Desconocido",
        proveedor_codigo=d.get("proveedor_codigo"),
        precio_unitario=d.get("precio_unitario"),
        precio_unidad=d.get("precio_unidad"),
        precio_presentacion=d.get("precio_presentacion"),
        porcentaje_iva=d.get("porcentaje_iva"),
        vigente_desde=d.get("vigente_desde"),
        vigente_hasta=d.get("vigente_hasta"),
        fecha_publicacion=d.get("fecha_publicacion"),
    )


def _fila_dict_to_node(
    d: dict, regulacion_map: Optional[dict] = None
) -> CotizacionFilaNode:
    mejor_raw = d.get("mejor_precio")
    todos_raw = d.get("todos_precios") or []
    cum_id = d.get("cum_id")
    reg = (regulacion_map or {}).get(cum_id) if cum_id else None
    return CotizacionFilaNode(
        nombre_input=d.get("nombre_input", ""),
        parse_warnings=d.get("parse_warnings") or [],
        match_stage=d.get("match_stage", "ERROR"),
        match_confidence=float(d.get("match_confidence", 0.0)),
        cum_id=cum_id,
        nombre_matcheado=d.get("nombre_matcheado"),
        forma_farmaceutica=d.get("forma_farmaceutica"),
        concentracion=d.get("concentracion"),
        reject_reason=d.get("reject_reason"),
        inn_score=float(d["inn_score"]) if d.get("inn_score") is not None else None,
        precios_count=int(d.get("precios_count", 0)),
        mejor_precio=_precio_dict_to_node(mejor_raw) if mejor_raw else None,
        todos_precios=[_precio_dict_to_node(p) for p in todos_raw],
        es_regulado=reg is not None,
        precio_maximo_regulado=float(reg.precio_maximo_venta)
            if reg and reg.precio_maximo_venta is not None else None,
    )


def _lote_to_node(
    lote: CotizacionLote, regulacion_map: Optional[dict] = None
) -> CotizacionLoteNode:
    resumen_node: Optional[ResumenCotizacionNode] = None
    if lote.resumen:
        r = lote.resumen
        resumen_node = ResumenCotizacionNode(
            total=r.get("total", 0),
            con_match=r.get("con_match", 0),
            sin_match=r.get("sin_match", 0),
            con_precio=r.get("con_precio", 0),
            sin_precio=r.get("sin_precio", 0),
            tasa_match=float(r.get("tasa_match", 0.0)),
            tasa_precio=float(r.get("tasa_precio", 0.0)),
        )

    filas_nodes: Optional[list[CotizacionFilaNode]] = None
    if lote.resultado is not None:
        filas_nodes = [_fila_dict_to_node(f, regulacion_map) for f in lote.resultado]

    return CotizacionLoteNode(
        id=strawberry.ID(str(lote.id)),
        hospital_id=lote.hospital_id,
        filename=lote.filename,
        status=lote.status,
        fecha_creacion=lote.fecha_creacion.isoformat(),
        fecha_completado=lote.fecha_completado.isoformat() if lote.fecha_completado else None,
        resumen=resumen_node,
        filas=filas_nodes,
    )
