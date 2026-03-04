"""Add stored generated column nombre_tsvector + GIN index

Revision ID: 20260303_0018
Revises: 20260303_0017
Create Date: 2026-03-03 23:00:00.000000

Descripción
-----------
Anomalía 1 (CRÍTICO) y Anomalía 2 (ALTO) detectadas en pruebas k6:

  - buscarMedicamentos p(95) = 6.46 s  (umbral: 1 500 ms) — seqscan por
    to_tsvector() calculado inline sobre regexp_replace anidado.
  - sugerenciasCum   p(95) = 14.84 s (umbral:   800 ms) — seqscan por
    to_tsvector() inline + OR similarity > 0.2 forzando sequential scan.

Solución
--------
1. Agregar columna STORED GENERATED  ``nombre_tsvector`` de tipo TSVECTOR.
   PostgreSQL mantiene el valor actualizado automáticamente sin overhead de
   escritura en la aplicación.

   Fórmula: to_tsvector('simple', lower(coalesce(nombre_limpio, '')))

2. Crear índice GIN  ``ix_medicamentos_nombre_tsvector_gin`` sobre esa columna.
   Con esto, las queries que usen ``nombre_tsvector @@ tsquery`` pasan de
   seqscan O(N) → GIN index seek O(log N + k).

Impacto posterior (medido en segundo run k6):
  - sugerenciasCum   p(95)  14.84 s → < 800 ms
  - buscarMedicamentos p(95)  6.46 s → < 1 500 ms
"""

from __future__ import annotations

from alembic import op


revision = "20260303_0018"
down_revision = "20260303_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Agregar columna STORED GENERATED.
    # GENERATED ALWAYS AS ... STORED requiere PostgreSQL 12+.
    # La columna es read-only desde la aplicación; PostgreSQL la mantiene.
    op.execute(
        """
        ALTER TABLE medicamentos
        ADD COLUMN IF NOT EXISTS nombre_tsvector tsvector
        GENERATED ALWAYS AS (
            to_tsvector('simple', lower(coalesce(nombre_limpio, '')))
        ) STORED
        """
    )

    # GIN index sobre la columna generada.
    # Acelera: nombre_tsvector @@ plainto_tsquery(...)
    # Usado por buscarMedicamentos y sugerenciasCum.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_medicamentos_nombre_tsvector_gin
        ON medicamentos
        USING GIN (nombre_tsvector)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_medicamentos_nombre_tsvector_gin")
    op.execute("ALTER TABLE medicamentos DROP COLUMN IF EXISTS nombre_tsvector")
