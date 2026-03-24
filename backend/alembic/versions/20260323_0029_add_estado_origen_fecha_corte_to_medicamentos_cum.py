"""Add estado_origen and fecha_corte_dato to medicamentos_cum.

Revision ID: 20260323_0029
Revises: add_medicamento_fields
Create Date: 2026-03-23

"""

from alembic import op
import sqlalchemy as sa


revision = "20260323_0029"
down_revision = "add_medicamento_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicamentos_cum", sa.Column("estado_origen", sa.String(), nullable=True))
    op.add_column(
        "medicamentos_cum",
        sa.Column("fecha_corte_dato", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_medicamentos_cum_estado_origen",
        "medicamentos_cum",
        ["estado_origen"],
        unique=False,
    )
    op.create_index(
        "ix_medicamentos_cum_fecha_corte_dato",
        "medicamentos_cum",
        ["fecha_corte_dato"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_medicamentos_cum_fecha_corte_dato", table_name="medicamentos_cum")
    op.drop_index("ix_medicamentos_cum_estado_origen", table_name="medicamentos_cum")

    op.drop_column("medicamentos_cum", "fecha_corte_dato")
    op.drop_column("medicamentos_cum", "estado_origen")
