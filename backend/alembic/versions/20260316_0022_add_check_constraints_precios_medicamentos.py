"""Add CHECK constraints on precios_medicamentos

Revision ID: 20260316_0022
Revises: 20260316_0021
Create Date: 2026-03-16 00:45:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0022"
down_revision = "20260316_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_precios_medicamentos_canal_mercado",
        "precios_medicamentos",
        "canal_mercado IN ('INS', 'COM')",
    )
    op.create_check_constraint(
        "ck_precios_medicamentos_regimen_precios",
        "precios_medicamentos",
        "regimen_precios IN (1, 2, 3)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_precios_medicamentos_regimen_precios",
        "precios_medicamentos",
        type_="check",
    )
    op.drop_constraint(
        "ck_precios_medicamentos_canal_mercado",
        "precios_medicamentos",
        type_="check",
    )
