"""vincular cliente usuario

Revision ID: b1c2d3e4f5a6
Revises: 3d80eb561919
Create Date: 2026-06-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "3d80eb561919"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("clientes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=167), nullable=True))
        batch_op.add_column(sa.Column("usuario_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_clientes_usuario_id",
            "usuarios",
            ["usuario_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_clientes_email", ["email"], unique=True)
        batch_op.create_index("ix_clientes_usuario_id", ["usuario_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("clientes", schema=None) as batch_op:
        batch_op.drop_index("ix_clientes_usuario_id")
        batch_op.drop_index("ix_clientes_email")
        batch_op.drop_constraint("fk_clientes_usuario_id", type_="foreignkey")
        batch_op.drop_column("usuario_id")
        batch_op.drop_column("email")
