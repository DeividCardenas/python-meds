"""Add ProveedorAlias table, confianza_score and fecha_vigencia_indefinida columns

Revision ID: 20260227_0008
Revises: 20260227_0007
Create Date: 2026-02-27 17:00:00.000000

Pillars implemented:
  * Pillar 2 – Supplier auto-identification: ``proveedor_aliases`` table stores
    filename-regex and header-fingerprint patterns per supplier.
  * Pillar 3 – Missing-data protocol: ``fecha_vigencia_indefinida`` boolean on
    ``staging_precios_proveedor`` flags rows where the supplier omitted dates.
  * Pillar 4 – Confidence scoring: ``confianza_score`` NUMERIC(5,4) on
    ``staging_precios_proveedor`` stores the Polars + pg_trgm match confidence.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "20260227_0008"
down_revision = "20260227_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Pillar 2 – proveedor_aliases
    # ------------------------------------------------------------------
    op.create_table(
        "proveedor_aliases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proveedor_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("alias_patron", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_proveedor_aliases_proveedor_id"),
        "proveedor_aliases",
        ["proveedor_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # Pillar 3 – fecha_vigencia_indefinida
    # ------------------------------------------------------------------
    op.add_column(
        "staging_precios_proveedor",
        sa.Column(
            "fecha_vigencia_indefinida",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # ------------------------------------------------------------------
    # Pillar 4 – confianza_score
    # ------------------------------------------------------------------
    op.add_column(
        "staging_precios_proveedor",
        sa.Column("confianza_score", sa.Numeric(precision=5, scale=4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("staging_precios_proveedor", "confianza_score")
    op.drop_column("staging_precios_proveedor", "fecha_vigencia_indefinida")
    op.drop_index(op.f("ix_proveedor_aliases_proveedor_id"), table_name="proveedor_aliases")
    op.drop_table("proveedor_aliases")
