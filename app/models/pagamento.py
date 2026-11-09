from sqlalchemy import Column, Integer, Float, String, ForeignKey, Text, DateTime
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

    status = Column(String(30), nullable=False, default="PENDENTE")

    provider = Column(String(50), nullable=True, default="pix")

    provider_charge_id = Column(String(255), nullable=True)

    pix_qr_code = Column(Text, nullable=True)

    pix_copy_paste = Column(Text, nullable=True)

    pix_qr_code_url = Column(String(255), nullable=True)

    pix_status = Column(String(30), nullable=True, default="PENDENTE")

    pix_data_pagamento = Column(DateTime, nullable=True)

    pix_observacao = Column(Text, nullable=True)

    venda = relationship(
        "Venda",
        back_populates="pagamentos"
    )