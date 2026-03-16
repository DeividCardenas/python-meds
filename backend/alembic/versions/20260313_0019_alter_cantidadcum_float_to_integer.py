"""Alter cantidadcum from FLOAT to INTEGER

Revision ID: 20260313_0019
Revises: 20260303_0018
Create Date: 2026-03-13 00:00:00.000000

Descripción
-----------
El campo cantidadcum en medicamentos_cum siempre almacena valores enteros
(cantidad de CUMs en un expediente). Se cambia de DOUBLE PRECISION (FLOAT)
a INTEGER para reflejar el tipo real del dato y evitar problemas de
precisión de punto flotante.

Se usa USING cantidadcum::integer para convertir los valores existentes.
"""

from __future__ import annotations

from alembic import op


revision = "20260313_0019"
down_revision = "20260303_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE medicamentos_cum
        ALTER COLUMN cantidadcum TYPE integer
        USING cantidadcum::integer
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE medicamentos_cum
        ALTER COLUMN cantidadcum TYPE double precision
        USING cantidadcum::double precision
        """
    )
