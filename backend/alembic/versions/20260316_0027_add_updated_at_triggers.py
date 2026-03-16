"""Add updated_at triggers for catalog tables

Revision ID: 20260316_0027
Revises: 20260316_0026
Create Date: 2026-03-16 19:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0027"
down_revision = "20260316_0026"
branch_labels = None
depends_on = None


TABLES = (
    "medicamentos",
    "precios_referencia",
    "medicamentos_cum",
    "precios_medicamentos",
    "precios_regulados_cnpmdm",
    "drug_synonym_dict",
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
