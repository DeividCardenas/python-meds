"""Add cotizaciones_lote table for hospital bulk-quoting jobs

Revision ID: pricing_0003
Revises: pricing_0002
Create Date: 2026-03-01 00:00:00.000000

Creates the ``cotizaciones_lote`` table in genhospi_pricing.
Each row represents one bulk-quotation job submitted by a hospital user.
The ``resultado`` JSONB column stores the full per-drug result list once
the Celery task completes.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "pricing_0003"
down_revision = "pricing_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cotizaciones_lote",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("hospital_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("resultado", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resumen", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        sa.Column("fecha_completado", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cotizaciones_lote_hospital_id", "cotizaciones_lote", ["hospital_id"])
    op.create_index("ix_cotizaciones_lote_status", "cotizaciones_lote", ["status"])


def downgrade() -> None:
    op.drop_index("ix_cotizaciones_lote_status", table_name="cotizaciones_lote")
    op.drop_index("ix_cotizaciones_lote_hospital_id", table_name="cotizaciones_lote")
    op.drop_table("cotizaciones_lote")
