"""Add composite index for active-price lookups in precios_proveedor

Revision ID: pricing_0006
Revises: pricing_0005
Create Date: 2026-03-16 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "pricing_0006"
down_revision = "pricing_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_precios_proveedor_cum_code_proveedor_id_vigente_hasta",
        "precios_proveedor",
        ["cum_code", "proveedor_id", "vigente_hasta"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_precios_proveedor_cum_code_proveedor_id_vigente_hasta",
        table_name="precios_proveedor",
    )
