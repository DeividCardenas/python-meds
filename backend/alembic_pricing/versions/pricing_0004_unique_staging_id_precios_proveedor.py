"""Add UNIQUE constraint on precios_proveedor.staging_id to prevent duplicate publishes

Revision ID: pricing_0004
Revises: pricing_0003
Create Date: 2026-03-03 00:00:00.000000

Adds a unique constraint on ``precios_proveedor.staging_id`` so that the DB
itself rejects any attempt to insert the same staging row twice, complementing
the application-level guard added in publicar_precios_aprobados().
"""

from __future__ import annotations

from alembic import op


revision = "pricing_0004"
down_revision = "pricing_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove duplicate rows first (in case re-publish happened before this migration)
    op.execute("""
        DELETE FROM precios_proveedor
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (PARTITION BY staging_id ORDER BY fecha_publicacion DESC) AS rn
                FROM precios_proveedor
            ) sub
            WHERE rn > 1
        )
    """)
    # Drop the plain index that already existed and replace with unique index
    op.drop_index("ix_precios_proveedor_staging_id", table_name="precios_proveedor")
    op.create_index(
        "ix_precios_proveedor_staging_id",
        "precios_proveedor",
        ["staging_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_precios_proveedor_staging_id", table_name="precios_proveedor")
    op.create_index(
        "ix_precios_proveedor_staging_id",
        "precios_proveedor",
        ["staging_id"],
        unique=False,
    )
