"""add trigram gin index for nombre_limpio

Revision ID: 20260219_0003
Revises: 20260219_0002
Create Date: 2026-02-19 14:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260219_0003"
down_revision = "20260219_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.create_index(
        "ix_medicamentos_nombre_gin",
        "medicamentos",
        [sa.text("nombre_limpio gin_trgm_ops")],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_medicamentos_nombre_gin", table_name="medicamentos")
