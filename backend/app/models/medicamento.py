from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

EMBEDDING_DIMENSION = 768


class CargaStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PUBLICADO = "PUBLICADO"


class Medicamento(SQLModel, table=True):
    __tablename__ = "medicamentos"
    __table_args__ = (
        Index("ix_medicamentos_nombre_gin", "nombre_limpio", postgresql_using="gin", postgresql_ops={"nombre_limpio": "gin_trgm_ops"}),
        Index("ix_medicamentos_principio_activo", text("lower(coalesce(principio_activo, ''))"), postgresql_using="btree"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    id_cum: str | None = Field(default=None, sa_column=Column(String, nullable=True, unique=True, index=True))
    nombre_limpio: str = Field(sa_column=Column(String, nullable=False, index=True))
    atc: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    registro_invima: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    estado_regulatorio: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    laboratorio: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    principio_activo: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    forma_farmaceutica: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    embedding_status: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    embedding: list[float] | None = Field(default=None, sa_column=Column(Vector(EMBEDDING_DIMENSION), nullable=True))
    # Estado del CUM: valor raw de medicamentos_cum.estadocum (ej. "Vigente", "Vencido")
    estado_cum: str | None = Field(default=None, sa_column=Column(String, nullable=True, index=True))
    # Flag desnormalizado: True cuando estadocum es Vigente/Activo, True por defecto para
    # medicamentos sin id_cum (no vinculados al catálogo INVIMA)
    activo: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true"))


class PrecioReferencia(SQLModel, table=True):
    __tablename__ = "precios_referencia"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    medicamento_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("medicamentos.id"), nullable=False, index=True)
    )
    empresa: str = Field(sa_column=Column(String, nullable=False))
    precio: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 2), nullable=True))
    fu: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))
    vpc: Decimal | None = Field(default=None, sa_column=Column(Numeric(18, 8), nullable=True))


class CargaArchivo(SQLModel, table=True):
    __tablename__ = "cargas_archivo"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    filename: str = Field(sa_column=Column(String, nullable=False))
    status: CargaStatus = Field(default=CargaStatus.PENDING, sa_column=Column(String, nullable=False))
    errores_log: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class MedicamentoCUM(SQLModel, table=True):
    """
    Tabla que almacena los registros del Código Único de Medicamentos (CUM)
    descargados desde los catálogos INVIMA via la API Socrata de datos.gov.co.

    La clave primaria id_cum es la concatenación estricta de expediente y
    consecutivocum (ej. "123456-01"), lo que garantiza unicidad por CUM.
    """

    __tablename__ = "medicamentos_cum"

    # PK: concatenación de expediente + "-" + consecutivocum
    id_cum: str = Field(sa_column=Column(String, primary_key=True))

    # Campos atómicos provenientes de la API Socrata
    expediente: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    consecutivocum: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    producto: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    titular: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    registrosanitario: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    fechaexpedicion: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    fechavencimiento: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    estadoregistro: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    cantidadcum: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    descripcioncomercial: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    estadocum: str | None = Field(default=None, sa_column=Column(String, nullable=True, index=True))
    fechaactivo: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    fechainactivo: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    muestramedica: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    unidad: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    atc: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    descripcionatc: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    viaadministracion: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    concentracion: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    principioactivo: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    unidadmedida: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    cantidad: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    unidadreferencia: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    formafarmaceutica: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    nombrerol: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    tiporol: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    modalidad: str | None = Field(default=None, sa_column=Column(String, nullable=True))


class CUMSyncLog(SQLModel, table=True):
    """
    Tabla de control que almacena la fecha de la última sincronización exitosa
    de cada catálogo CUM, junto con el timestamp rowsUpdatedAt de Socrata en
    el momento de esa sincronización.  Se usa para el Smart Sync: si el
    dataset de Socrata no ha cambiado desde la última descarga, se omite la
    extracción masiva.
    """

    __tablename__ = "cum_sync_log"

    # fuente es la clave del catálogo (ej. "vigentes", "en_tramite", "vencidos")
    fuente: str = Field(sa_column=Column(String, primary_key=True))
    rows_updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    ultima_sincronizacion: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
