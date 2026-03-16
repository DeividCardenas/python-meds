"""Update ON DELETE behavior for pricing foreign keys

Revision ID: pricing_0007
Revises: pricing_0006
Create Date: 2026-03-16 13:30:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "pricing_0007"
down_revision = "pricing_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "proveedor_aliases_proveedor_id_fkey",
        "proveedor_aliases",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "proveedor_aliases_proveedor_id_fkey",
        "proveedor_aliases",
        "proveedores",
        ["proveedor_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "proveedor_archivos_proveedor_id_fkey",
        "proveedor_archivos",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "proveedor_archivos_proveedor_id_fkey",
        "proveedor_archivos",
        "proveedores",
        ["proveedor_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "staging_precios_proveedor_archivo_id_fkey",
        "staging_precios_proveedor",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "staging_precios_proveedor_archivo_id_fkey",
        "staging_precios_proveedor",
        "proveedor_archivos",
        ["archivo_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "precios_proveedor_archivo_id_fkey",
        "precios_proveedor",
        type_="foreignkey",
    )
    op.alter_column(
        "precios_proveedor",
        "archivo_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.create_foreign_key(
        "precios_proveedor_archivo_id_fkey",
        "precios_proveedor",
        "proveedor_archivos",
        ["archivo_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "precios_proveedor_proveedor_id_fkey",
        "precios_proveedor",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "precios_proveedor_proveedor_id_fkey",
        "precios_proveedor",
        "proveedores",
        ["proveedor_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "precios_proveedor_proveedor_id_fkey",
        "precios_proveedor",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "precios_proveedor_proveedor_id_fkey",
        "precios_proveedor",
        "proveedores",
        ["proveedor_id"],
        ["id"],
    )

    op.drop_constraint(
        "precios_proveedor_archivo_id_fkey",
        "precios_proveedor",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "precios_proveedor_archivo_id_fkey",
        "precios_proveedor",
        "proveedor_archivos",
        ["archivo_id"],
        ["id"],
    )
    op.execute(
        """
        UPDATE precios_proveedor AS pp
        SET archivo_id = spp.archivo_id
        FROM staging_precios_proveedor AS spp
        WHERE pp.archivo_id IS NULL
          AND pp.staging_id = spp.id
          AND spp.archivo_id IS NOT NULL
        """
    )
    op.execute("DELETE FROM precios_proveedor WHERE archivo_id IS NULL")
    op.alter_column(
        "precios_proveedor",
        "archivo_id",
        existing_type=sa.UUID(),
        nullable=False,
    )

    op.drop_constraint(
        "staging_precios_proveedor_archivo_id_fkey",
        "staging_precios_proveedor",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "staging_precios_proveedor_archivo_id_fkey",
        "staging_precios_proveedor",
        "proveedor_archivos",
        ["archivo_id"],
        ["id"],
    )

    op.drop_constraint(
        "proveedor_archivos_proveedor_id_fkey",
        "proveedor_archivos",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "proveedor_archivos_proveedor_id_fkey",
        "proveedor_archivos",
        "proveedores",
        ["proveedor_id"],
        ["id"],
    )

    op.drop_constraint(
        "proveedor_aliases_proveedor_id_fkey",
        "proveedor_aliases",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "proveedor_aliases_proveedor_id_fkey",
        "proveedor_aliases",
        "proveedores",
        ["proveedor_id"],
        ["id"],
    )
