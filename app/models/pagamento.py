from sqlalchemy import Column, Integer, Float, String, ForeignKey
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

    venda = relationship(
        "Venda",
        back_populates="pagamentos"
    )