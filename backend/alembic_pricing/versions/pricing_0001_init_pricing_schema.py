"""Initial schema for genhospi_pricing database

Revision ID: pricing_0001
Revises:
Create Date: 2026-02-27 20:00:00.000000

Creates the supplier pricing pipeline tables in genhospi_pricing:
  - proveedores
  - proveedor_aliases
  - proveedor_archivos
  - staging_precios_proveedor

NOTE: staging_precios_proveedor.medicamento_id is a soft (application-level)
reference to medicamentos.id in genhospi_catalog. No DB-level FK is created
because PostgreSQL does not support cross-database foreign keys.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "pricing_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm for fuzzy similarity search used by the CUM matcher
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # proveedores
    # ------------------------------------------------------------------
    op.create_table(
        "proveedores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("codigo", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proveedores_codigo"), "proveedores", ["codigo"], unique=False)

    # ------------------------------------------------------------------
    # proveedor_aliases
    # ------------------------------------------------------------------
    op.create_table(
        "proveedor_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proveedor_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("alias_patron", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_proveedor_aliases_proveedor_id"),
        "proveedor_aliases",
        ["proveedor_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # proveedor_archivos
    # ------------------------------------------------------------------
    op.create_table(
        "proveedor_archivos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proveedor_id", sa.UUID(), nullable=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("columnas_detectadas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("mapeo_columnas", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fecha_carga", sa.DateTime(timezone=True), nullable=False),
        sa.Column("errores_log", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_proveedor_archivos_proveedor_id"),
        "proveedor_archivos",
        ["proveedor_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # staging_precios_proveedor
    # NO FK to medicamentos.id — that table lives in genhospi_catalog.
    # The application enforces the logical reference.
    # ------------------------------------------------------------------
    op.create_table(
        "staging_precios_proveedor",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("archivo_id", sa.UUID(), nullable=False),
        sa.Column("fila_numero", sa.Integer(), nullable=False),
        sa.Column("cum_code", sa.String(), nullable=True),
        sa.Column("precio_unitario", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("precio_unidad", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("precio_presentacion", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("porcentaje_iva", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("vigente_desde", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column("descripcion_raw", sa.String(), nullable=True),
        sa.Column("estado_homologacion", sa.String(), nullable=False),
        # medicamento_id: soft reference to genhospi_catalog.public.medicamentos
        sa.Column("medicamento_id", sa.UUID(), nullable=True),
        sa.Column("fecha_vigencia_indefinida", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confianza_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("datos_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sugerencias_cum", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["archivo_id"], ["proveedor_archivos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_staging_precios_proveedor_archivo_id"),
        "staging_precios_proveedor",
        ["archivo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staging_precios_proveedor_cum_code"),
        "staging_precios_proveedor",
        ["cum_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staging_precios_proveedor_estado_homologacion"),
        "staging_precios_proveedor",
        ["estado_homologacion"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_staging_precios_proveedor_estado_homologacion"),
        table_name="staging_precios_proveedor",
    )
    op.drop_index(
        op.f("ix_staging_precios_proveedor_cum_code"),
        table_name="staging_precios_proveedor",
    )
    op.drop_index(
        op.f("ix_staging_precios_proveedor_archivo_id"),
        table_name="staging_precios_proveedor",
    )
    op.drop_table("staging_precios_proveedor")

    op.drop_index(op.f("ix_proveedor_archivos_proveedor_id"), table_name="proveedor_archivos")
    op.drop_table("proveedor_archivos")

    op.drop_index(op.f("ix_proveedor_aliases_proveedor_id"), table_name="proveedor_aliases")
    op.drop_table("proveedor_aliases")

    op.drop_index(op.f("ix_proveedores_codigo"), table_name="proveedores")
    op.drop_table("proveedores")
