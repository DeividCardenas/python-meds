"""Move pricing pipeline tables out of genhospi_catalog

Revision ID: 20260227_0010
Revises: 7772da91e090
Create Date: 2026-02-27 21:00:00.000000

Drops the supplier pricing pipeline tables from genhospi_catalog.
These tables are now owned by genhospi_pricing (see alembic_pricing/).

Tables removed:
  - staging_precios_proveedor
  - proveedor_archivos
  - proveedor_aliases
  - proveedores
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260227_0010"
down_revision = "7772da91e090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop in reverse-FK order (only indexes that were actually created in catalog)
    op.drop_index("ix_staging_precios_proveedor_cum_code", table_name="staging_precios_proveedor")
    op.drop_index("ix_staging_precios_proveedor_archivo_id", table_name="staging_precios_proveedor")
    op.drop_table("staging_precios_proveedor")

    op.drop_index("ix_proveedor_archivos_proveedor_id", table_name="proveedor_archivos")
    op.drop_table("proveedor_archivos")

    op.drop_index("ix_proveedor_aliases_proveedor_id", table_name="proveedor_aliases")
    op.drop_table("proveedor_aliases")

    op.drop_index("ix_proveedores_codigo", table_name="proveedores")
    op.drop_table("proveedores")


def downgrade() -> None:
    # Recreate all four tables in catalog (for rollback only)
    op.create_table(
        "proveedores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("codigo", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proveedores_codigo"), "proveedores", ["codigo"], unique=False)

    op.create_table(
        "proveedor_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proveedor_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("alias_patron", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_proveedor_aliases_proveedor_id"), "proveedor_aliases", ["proveedor_id"], unique=False)

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
    op.create_index(op.f("ix_proveedor_archivos_proveedor_id"), "proveedor_archivos", ["proveedor_id"], unique=False)

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
        sa.Column("medicamento_id", sa.UUID(), nullable=True),
        sa.Column("fecha_vigencia_indefinida", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confianza_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("datos_raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sugerencias_cum", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["archivo_id"], ["proveedor_archivos.id"]),
        sa.ForeignKeyConstraint(["medicamento_id"], ["medicamentos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_staging_precios_proveedor_archivo_id"), "staging_precios_proveedor", ["archivo_id"], unique=False)
    op.create_index(op.f("ix_staging_precios_proveedor_cum_code"), "staging_precios_proveedor", ["cum_code"], unique=False)
