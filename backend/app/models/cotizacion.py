"""Database model for hospital bulk-quotation jobs."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel


class CotizacionLote(SQLModel, table=True):
    """
    Represents one bulk-quotation job submitted by a hospital user.

    Lifecycle
    ---------
    PENDING → PROCESSING → COMPLETED | FAILED

    The ``resultado`` JSONB field stores the full list of per-drug result rows
    once the job completes.  The ``resumen`` field stores aggregate stats.

    Each result row structure:
    {
        "nombre_input":       str,
        "parse_warnings":     list[str],
        "match_stage":        str,   # EXACT | FUZZY_INN_SAFE | SYNONYM_DICT | NO_MATCH | ERROR
        "match_confidence":   float,
        "cum_id":             str | null,
        "nombre_matcheado":   str | null,
        "forma_farmaceutica": str | null,
        "concentracion":      str | null,
        "reject_reason":      str | null,
        "inn_score":          float | null,
        "precios_count":      int,
        "mejor_precio":       PrecioRow | null,  # most-recent price
        "todos_precios":      list[PrecioRow],
    }

    PrecioRow:
    {
        "proveedor_id":         str | null,
        "proveedor_nombre":     str,
        "proveedor_codigo":     str | null,
        "precio_unitario":      float | null,
        "precio_unidad":        float | null,
        "precio_presentacion":  float | null,
        "porcentaje_iva":       float | null,
        "vigente_desde":        str | null,
        "vigente_hasta":        str | null,
        "fecha_publicacion":    str,
    }
    """

    __tablename__ = "cotizaciones_lote"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    hospital_id: str = Field(
        default="GLOBAL",
        sa_column=Column(String, nullable=False, index=True),
    )
    filename: str = Field(sa_column=Column(String, nullable=False))
    status: str = Field(
        default="PENDING",
        sa_column=Column(String, nullable=False, index=True),
    )
    # Full list of per-drug result rows (set when COMPLETED)
    resultado: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    # Aggregate summary stats
    resumen: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    fecha_creacion: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=False), nullable=False),
    )
    fecha_completado: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=False), nullable=True),
    )
