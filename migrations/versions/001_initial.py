"""Initial schema with gamification

Revision ID: 001_initial
Revises:
Create Date: 2026-06-01 21:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('categorias',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nome', sa.String(length=167), nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nome')
    )
    op.create_index(op.f('ix_categorias_id'), 'categorias', ['id'], unique=False)

    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nome', sa.String(length=167), nullable=False),
    sa.Column('email', sa.String(length=167), nullable=False),
    sa.Column('senha_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('criado_em', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.Column('xp_total', sa.Integer(), server_default='0', nullable=False),
    sa.Column('nivel', sa.Integer(), server_default='1', nullable=False),
    sa.Column('moedas_resgate', sa.Integer(), server_default='0', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_usuarios_email'), 'usuarios', ['email'], unique=False)
    op.create_index(op.f('ix_usuarios_id'), 'usuarios', ['id'], unique=False)

    op.create_table('produtos',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nome', sa.String(length=167), nullable=False),
    sa.Column('preco', sa.Float(), nullable=False),
    sa.Column('plataforma', sa.String(length=100), server_default='PC', nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=True),
    sa.Column('estoque_atual', sa.Integer(), nullable=False),
    sa.Column('estoque_minimo', sa.Integer(), server_default='5', nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=True),
    sa.Column('imagem_path', sa.String(length=255), nullable=True),
    sa.Column('categoria_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['categoria_id'], ['categorias.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_produtos_id'), 'produtos', ['id'], unique=False)
    op.create_index(op.f('ix_produtos_nome'), 'produtos', ['nome'], unique=False)

    op.create_table('conquistas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nome', sa.String(length=167), nullable=False),
    sa.Column('descricao', sa.String(length=255), nullable=False),
    sa.Column('xp_requerido', sa.Integer(), nullable=False),
    sa.Column('desconto_reais', sa.Float(), nullable=False),
    sa.Column('icon', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('nome')
    )
    op.create_index(op.f('ix_conquistas_id'), 'conquistas', ['id'], unique=False)

    op.create_table('vendas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('total', sa.Float(), nullable=False),
    sa.Column('xp_ganho', sa.Integer(), nullable=False),
    sa.Column('desconto_aplicado', sa.Float(), nullable=False),
    sa.Column('metodos_pagamento', sa.String(length=255), nullable=False),
    sa.Column('data_venda', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vendas_id'), 'vendas', ['id'], unique=False)

    op.create_table('itens_vendas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('venda_id', sa.Integer(), nullable=False),
    sa.Column('produto_id', sa.Integer(), nullable=False),
    sa.Column('quantidade', sa.Integer(), nullable=False),
    sa.Column('preco_unitario', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['produto_id'], ['produtos.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['venda_id'], ['vendas.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_itens_vendas_id'), 'itens_vendas', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_itens_vendas_id'), table_name='itens_vendas')
    op.drop_table('itens_vendas')
    op.drop_index(op.f('ix_vendas_id'), table_name='vendas')
    op.drop_table('vendas')
    op.drop_index(op.f('ix_conquistas_id'), table_name='conquistas')
    op.drop_table('conquistas')
    op.drop_index(op.f('ix_produtos_nome'), table_name='produtos')
    op.drop_index(op.f('ix_produtos_id'), table_name='produtos')
    op.drop_table('produtos')
    op.drop_index(op.f('ix_usuarios_id'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_email'), table_name='usuarios')
    op.drop_table('usuarios')
    op.drop_index(op.f('ix_categorias_id'), table_name='categorias')
    op.drop_table('categorias')
