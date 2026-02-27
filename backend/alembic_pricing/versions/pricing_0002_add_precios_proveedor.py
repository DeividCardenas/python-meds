"""Add precios_proveedor production table

Revision ID: pricing_0002
Revises: pricing_0001
Create Date: 2026-02-27 22:00:00.000000

Creates the ``precios_proveedor`` table in genhospi_pricing.
This is the *production* destination for approved supplier prices that have
been promoted from ``staging_precios_proveedor`` via the Publish workflow.

Schema mirrors the staging table's financial and validity columns but:
  - cum_code is NOT NULL (only approved rows with a resolved CUM reach here)
  - staging_id links back to the originating staging row (soft reference)
  - fecha_publicacion records when the row was promoted to production
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "pricing_0002"
down_revision = "pricing_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "precios_proveedor",
        sa.Column("id", sa.UUID(), nullable=False),
        # Traceability back to the staging row (soft ref – no FK so staging can be purged)
        sa.Column("staging_id", sa.UUID(), nullable=False),
        # FK to the upload batch
        sa.Column("archivo_id", sa.UUID(), nullable=False),
        # Nullable FK to the supplier (batch may not have a detected supplier)
        sa.Column("proveedor_id", sa.UUID(), nullable=True),
        # CUM code is mandatory in production
        sa.Column("cum_code", sa.String(), nullable=False),
        # Soft cross-DB reference to genhospi_catalog.medicamentos.id
        sa.Column("medicamento_id", sa.UUID(), nullable=True),
        # --- Financial columns ---
        sa.Column("precio_unitario", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("precio_unidad", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("precio_presentacion", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("porcentaje_iva", sa.Numeric(precision=5, scale=4), nullable=True),
        # --- Validity dates ---
        sa.Column("vigente_desde", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column(
            "fecha_vigencia_indefinida",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # --- Confidence score ---
        sa.Column("confianza_score", sa.Numeric(precision=5, scale=4), nullable=True),
        # --- Audit ---
        sa.Column("fecha_publicacion", sa.DateTime(timezone=True), nullable=False),
        # --- Constraints ---
        sa.ForeignKeyConstraint(["archivo_id"], ["proveedor_archivos.id"]),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_precios_proveedor_staging_id"),
        "precios_proveedor",
        ["staging_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precios_proveedor_archivo_id"),
        "precios_proveedor",
        ["archivo_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precios_proveedor_cum_code"),
        "precios_proveedor",
        ["cum_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_precios_proveedor_proveedor_id"),
        "precios_proveedor",
        ["proveedor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_precios_proveedor_proveedor_id"), table_name="precios_proveedor")
    op.drop_index(op.f("ix_precios_proveedor_cum_code"), table_name="precios_proveedor")
    op.drop_index(op.f("ix_precios_proveedor_archivo_id"), table_name="precios_proveedor")
    op.drop_index(op.f("ix_precios_proveedor_staging_id"), table_name="precios_proveedor")
    op.drop_table("precios_proveedor")
