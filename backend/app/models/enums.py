"""Centralised Enum definitions shared across catalog and pricing models.

Keep all status/state Enums here to avoid cross-module coupling and
silent bugs caused by bare string comparisons.
"""
from __future__ import annotations

from enum import Enum


class CargaStatus(str, Enum):
    """Lifecycle states for a file-upload job (CargaArchivo / ProveedorArchivo)."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PUBLICADO = "PUBLICADO"


class CotizacionStatus(str, Enum):
    """Lifecycle states for a bulk-quotation job (CotizacionLote)."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
