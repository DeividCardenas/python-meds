"""add costos y regulacion fields

Revision ID: 20260219_0004
Revises: 20260219_0003
Create Date: 2026-02-19 15:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260219_0004"
down_revision = "20260219_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicamentos", sa.Column("precio_unitario", sa.Float(), nullable=True))
    op.add_column("medicamentos", sa.Column("precio_empaque", sa.Float(), nullable=True))
    op.add_column(
        "medicamentos",
        sa.Column("es_regulado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("medicamentos", sa.Column("precio_maximo_regulado", sa.Float(), nullable=True))
    op.alter_column("medicamentos", "es_regulado", server_default=None)


def downgrade() -> None:
    op.drop_column("medicamentos", "precio_maximo_regulado")
    op.drop_column("medicamentos", "es_regulado")
    op.drop_column("medicamentos", "precio_empaque")
    op.drop_column("medicamentos", "precio_unitario")
