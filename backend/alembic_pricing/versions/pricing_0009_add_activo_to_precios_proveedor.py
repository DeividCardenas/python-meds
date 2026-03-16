"""Add activo column and B-tree index to precios_proveedor

Revision ID: pricing_0009
Revises: pricing_0008
Create Date: 2026-03-16 18:10:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "pricing_0009"
down_revision = "pricing_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "precios_proveedor",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_precios_proveedor_activo",
        "precios_proveedor",
        ["activo"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_precios_proveedor_activo",
        table_name="precios_proveedor",
    )
    op.drop_column("precios_proveedor", "activo")
