"""drop cost fields and add cum_sync_log table

Revision ID: 20260225_0006
Revises: 20260224_0005
Create Date: 2026-02-25 22:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260225_0006"
down_revision = "20260224_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Objective 1: drop cost/pricing columns from medicamentos
    op.drop_column("medicamentos", "precio_unitario")
    op.drop_column("medicamentos", "precio_empaque")
    op.drop_column("medicamentos", "es_regulado")
    op.drop_column("medicamentos", "precio_maximo_regulado")

    # Objective 2: create cum_sync_log table for Smart Sync state tracking
    op.create_table(
        "cum_sync_log",
        sa.Column("fuente", sa.String(), nullable=False),
        sa.Column("rows_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultima_sincronizacion", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("fuente"),
    )


def downgrade() -> None:
    op.drop_table("cum_sync_log")

    op.add_column("medicamentos", sa.Column("precio_unitario", sa.Float(), nullable=True))
    op.add_column("medicamentos", sa.Column("precio_empaque", sa.Float(), nullable=True))
    op.add_column(
        "medicamentos",
        sa.Column("es_regulado", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("medicamentos", sa.Column("precio_maximo_regulado", sa.Float(), nullable=True))
    op.alter_column("medicamentos", "es_regulado", server_default=None)
