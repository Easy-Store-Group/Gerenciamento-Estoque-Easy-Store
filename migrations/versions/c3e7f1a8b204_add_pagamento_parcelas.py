"""Create exact installment detail rows per payment.

Revision ID: c3e7f1a8b204
Revises: 9375cb76e103
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e7f1a8b204"
down_revision: Union[str, Sequence[str], None] = "9375cb76e103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pagamento_parcelas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pagamento_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("numero >= 1", name="ck_pagamento_parcelas_numero_positivo"),
        sa.CheckConstraint("valor >= 0", name="ck_pagamento_parcelas_valor_nao_negativo"),
        sa.ForeignKeyConstraint(["pagamento_id"], ["pagamentos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pagamento_id",
            "numero",
            name="uq_pagamento_parcelas_pagamento_numero",
        ),
    )
    op.create_index(
        "ix_pagamento_parcelas_pagamento_id",
        "pagamento_parcelas",
        ["pagamento_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    parcelas_existentes = bind.execute(
        sa.text("SELECT COUNT(*) FROM pagamento_parcelas")
    ).scalar_one()
    if parcelas_existentes:
        raise RuntimeError(
            "Downgrade bloqueado: pagamento_parcelas contém dados. Faça backup/exportação "
            "dos detalhes antes de removê-los."
        )

    op.drop_index("ix_pagamento_parcelas_pagamento_id", table_name="pagamento_parcelas")
    op.drop_table("pagamento_parcelas")
