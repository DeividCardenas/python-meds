"""initial schema

Revision ID: 20260218_0001
Revises:
Create Date: 2026-02-18 16:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20260218_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "cargas_archivo",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("errores_log", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "medicamentos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nombre_limpio", sa.String(), nullable=False),
        sa.Column("embedding", Vector(dim=768), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_medicamentos_nombre_limpio"), "medicamentos", ["nombre_limpio"], unique=False)
    op.create_table(
        "precios_referencia",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("medicamento_id", sa.UUID(), nullable=False),
        sa.Column("empresa", sa.String(), nullable=False),
        sa.Column("precio", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("fu", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("vpc", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.ForeignKeyConstraint(["medicamento_id"], ["medicamentos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_precios_referencia_medicamento_id"), "precios_referencia", ["medicamento_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_precios_referencia_medicamento_id"), table_name="precios_referencia")
    op.drop_table("precios_referencia")
    op.drop_index(op.f("ix_medicamentos_nombre_limpio"), table_name="medicamentos")
    op.drop_table("medicamentos")
    op.drop_table("cargas_archivo")
