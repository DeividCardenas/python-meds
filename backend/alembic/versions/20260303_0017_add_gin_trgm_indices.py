"""Add GIN pg_trgm indices on principio_activo and forma_farmaceutica

Revision ID: 20260303_0017
Revises: 20260303_0016
Create Date: 2026-03-03 22:00:00.000000

Descripción
-----------
El motor de matching (Stage 1 Pass B y Stage 2) ejecuta consultas con
similarity(), word_similarity() y LIKE sobre las columnas principio_activo
y forma_farmaceutica.

El índice B-tree previo (ix_medicamentos_principio_activo) es INÚTIL para
operadores de trigramas — sólo acelera igualdad exacta.

Esta migración:
  1. Agrega ix_medicamentos_principio_activo_gin  — GIN trgm en
     lower(coalesce(principio_activo, ''))
     Acelera: similarity(), word_similarity(), operadores %, <%

  2. Agrega ix_medicamentos_forma_farmaceutica_gin — GIN trgm en
     lower(coalesce(forma_farmaceutica, ''))
     Acelera: LIKE '%tableta%' y similares en Stage 1B

El índice B-tree existente se MANTIENE porque Stage 1 Pass A usa
igualdad exacta (lower(PA) = inn_query), donde B-tree es más eficiente.

Impacto esperado: Stage 2 pasa de sequential scan 53K filas → index seek.
"""

from __future__ import annotations

from alembic import op


revision = "20260303_0017"
down_revision = "20260303_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pg_trgm extension is available (no-op if already installed).
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # GIN index for similarity() / word_similarity() / % / <% operators
    # on lower(coalesce(principio_activo, '')).
    # Stage 1 Pass B uses <%  (word_similarity operator).
    # Stage 2 fuzzy uses %   (similarity operator) and <% (word_similarity).
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_principio_activo_gin
        ON medicamentos
        USING GIN (lower(coalesce(principio_activo, '')) gin_trgm_ops)
        """
    )

    # GIN index for LIKE '%canonical_form%' on lower(coalesce(forma_farmaceutica, '')).
    # Stage 1 Pass B filters by forma using a CONTAINS / LIKE pattern.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_forma_farmaceutica_gin
        ON medicamentos
        USING GIN (lower(coalesce(forma_farmaceutica, '')) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_principio_activo_gin")
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_forma_farmaceutica_gin")
