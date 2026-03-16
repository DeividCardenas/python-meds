"""Add B-tree and GIN trgm indices to medicamentos_cum

Revision ID: 20260316_0021
Revises: 20260316_0020
Create Date: 2026-03-16 00:30:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "20260316_0021"
down_revision = "20260316_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_cum_registrosanitario
        ON medicamentos_cum (registrosanitario)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_cum_expediente
        ON medicamentos_cum (expediente)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_cum_principioactivo_gin
        ON medicamentos_cum
        USING GIN (lower(coalesce(principioactivo, '')) gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_cum_descripcioncomercial_gin
        ON medicamentos_cum
        USING GIN (lower(coalesce(descripcioncomercial, '')) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_cum_descripcioncomercial_gin")
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_cum_principioactivo_gin")
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_cum_expediente")
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_cum_registrosanitario")
    op.execute(
        """
        DO $$
        DECLARE trgm_index_count integer;
        BEGIN
            SELECT count(*)
            INTO trgm_index_count
            FROM pg_catalog.pg_index i
            JOIN pg_catalog.pg_opclass opc ON opc.oid = ANY (i.indclass)
            WHERE opc.opcname = 'gin_trgm_ops';

            IF trgm_index_count = 0 THEN
                EXECUTE 'DROP EXTENSION IF EXISTS pg_trgm';
            END IF;
        END
        $$;
        """
    )
