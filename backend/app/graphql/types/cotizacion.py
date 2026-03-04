from __future__ import annotations

from typing import Optional

import strawberry


@strawberry.type
class PrecioItemNode:
    """One supplier price entry for a matched drug."""
    proveedor_id:        Optional[str]
    proveedor_nombre:    str
    proveedor_codigo:    Optional[str]
    precio_unitario:     Optional[float]
    precio_unidad:       Optional[float]
    precio_presentacion: Optional[float]
    porcentaje_iva:      Optional[float]
    vigente_desde:       Optional[str]
    vigente_hasta:       Optional[str]
    fecha_publicacion:   Optional[str]


@strawberry.type
class CotizacionFilaNode:
    """Per-drug result row within a bulk-quotation job."""
    nombre_input:           str
    parse_warnings:         list[str]
    match_stage:            str    # EXACT | FUZZY_INN_SAFE | SYNONYM_DICT | NO_MATCH | ERROR
    match_confidence:       float
    cum_id:                 Optional[str]
    nombre_matcheado:       Optional[str]
    forma_farmaceutica:     Optional[str]
    concentracion:          Optional[str]
    reject_reason:          Optional[str]
    inn_score:              Optional[float]
    precios_count:          int
    mejor_precio:           Optional[PrecioItemNode]
    todos_precios:          list[PrecioItemNode]
    es_regulado:            bool = False
    precio_maximo_regulado: Optional[float] = None


@strawberry.type
class ResumenCotizacionNode:
    total:       int
    con_match:   int
    sin_match:   int
    con_precio:  int
    sin_precio:  int
    tasa_match:  float
    tasa_precio: float


@strawberry.type
class CotizacionLoteNode:
    """A hospital bulk-quotation job (upload → process → results)."""
    id:               strawberry.ID
    hospital_id:      str
    filename:         str
    status:           str   # PENDING | PROCESSING | COMPLETED | FAILED
    fecha_creacion:   str
    fecha_completado: Optional[str]
    resumen:          Optional[ResumenCotizacionNode]
    filas:            Optional[list[CotizacionFilaNode]]
