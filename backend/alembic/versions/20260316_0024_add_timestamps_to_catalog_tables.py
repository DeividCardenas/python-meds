"""Add created_at and updated_at timestamp columns to catalog tables

Revision ID: 20260316_0024
Revises: 20260316_0023
Create Date: 2026-03-16 16:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260316_0024"
down_revision = "20260316_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medicamentos",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "medicamentos",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "precios_referencia",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "precios_referencia",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "medicamentos_cum",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "medicamentos_cum",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "precios_medicamentos",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "precios_medicamentos",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.add_column(
        "precios_regulados_cnpmdm",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "precios_regulados_cnpmdm",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.alter_column(
        "drug_synonym_dict",
        "created_at",
        existing_type=sa.DateTime(timezone=False),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.func.now(),
    )
    op.add_column(
        "drug_synonym_dict",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_column("drug_synonym_dict", "updated_at")
    op.alter_column(
        "drug_synonym_dict",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(timezone=False),
        existing_nullable=False,
        server_default=sa.text("NOW()"),
    )

    op.drop_column("precios_regulados_cnpmdm", "updated_at")
    op.drop_column("precios_regulados_cnpmdm", "created_at")

    op.drop_column("precios_medicamentos", "updated_at")
    op.drop_column("precios_medicamentos", "created_at")

    op.drop_column("medicamentos_cum", "updated_at")
    op.drop_column("medicamentos_cum", "created_at")

    op.drop_column("precios_referencia", "updated_at")
    op.drop_column("precios_referencia", "created_at")

    op.drop_column("medicamentos", "updated_at")
    op.drop_column("medicamentos", "created_at")
