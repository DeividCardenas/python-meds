"""Drop FK constraint from precios_medicamentos.id_cum

Revision ID: 20260301_0014
Revises: 20260301_0013
Create Date: 2026-03-01 20:30:00.000000

Descripcion:
    Elimina la Foreign Key fk_precios_medicamentos_id_cum de la tabla
    precios_medicamentos.

    Motivación:
    El dataset SISMED (datos.gov.co/resource/3he6-m866) contiene registros
    históricos de precios de CUMs que pueden no estar presentes en el
    catálogo activo de INVIMA (medicamentos_cum).  La FK a nivel de BD
    impedía insertar estos precios generando ForeignKeyViolationError.

    El campo id_cum permanece como llave lógica (mismo formato "expediente-NN")
    y se sigue usando en JOINs con medicamentos_cum, pero sin que la BD
    rechace precios de CUMs históricos o aún no sincronizados.
"""

from __future__ import annotations

from alembic import op


revision = "20260301_0014"
down_revision = "20260301_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_precios_medicamentos_id_cum",
        "precios_medicamentos",
        type_="foreignkey",
    )


def downgrade() -> None:
    op.create_foreign_key(
        "fk_precios_medicamentos_id_cum",
        "precios_medicamentos",
        "medicamentos_cum",
        ["id_cum"],
        ["id_cum"],
        ondelete="CASCADE",
    )
