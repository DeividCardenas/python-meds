"""Add activo column and B-tree indexes to catalog pricing tables

Revision ID: 20260316_0026
Revises: 20260316_0025
Create Date: 2026-03-16 18:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260316_0026"
down_revision = "20260316_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "precios_referencia",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_precios_referencia_activo",
        "precios_referencia",
        ["activo"],
        unique=False,
    )

    op.add_column(
        "precios_medicamentos",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_precios_medicamentos_activo",
        "precios_medicamentos",
        ["activo"],
        unique=False,
    )

    op.add_column(
        "precios_regulados_cnpmdm",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_precios_regulados_cnpmdm_activo",
        "precios_regulados_cnpmdm",
        ["activo"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_precios_regulados_cnpmdm_activo",
        table_name="precios_regulados_cnpmdm",
    )
    op.drop_column("precios_regulados_cnpmdm", "activo")

    op.drop_index(
        "ix_precios_medicamentos_activo",
        table_name="precios_medicamentos",
    )
    op.drop_column("precios_medicamentos", "activo")

    op.drop_index(
        "ix_precios_referencia_activo",
        table_name="precios_referencia",
    )
    op.drop_column("precios_referencia", "activo")
