"""Update ON DELETE behavior for precios_referencia.medicamento_id

Revision ID: 20260316_0023
Revises: 20260316_0022
Create Date: 2026-03-16 13:30:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0023"
down_revision = "20260316_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "precios_referencia_medicamento_id_fkey",
        "precios_referencia",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "precios_referencia_medicamento_id_fkey",
        "precios_referencia",
        "medicamentos",
        ["medicamento_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "precios_referencia_medicamento_id_fkey",
        "precios_referencia",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "precios_referencia_medicamento_id_fkey",
        "precios_referencia",
        "medicamentos",
        ["medicamento_id"],
        ["id"],
    )
