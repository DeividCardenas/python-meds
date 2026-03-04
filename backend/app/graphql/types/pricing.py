from __future__ import annotations

from typing import Optional

import strawberry


@strawberry.type
class ProveedorArchivoNode:
    id: strawberry.ID
    filename: str
    status: str
    columnas_detectadas: Optional[list[str]]
    mapeo_sugerido: Optional[str]  # JSON-encoded dict of auto-detected mapping


@strawberry.type
class StagingFilaNode:
    id: strawberry.ID
    fila_numero: int
    cum_code: Optional[str]
    precio_unitario: Optional[float]
    precio_unidad: Optional[float]
    precio_presentacion: Optional[float]
    porcentaje_iva: Optional[float]
    descripcion_raw: Optional[str]
    estado_homologacion: str
    sugerencias_cum: Optional[str]  # JSON-encoded list
    datos_raw: str  # JSON-encoded dict
    # Pillar 3: missing-date flag
    fecha_vigencia_indefinida: bool = False
    # Pillar 4: normalised confidence score ∈ [0,1]
    confianza_score: Optional[float] = None


@strawberry.type
class PublicarResultadoNode:
    """Result returned by the publicarPreciosProveedor mutation."""

    filas_publicadas: int
    archivo_id: strawberry.ID
    status: str


@strawberry.input
class MapeoColumnasInput:
    cum_code: Optional[str] = None
    precio_unitario: Optional[str] = None
    precio_unidad: Optional[str] = None
    precio_presentacion: Optional[str] = None
    porcentaje_iva: Optional[str] = None
    descripcion: Optional[str] = None
    vigente_desde: Optional[str] = None
    vigente_hasta: Optional[str] = None
