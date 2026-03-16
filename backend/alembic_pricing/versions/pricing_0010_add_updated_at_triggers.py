"""Add updated_at triggers for pricing tables

Revision ID: pricing_0010
Revises: pricing_0009
Create Date: 2026-03-16 19:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "pricing_0010"
down_revision = "pricing_0009"
branch_labels = None
depends_on = None


TABLES = (
    "proveedores",
    "staging_precios_proveedor",
    "precios_proveedor",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    for table in TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_set_updated_at_{table}
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at();
            """
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_set_updated_at_{table} ON {table};")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
