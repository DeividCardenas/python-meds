from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

EMBEDDING_DIMENSION = 768


class CargaStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Medicamento(SQLModel, table=True):
    __tablename__ = "medicamentos"

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
