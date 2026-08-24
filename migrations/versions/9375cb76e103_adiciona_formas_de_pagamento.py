"""adiciona formas de pagamento

Revision ID: 9375cb76e103
Revises: 9fc710bced1a
Create Date: 2026-08-24 11:18:14.394034
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9375cb76e103"
down_revision: Union[str, Sequence[str], None] = "9fc710bced1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela de pagamentos."""

    op.create_table(
        "pagamentos",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "venda_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "forma",
            sa.String(length=30),
            nullable=False
        ),

        sa.Column(
            "valor",
            sa.Float(),
            nullable=False
        ),

        sa.Column(
            "valor_recebido",
            sa.Float(),
            nullable=True
        ),

        sa.Column(
            "troco",
            sa.Float(),
            nullable=True
        ),

        sa.ForeignKeyConstraint(
            ["venda_id"],
            ["vendas.id"],
            ondelete="CASCADE"
        ),

        sa.PrimaryKeyConstraint("id")
    )

    op.create_index(
        "ix_pagamentos_id",
        "pagamentos",
        ["id"],
        unique=False
    )


def downgrade() -> None:
    """Remove a tabela de pagamentos."""

    op.drop_index(
        "ix_pagamentos_id",
        table_name="pagamentos"
    )

    op.drop_table("pagamentos")