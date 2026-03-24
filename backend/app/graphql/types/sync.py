from __future__ import annotations

from typing import Optional

import strawberry
from strawberry.scalars import JSON


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


@strawberry.type
class TaskStatusNode:
    """Estado actual de una tarea de background en Celery."""

    task_id: str
    status: str
    mensaje: str
    progress_pct: Optional[float] = None
    resultado: Optional[JSON] = None
    error: Optional[str] = None
