"""Alter precio_maximo_venta from FLOAT to NUMERIC(14,4)

Revision ID: 20260316_0020
Revises: 20260313_0019
Create Date: 2026-03-16 00:00:00.000000

Descripción
-----------
El campo precio_maximo_venta en precios_regulados_cnpmdm se cambia de
DOUBLE PRECISION (FLOAT) a NUMERIC(14,4) para alinear la precisión con
las demás tablas de precios.

Se usa USING precio_maximo_venta::numeric(14,4) para convertir los datos
existentes.
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0020"
down_revision = "20260313_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE precios_regulados_cnpmdm
        ALTER COLUMN precio_maximo_venta TYPE numeric(14,4)
        USING precio_maximo_venta::numeric(14,4)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE precios_regulados_cnpmdm
        ALTER COLUMN precio_maximo_venta TYPE double precision
        USING precio_maximo_venta::double precision
        """
    )
