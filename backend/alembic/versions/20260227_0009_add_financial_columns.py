"""Add dedicated financial columns to staging_precios_proveedor

Revision ID: 20260227_0009
Revises: 20260227_0008
Create Date: 2026-02-27 18:00:00.000000

Adds three nullable columns to ``staging_precios_proveedor`` to capture the
variable pricing structure found across suppliers:

* ``precio_unidad``       – unit / minimum-dispensing price (e.g. Megalabs "Precio UMD")
* ``precio_presentacion`` – box / presentation price       (e.g. Megalabs "Precio Presentacion")
* ``porcentaje_iva``      – IVA as a fraction (0.19 for 19%, NULL when not provided)

Migration is non-destructive: all three columns are nullable with no server
default so existing rows remain untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260227_0009"
down_revision = "20260227_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "staging_precios_proveedor",
        sa.Column("precio_unidad", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "staging_precios_proveedor",
        sa.Column("precio_presentacion", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "staging_precios_proveedor",
        sa.Column("porcentaje_iva", sa.Numeric(precision=5, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("staging_precios_proveedor", "porcentaje_iva")
    op.drop_column("staging_precios_proveedor", "precio_presentacion")
    op.drop_column("staging_precios_proveedor", "precio_unidad")
