from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID as PGUUID
from sqlmodel import Field, SQLModel

from app.models.enums import CargaStatus  # noqa: F401 – re-exported for back-compat

EMBEDDING_DIMENSION = 768


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
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )
    id_cum: str | None = Field(
        default=None,
        sa_column=Column(
            String,
            ForeignKey("medicamentos_cum.id_cum"),
            nullable=True,
            unique=True,
            index=True,
        ),
    )
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
    # Columna STORED GENERATED para búsqueda FTS eficiente (migración 0018).
    # PostgreSQL la mantiene actualizada automáticamente; la app nunca escribe aquí.
    # Permite usar el índice GIN ix_medicamentos_nombre_tsvector_gin con @@.
    nombre_tsvector: str | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed(
                "to_tsvector('simple', lower(coalesce(nombre_limpio, '')))",
                persisted=True,
            ),
            nullable=True,
        ),
    )


class PrecioReferencia(SQLModel, table=True):
    __tablename__ = "precios_referencia"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )
    medicamento_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("medicamentos.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    empresa: str = Field(sa_column=Column(String, nullable=False))
    activo: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true", index=True))
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
    __table_args__ = (
        Index("ix_medicamentos_cum_registrosanitario", "registrosanitario"),
        Index("ix_medicamentos_cum_expediente", "expediente"),
        Index(
            "ix_medicamentos_cum_principioactivo_gin",
            text("lower(coalesce(principioactivo, '')) gin_trgm_ops"),
            postgresql_using="gin",
        ),
        Index(
            "ix_medicamentos_cum_descripcioncomercial_gin",
            text("lower(coalesce(descripcioncomercial, '')) gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )

    # PK: concatenación de expediente + "-" + consecutivocum
    id_cum: str = Field(sa_column=Column(String, primary_key=True))
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    # Campos atómicos provenientes de la API Socrata
    expediente: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    consecutivocum: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    producto: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    titular: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    registrosanitario: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    fechaexpedicion: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    fechavencimiento: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    estadoregistro: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    cantidadcum: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
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


class PrecioMedicamento(SQLModel, table=True):
    """
    Precios regulados y de mercado (SISMED) de cada CUM.

    La clave natural del registro es la combinación (id_cum, canal_mercado),
    que refleja que un mismo CUM puede tener precios distintos en el canal
    institucional ('INS') y en el canal comercial ('COM').

    El campo id_cum es una llave lógica hacia medicamentos_cum.id_cum
    (sin FK a nivel de BD para permitir precios SISMED de CUMs históricos
    o no incluidos aún en el catálogo activo de INVIMA).

    Fuentes de datos
    ----------------
    - Precios regulados : Circulares / actos administrativos CNPMDM
    - Precios de mercado: Dataset SISMED de datos.gov.co (resource 3he6-m866)
    """

    __tablename__ = "precios_medicamentos"
    __table_args__ = (
        UniqueConstraint("id_cum", "canal_mercado", name="uq_precio_cum_canal"),
        Index("ix_precios_medicamentos_id_cum", "id_cum"),
        CheckConstraint("canal_mercado IN ('INS', 'COM')", name="ck_precios_medicamentos_canal_mercado"),
        CheckConstraint("regimen_precios IN (1, 2, 3)", name="ck_precios_medicamentos_regimen_precios"),
    )

    # -----------------------------------------------------------------------
    # Clave primaria interna y FK al catálogo CUM
    # -----------------------------------------------------------------------
    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    # Llave lógica hacia el catálogo INVIMA – mismo formato que MedicamentoCUM.id_cum
    # (ej. "123456-01").  Sin FK a nivel de BD para permitir precios SISMED de CUMs
    # históricos o no incluidos aún en el catálogo activo de INVIMA.
    id_cum: str = Field(
        sa_column=Column(
            String,
            nullable=False,
            index=False,  # cubierto por ix_precios_medicamentos_id_cum
        )
    )

    # -----------------------------------------------------------------------
    # Control de precios regulados (Estándar CNPMDM / datos.gov.co)
    # -----------------------------------------------------------------------

    # 1 = Libertad vigilada  2 = Libertad regulada  3 = Control directo
    regimen_precios: int | None = Field(
        default=None,
        sa_column=Column(Integer, nullable=True),
    )

    # Precio máximo de venta asignado por la norma
    precio_regulado_maximo: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 4), nullable=True),
    )

    # Ej. "Circular 013 de 2022"
    acto_administrativo_precio: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )

    # -----------------------------------------------------------------------
    # Precios de mercado SISMED
    # -----------------------------------------------------------------------

    # 'INS' = Institucional  |  'COM' = Comercial
    canal_mercado: str = Field(
        sa_column=Column(String(3), nullable=False),
    )

    precio_sismed_minimo: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 4), nullable=True),
    )

    precio_sismed_maximo: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 4), nullable=True),
    )

    activo: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true", index=True))

    # -----------------------------------------------------------------------
    # Auditoría
    # -----------------------------------------------------------------------
    ultima_actualizacion: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class PrecioReguladoCNPMDM(SQLModel, table=True):
    """
    Precios máximos de venta fijados por la Comisión Nacional de Precios
    de Medicamentos y Dispositivos Médicos (CNPMDM) del Ministerio de Salud.

    La fuente es el 'Anexo Técnico' publicado con cada Circular de Precios.
    El campo id_cum es la llave lógica hacia medicamentos_cum (mismo formato
    "expediente-NN").  No se define FK a nivel de BD para permitir precios
    de CUMs históricos o aún no sincronizados en el catálogo activo.

    Referencia: Circular Única de Precios CNPMDM.
    """

    __tablename__ = "precios_regulados_cnpmdm"

    # PK: id_cum es 1:1 con esta tabla — cada CUM tiene un único precio máximo
    # fijado por la circular vigente.
    id_cum: str = Field(
        sa_column=Column(String, primary_key=True)
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        )
    )

    # Precio máximo de venta al público (PVP) expresado en pesos colombianos.
    precio_maximo_venta: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(14, 4), nullable=True),
    )

    activo: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, server_default="true", index=True))

    # Identificador de la circular de origen, ej. "Circular 013 de 2022".
    circular_origen: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )

    # Fecha de carga/actualización del registro en la BD.
    ultima_actualizacion: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
