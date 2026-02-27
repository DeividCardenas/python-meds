from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

from app.models.medicamento import CargaStatus


class Proveedor(SQLModel, table=True):
    """Registry of known pharmaceutical suppliers."""

    __tablename__ = "proveedores"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    nombre: str = Field(sa_column=Column(String, nullable=False))
    codigo: str = Field(sa_column=Column(String, nullable=False, unique=True, index=True))


class ProveedorArchivo(SQLModel, table=True):
    """Tracks supplier price-list uploads through the staging pipeline."""

    __tablename__ = "proveedor_archivos"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    proveedor_id: UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("proveedores.id"), nullable=True, index=True),
    )
    filename: str = Field(sa_column=Column(String, nullable=False))
    status: CargaStatus = Field(
        default=CargaStatus.PENDING,
        sa_column=Column(String, nullable=False),
    )
    # Raw list of column names detected from the uploaded file
    columnas_detectadas: list[str] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    # User-confirmed mapping: standard field → original column name
    # e.g. {"cum_code": "Código CUM", "precio_unitario": "Precio UMD"}
    mapeo_columnas: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    fecha_carga: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    errores_log: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


class StagingPrecioProveedor(SQLModel, table=True):
    """
    Staging table for individual rows from supplier price files.

    Core business metrics are extracted into typed columns.
    The full original row is preserved verbatim in ``datos_raw``
    (JSONB vault) for full traceability.
    """

    __tablename__ = "staging_precios_proveedor"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    archivo_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("proveedor_archivos.id"), nullable=False, index=True),
    )
    fila_numero: int = Field(sa_column=Column(Integer, nullable=False))

    # --- Core business fields (may be NULL when not mapped / not present) ---
    cum_code: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True, index=True),
    )
    precio_unitario: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    vigente_desde: date | None = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
    )
    vigente_hasta: date | None = Field(
        default=None,
        sa_column=Column(Date, nullable=True),
    )
    # Free-text description used for CUM fuzzy matching when cum_code is absent
    descripcion_raw: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )

    # --- Homologation state ---
    # PENDIENTE → APROBADO | RECHAZADO
    estado_homologacion: str = Field(
        default="PENDIENTE",
        sa_column=Column(String, nullable=False, index=True),
    )
    # FK to medicamentos.id once the row has been approved
    medicamento_id: UUID | None = Field(
        default=None,
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("medicamentos.id"), nullable=True),
    )

    # --- JSONB vaults ---
    # Complete original row exactly as read from the supplier file
    datos_raw: dict[str, Any] = Field(
        sa_column=Column(JSONB, nullable=False),
    )
    # Top-N CUM suggestions returned by the fuzzy matcher
    # Each item: {"id_cum": str, "nombre": str, "score": float, ...}
    sugerencias_cum: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
