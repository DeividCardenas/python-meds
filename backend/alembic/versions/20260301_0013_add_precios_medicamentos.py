"""Add precios_medicamentos table

Revision ID: 20260301_0013
Revises: 20260227_0012
Create Date: 2026-03-01 00:00:00.000000

Descripcion:
    Crea la tabla precios_medicamentos para almacenar los precios regulados y
    de mercado (SISMED) de los medicamentos, cumpliendo con el Estándar de
    Datos de Medicamentos de Uso Humano en Colombia (CNPMDM).

    Estructura:
    -----------
    - id                        UUID PK interno
    - id_cum                    VARCHAR NOT NULL  FK → medicamentos_cum.id_cum
                                (ON DELETE CASCADE: al eliminar un CUM se limpian
                                 sus precios automáticamente)
    - canal_mercado             VARCHAR(3) NOT NULL  'INS' | 'COM'

    Control de Precios Regulados (CNPMDM):
    - regimen_precios           INTEGER NULL   1=Libertad vigilada  2=Libertad regulada  3=Control directo
    - precio_regulado_maximo    NUMERIC(14,4) NULL
    - acto_administrativo_precio VARCHAR NULL  ej. "Circular 013 de 2022"

    Precios de Mercado (SISMED – datos.gov.co resource 3he6-m866):
    - precio_sismed_minimo      NUMERIC(14,4) NULL
    - precio_sismed_maximo      NUMERIC(14,4) NULL

    Auditoría:
    - ultima_actualizacion      TIMESTAMPTZ NULL

    Restricciones:
    - uq_precio_cum_canal       UNIQUE (id_cum, canal_mercado)
    - ix_precios_medicamentos_id_cum  INDEX (id_cum)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260301_0013"
down_revision = "20260227_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "precios_medicamentos",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "id_cum",
            sa.String(),
            sa.ForeignKey(
                "medicamentos_cum.id_cum",
                ondelete="CASCADE",
                name="fk_precios_medicamentos_id_cum",
            ),
            nullable=False,
        ),
        sa.Column("canal_mercado", sa.String(3), nullable=False),
        # Precios regulados
        sa.Column("regimen_precios", sa.Integer(), nullable=True),
        sa.Column("precio_regulado_maximo", sa.Numeric(14, 4), nullable=True),
        sa.Column("acto_administrativo_precio", sa.String(), nullable=True),
        # Precios SISMED
        sa.Column("precio_sismed_minimo", sa.Numeric(14, 4), nullable=True),
        sa.Column("precio_sismed_maximo", sa.Numeric(14, 4), nullable=True),
        # Auditoría
        sa.Column("ultima_actualizacion", sa.DateTime(timezone=True), nullable=True),
    )

    # Unique constraint que garantiza un único registro por (CUM, canal)
    op.create_unique_constraint(
        "uq_precio_cum_canal",
        "precios_medicamentos",
        ["id_cum", "canal_mercado"],
    )

    # Índice de acceso rápido por CUM
    op.create_index(
        "ix_precios_medicamentos_id_cum",
        "precios_medicamentos",
        ["id_cum"],
    )


def downgrade() -> None:
    op.drop_index("ix_precios_medicamentos_id_cum", table_name="precios_medicamentos")
    op.drop_constraint(
        "uq_precio_cum_canal",
        "precios_medicamentos",
        type_="unique",
    )
    op.drop_table("precios_medicamentos")
