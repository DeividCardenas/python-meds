"""Add created_at and updated_at timestamp columns to pricing tables

Revision ID: pricing_0008
Revises: pricing_0007
Create Date: 2026-03-16 16:31:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "pricing_0008"
down_revision = "pricing_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proveedores",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "proveedores",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "staging_precios_proveedor",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "staging_precios_proveedor",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "precios_proveedor",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "precios_proveedor",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("precios_proveedor", "updated_at")
    op.drop_column("precios_proveedor", "created_at")

    op.drop_column("staging_precios_proveedor", "updated_at")
    op.drop_column("staging_precios_proveedor", "created_at")

    op.drop_column("proveedores", "updated_at")
    op.drop_column("proveedores", "created_at")
