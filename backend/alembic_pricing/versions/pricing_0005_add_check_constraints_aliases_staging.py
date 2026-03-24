"""Add CHECK constraints on proveedor_aliases and staging_precios_proveedor

Revision ID: pricing_0005
Revises: pricing_0004
Create Date: 2026-03-16 00:45:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "pricing_0005"
down_revision = "pricing_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Normaliza datos legacy antes de imponer CHECK estricto.
    op.execute(
        """
        UPDATE staging_precios_proveedor
        SET estado_homologacion = UPPER(TRIM(estado_homologacion))
        """
    )
    op.execute(
        """
        UPDATE staging_precios_proveedor
        SET estado_homologacion = 'APROBADO'
        WHERE estado_homologacion = 'AUTO_APROBADO'
        """
    )
    op.execute(
        """
        UPDATE staging_precios_proveedor
        SET estado_homologacion = 'PENDIENTE'
        WHERE estado_homologacion NOT IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')
        """
    )

    op.create_check_constraint(
        "ck_staging_precios_proveedor_estado_homologacion",
        "staging_precios_proveedor",
        "estado_homologacion IN ('PENDIENTE', 'APROBADO', 'RECHAZADO')",
    )
    op.create_check_constraint(
        "ck_proveedor_aliases_tipo",
        "proveedor_aliases",
        "tipo IN ('filename', 'header')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_proveedor_aliases_tipo",
        "proveedor_aliases",
        type_="check",
    )
    op.drop_constraint(
        "ck_staging_precios_proveedor_estado_homologacion",
        "staging_precios_proveedor",
        type_="check",
    )
