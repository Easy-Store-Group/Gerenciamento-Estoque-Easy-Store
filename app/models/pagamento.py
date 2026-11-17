from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Pagamento(Base):
    __tablename__ = "pagamentos"

    id = Column(Integer, primary_key=True, index=True)

    venda_id = Column(
        Integer,
        ForeignKey("vendas.id", ondelete="CASCADE"),
        nullable=False
    )

    forma = Column(String(30), nullable=False)

    valor = Column(Float, nullable=False)

    valor_recebido = Column(Float, nullable=True)

    troco = Column(Float, nullable=True)

    parcelado = Column(Boolean, nullable=False, default=False)

    numero_parcelas = Column(Integer, nullable=True, default=1)

    valor_parcela = Column(Float, nullable=True)

    venda = relationship(
        "Venda",
        back_populates="pagamentos"
    )

    parcelas_detalhe = relationship(
        "PagamentoParcela",
        back_populates="pagamento",
        cascade="all, delete-orphan",
        order_by="PagamentoParcela.numero",
    )


class PagamentoParcela(Base):
    __tablename__ = "pagamento_parcelas"
    __table_args__ = (
        UniqueConstraint(
            "pagamento_id",
            "numero",
            name="uq_pagamento_parcelas_pagamento_numero",
        ),
        CheckConstraint("numero >= 1", name="ck_pagamento_parcelas_numero_positivo"),
        CheckConstraint("valor >= 0", name="ck_pagamento_parcelas_valor_nao_negativo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    pagamento_id = Column(
        Integer,
        ForeignKey("pagamentos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    numero = Column(Integer, nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)

    pagamento = relationship("Pagamento", back_populates="parcelas_detalhe")
