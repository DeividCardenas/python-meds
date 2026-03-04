from __future__ import annotations

import strawberry


@strawberry.type
class SincronizacionTareaNode:
    """Resultado inmediato del despacho de una tarea de sincronización."""
    tarea: str
    task_id: str
    mensaje: str


@strawberry.type
class SincronizacionCatalogosNode:
    """Resultado de disparar la sincronización de catálogos al vuelo."""
    cum: SincronizacionTareaNode
    sismed: SincronizacionTareaNode
