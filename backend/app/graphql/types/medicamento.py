from __future__ import annotations

from typing import Optional

import strawberry


@strawberry.type
class MedicamentoNode:
    id: strawberry.ID
    nombre_limpio: str
    distancia: float
    id_cum: Optional[str]
    laboratorio: Optional[str]
    forma_farmaceutica: Optional[str]
    registro_invima: Optional[str]
    principio_activo: Optional[str]
    precio_unitario: Optional[float] = None
    precio_empaque: Optional[float] = None
    es_regulado: bool = False
    precio_maximo_regulado: Optional[float] = None
    activo: bool = True
    estado_cum: Optional[str] = None


@strawberry.type
class CargaArchivoNode:
    id: strawberry.ID
    filename: str
    status: str


@strawberry.type
class SugerenciaCUMNode:
    id_cum: str
    nombre: str
    score: float
    principio_activo: Optional[str]
    laboratorio: Optional[str]
