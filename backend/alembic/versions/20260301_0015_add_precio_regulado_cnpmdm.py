"""Add precios_regulados_cnpmdm table

Revision ID: 20260301_0015
Revises: 20260301_0014
Create Date: 2026-03-01 22:00:00.000000

Descripcion:
    Crea la tabla precios_regulados_cnpmdm para almacenar los precios
    máximos de venta fijados por la CNPMDM (Comisión Nacional de Precios
    de Medicamentos y Dispositivos Médicos) del Ministerio de Salud.

    La fuente es el Anexo Técnico publicado con cada Circular de Precios.

    Estructura:
    - id_cum              VARCHAR  PK  (llave lógica, formato "expediente-NN")
    - precio_maximo_venta FLOAT        PVP fijado por la circular
    - circular_origen     VARCHAR      Ej. "Circular 013 de 2022"
    - ultima_actualizacion TIMESTAMPTZ  Fecha de la última carga
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260301_0015"
down_revision = "20260301_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "precios_regulados_cnpmdm",
        sa.Column("id_cum", sa.String(), primary_key=True, nullable=False),
        sa.Column("precio_maximo_venta", sa.Float(), nullable=True),
        sa.Column("circular_origen", sa.String(), nullable=True),
        sa.Column(
            "ultima_actualizacion",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_precios_regulados_cnpmdm_id_cum",
        "precios_regulados_cnpmdm",
        ["id_cum"],
    )


def downgrade() -> None:
    op.drop_index("ix_precios_regulados_cnpmdm_id_cum", table_name="precios_regulados_cnpmdm")
    op.drop_table("precios_regulados_cnpmdm")
