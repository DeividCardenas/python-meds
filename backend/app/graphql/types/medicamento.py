from __future__ import annotations

from typing import Optional

import strawberry


@strawberry.type(name="Medicamento")
class MedicamentoNode:
    id: strawberry.ID
    nombre_comercial: Optional[str] = None
    marca_comercial: Optional[str] = None
    nombre_limpio: str
    dosis_cantidad: Optional[float] = None
    dosis_unidad: Optional[str] = None
    distancia: float
    id_cum: Optional[str]
    laboratorio: Optional[str]
    forma_farmaceutica: Optional[str]
    via_administracion: Optional[str] = None
    presentacion: Optional[str] = None
    tipo_liberacion: Optional[str] = None
    volumen_solucion: Optional[float] = None
    registro_invima: Optional[str]
    principio_activo: Optional[str]
    precio_unitario: Optional[float] = None
    precio_empaque: Optional[float] = None
    es_regulado: bool = False
    precio_maximo_regulado: Optional[float] = None
    activo: bool = True
    estado_cum: Optional[str] = None
    # Mejor precio de proveedor cargado (solo populado en comparativaPrecios)
    mejor_precio_proveedor: Optional[float] = None
    mejor_proveedor_nombre: Optional[str] = None

    @strawberry.field(name="dosisCanitidad")
    def dosis_canitidad_alias(self) -> Optional[float]:
        return self.dosis_cantidad


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
