"""Add FK from medicamentos.id_cum to medicamentos_cum.id_cum

Revision ID: 20260316_0025
Revises: 20260316_0024
Create Date: 2026-03-16 17:20:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260316_0025"
down_revision = "20260316_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    orphan_rows = bind.execute(
        sa.text(
            """
            SELECT m.id_cum
            FROM medicamentos AS m
            LEFT JOIN medicamentos_cum AS mc
                ON mc.id_cum = m.id_cum
            WHERE m.id_cum IS NOT NULL
              AND mc.id_cum IS NULL
            ORDER BY m.id_cum
            """
        )
    ).fetchall()

    if orphan_rows:
        orphan_values = [row[0] for row in orphan_rows]
        print(
            "Orphan medicamentos.id_cum values "
            "(not present in medicamentos_cum):"
        )
        for orphan_value in orphan_values:
            print(orphan_value)
        raise RuntimeError(
            "Cannot create FK medicamentos.id_cum -> "
            "medicamentos_cum.id_cum because orphan values exist."
        )

    op.create_foreign_key(
        "medicamentos_id_cum_fkey",
        "medicamentos",
        "medicamentos_cum",
        ["id_cum"],
        ["id_cum"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "medicamentos_id_cum_fkey",
        "medicamentos",
        type_="foreignkey",
    )
