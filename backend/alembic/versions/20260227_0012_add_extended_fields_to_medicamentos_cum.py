"""Add extended fields to medicamentos_cum

Revision ID: 20260227_0012
Revises: 20260227_0011
Create Date: 2026-02-27 21:00:00.000000

Descripcion:
    Amplía la tabla medicamentos_cum con los campos adicionales que devuelve
    la API Socrata de datos.gov.co pero que no estaban siendo almacenados:

    - fechaexpedicion      TIMESTAMPTZ NULL: fecha de expedición del registro sanitario
    - estadoregistro       VARCHAR NULL: estado del registro (Vigente, Vencido, En tramite renov)
    - fechaactivo          TIMESTAMPTZ NULL: fecha en que el CUM fue marcado como activo
    - fechainactivo        TIMESTAMPTZ NULL: fecha en que el CUM fue marcado como inactivo
    - muestramedica        VARCHAR NULL: indica si es muestra médica ('Si' / 'No')
    - unidad               VARCHAR NULL: unidad de dispensación (ej. 'U')
    - viaadministracion    VARCHAR NULL: vía de administración (ej. 'ORAL')
    - concentracion        VARCHAR NULL: código de concentración (ej. 'A')
    - unidadmedida         VARCHAR NULL: unidad de medida del principio activo (ej. 'mg', 'mcg')
    - cantidad             VARCHAR NULL: cantidad del principio activo (ej. '12.5', '0.03')
                           Se almacena como texto para manejar valores como 'A'.
    - unidadreferencia     VARCHAR NULL: unidad de referencia (ej. 'TABLETA RECUBIERTA')
    - formafarmaceutica    VARCHAR NULL: forma farmacéutica (ej. 'TABLETA RECUBIERTA')
    - nombrerol            VARCHAR NULL: nombre del titular del rol (fabricante/importador)
    - tiporol              VARCHAR NULL: tipo de rol (FABRICANTE, IMPORTADOR, etc.)
    - modalidad            VARCHAR NULL: modalidad de comercialización (ej. 'FABRICAR Y VENDER')
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260227_0012"
down_revision = "20260227_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicamentos_cum", sa.Column("fechaexpedicion", sa.DateTime(timezone=True), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("estadoregistro", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("fechaactivo", sa.DateTime(timezone=True), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("fechainactivo", sa.DateTime(timezone=True), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("muestramedica", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("unidad", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("viaadministracion", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("concentracion", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("unidadmedida", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("cantidad", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("unidadreferencia", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("formafarmaceutica", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("nombrerol", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("tiporol", sa.String(), nullable=True))
    op.add_column("medicamentos_cum", sa.Column("modalidad", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("medicamentos_cum", "modalidad")
    op.drop_column("medicamentos_cum", "tiporol")
    op.drop_column("medicamentos_cum", "nombrerol")
    op.drop_column("medicamentos_cum", "formafarmaceutica")
    op.drop_column("medicamentos_cum", "unidadreferencia")
    op.drop_column("medicamentos_cum", "cantidad")
    op.drop_column("medicamentos_cum", "unidadmedida")
    op.drop_column("medicamentos_cum", "concentracion")
    op.drop_column("medicamentos_cum", "viaadministracion")
    op.drop_column("medicamentos_cum", "unidad")
    op.drop_column("medicamentos_cum", "muestramedica")
    op.drop_column("medicamentos_cum", "fechainactivo")
    op.drop_column("medicamentos_cum", "fechaactivo")
    op.drop_column("medicamentos_cum", "estadoregistro")
    op.drop_column("medicamentos_cum", "fechaexpedicion")
