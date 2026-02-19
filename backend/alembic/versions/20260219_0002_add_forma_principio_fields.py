"""add forma farmaceutica and principio activo

Revision ID: 20260219_0002
Revises: 20260218_0001
Create Date: 2026-02-19 04:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260219_0002"
down_revision = "20260218_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicamentos", sa.Column("principio_activo", sa.String(), nullable=True))
    op.add_column("medicamentos", sa.Column("forma_farmaceutica", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("medicamentos", "forma_farmaceutica")
    op.drop_column("medicamentos", "principio_activo")
