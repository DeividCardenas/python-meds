"""Add drug_synonym_dict table to catalog DB

Revision ID: 20260303_0016
Revises: 20260301_0015
Create Date: 2026-03-03 12:00:00.000000

Descripcion:
    Crea la tabla drug_synonym_dict para el diccionario de sinónimos
    hospital-scoped del matching engine.  Cada fila mapea un nombre
    libre de medicamento (raw_input) al CUM correspondiente, con contexto
    de hospital y confianza.

    La tabla es la clave del pre-stage O(1) en matching_engine.match_drug():
    si un nombre ya fue resuelto manualmente para ese hospital, se retorna
    directamente sin pasar por Stage 1 ni Stage 2.

    Índice único: (hospital_id, raw_input_normalized)
    → previene duplicados y acelera el lookup.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260303_0016"
down_revision = "20260301_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "drug_synonym_dict",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("hospital_id",          sa.String(), nullable=False),
        sa.Column("raw_input",            sa.String(), nullable=False),
        sa.Column("raw_input_normalized", sa.String(), nullable=False),
        sa.Column("cum_id",               sa.String(), nullable=False),
        sa.Column("medicamento_id",       sa.UUID(),   nullable=True),
        sa.Column(
            "resolved_by",
            sa.String(),
            nullable=False,
            server_default="HUMAN",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="1.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Unique lookup index: (hospital_id, raw_input_normalizado)
    op.create_index(
        "ix_drug_synonym_dict_hospital_raw",
        "drug_synonym_dict",
        ["hospital_id", "raw_input_normalized"],
        unique=True,
    )

    # Secondary index for CUM-based lookups
    op.create_index(
        "ix_drug_synonym_dict_cum_id",
        "drug_synonym_dict",
        ["cum_id"],
    )

    # Secondary index for hospital-scoped queries
    op.create_index(
        "ix_drug_synonym_dict_hospital_id",
        "drug_synonym_dict",
        ["hospital_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_drug_synonym_dict_hospital_id",  table_name="drug_synonym_dict")
    op.drop_index("ix_drug_synonym_dict_cum_id",        table_name="drug_synonym_dict")
    op.drop_index("ix_drug_synonym_dict_hospital_raw",  table_name="drug_synonym_dict")
    op.drop_table("drug_synonym_dict")
