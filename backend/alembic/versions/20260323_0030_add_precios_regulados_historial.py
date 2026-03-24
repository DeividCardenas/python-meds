"""Add versioned history table for CNPMDM regulated prices.

Revision ID: 20260323_0030
Revises: 20260323_0029
Create Date: 2026-03-23

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260323_0030"
down_revision = "20260323_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "precios_regulados_cnpmdm_historial",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id_cum", sa.String(), nullable=False),
        sa.Column("precio_maximo_venta", sa.Numeric(14, 4), nullable=False),
        sa.Column("circular_origen", sa.String(), nullable=True),
        sa.Column("fecha_inicio_vigencia", sa.Date(), nullable=False),
        sa.Column("fecha_fin_vigencia", sa.Date(), nullable=True),
        sa.Column("ultima_actualizacion", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_precios_regulados_cnpmdm_historial"),
        sa.UniqueConstraint(
            "id_cum",
            "circular_origen",
            "fecha_inicio_vigencia",
            name="uq_precio_regulado_historial_cum_circular_inicio",
        ),
    )

    op.create_index(
        "ix_precios_regulados_historial_id_cum",
        "precios_regulados_cnpmdm_historial",
        ["id_cum"],
        unique=False,
    )
    op.create_index(
        "ix_precios_regulados_historial_inicio",
        "precios_regulados_cnpmdm_historial",
        ["fecha_inicio_vigencia"],
        unique=False,
    )
    op.create_index(
        "ix_precios_regulados_historial_fin",
        "precios_regulados_cnpmdm_historial",
        ["fecha_fin_vigencia"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_precios_regulados_historial_fin", table_name="precios_regulados_cnpmdm_historial")
    op.drop_index("ix_precios_regulados_historial_inicio", table_name="precios_regulados_cnpmdm_historial")
    op.drop_index("ix_precios_regulados_historial_id_cum", table_name="precios_regulados_cnpmdm_historial")
    op.drop_table("precios_regulados_cnpmdm_historial")
