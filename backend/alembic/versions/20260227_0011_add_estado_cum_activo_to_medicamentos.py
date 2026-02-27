"""Add estado_cum and activo columns to medicamentos

Revision ID: 20260227_0011
Revises: 20260227_0009
Create Date: 2026-02-27 20:00:00.000000

Descripcion:
    - estado_cum VARCHAR NULL: almacena el valor raw de medicamentos_cum.estadocum
      (ej. 'Vigente', 'Vencido', 'En Trámite', 'Inactivo').  Se actualiza
      automáticamente cada vez que se ejecuta la sincronización mensual del
      catálogo CUM desde la API Socrata de datos.gov.co.
    - activo BOOLEAN NOT NULL DEFAULT true: flag desnormalizado derivado de
      estado_cum.  True cuando estadocum es 'Vigente' o 'Activo'.  Los
      medicamentos sin id_cum (no vinculados al catálogo INVIMA) conservan
      activo=true para no romper la búsqueda existente.
    - Índice en medicamentos.activo para acelerar el filtro habitual
      (solo_activos=True) en buscar_medicamentos.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260227_0011"
down_revision = "20260227_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Estado raw del CUM (nullable: medicamentos sin id_cum lo tendrán NULL)
    op.add_column(
        "medicamentos",
        sa.Column("estado_cum", sa.String(), nullable=True),
    )

    # Flag booleano desnormalizado; default True para no romper registros existentes
    op.add_column(
        "medicamentos",
        sa.Column(
            "activo",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # Índice para acelerar búsquedas con filtro solo_activos
    op.create_index(
        "ix_medicamentos_activo",
        "medicamentos",
        ["activo"],
        unique=False,
    )

    # Sincronización inicial: propagar estadocum desde medicamentos_cum
    # usando el id_cum como clave de join.
    op.execute(
        sa.text("""
        UPDATE medicamentos m
        SET
            estado_cum = c.estadocum,
            activo     = lower(c.estadocum) IN ('vigente', 'activo')
        FROM medicamentos_cum c
        WHERE m.id_cum = c.id_cum
          AND m.id_cum IS NOT NULL
        """)
    )


def downgrade() -> None:
    op.drop_index("ix_medicamentos_activo", table_name="medicamentos")
    op.drop_column("medicamentos", "activo")
    op.drop_column("medicamentos", "estado_cum")
