"""add functional index on lower(principio_activo) for comparativaPrecios

Revision ID: 20260224_0005
Revises: 20260219_0004
Create Date: 2026-02-24 16:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260224_0005"
down_revision = "20260219_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_medicamentos_principio_activo",
        "medicamentos",
        [sa.text("lower(coalesce(principio_activo, ''))")],
        unique=False,
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_medicamentos_principio_activo", table_name="medicamentos")
