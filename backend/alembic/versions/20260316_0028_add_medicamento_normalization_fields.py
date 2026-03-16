"""Add medicamento normalization fields.

Revision ID: add_medicamento_fields
Revises: 20260316_0027
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_medicamento_fields'
down_revision = '20260316_0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('medicamentos', sa.Column('nombre_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('marca_comercial', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_cantidad', sa.Float(), nullable=True))
    op.add_column('medicamentos', sa.Column('dosis_unidad', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('via_administracion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('presentacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('tipo_liberacion', sa.String(), nullable=True))
    op.add_column('medicamentos', sa.Column('volumen_solucion', sa.Float(), nullable=True))

    op.create_index('ix_medicamentos_nombre_comercial', 'medicamentos', ['nombre_comercial'])
    op.create_index('ix_medicamentos_dosis', 'medicamentos', ['dosis_cantidad', 'dosis_unidad'])
    op.create_index('ix_medicamentos_via', 'medicamentos', ['via_administracion'])


def downgrade() -> None:
    op.drop_index('ix_medicamentos_via', table_name='medicamentos')
    op.drop_index('ix_medicamentos_dosis', table_name='medicamentos')
    op.drop_index('ix_medicamentos_nombre_comercial', table_name='medicamentos')

    op.drop_column('medicamentos', 'volumen_solucion')
    op.drop_column('medicamentos', 'tipo_liberacion')
    op.drop_column('medicamentos', 'presentacion')
    op.drop_column('medicamentos', 'via_administracion')
    op.drop_column('medicamentos', 'dosis_unidad')
    op.drop_column('medicamentos', 'dosis_cantidad')
    op.drop_column('medicamentos', 'marca_comercial')
    op.drop_column('medicamentos', 'nombre_comercial')
