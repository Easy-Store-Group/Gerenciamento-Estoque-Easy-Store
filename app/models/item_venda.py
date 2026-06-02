from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ItemVenda(Base):
    __tablename__ = "itens_vendas"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    venda_id = Column(Integer, ForeignKey("vendas.id", ondelete="CASCADE"), nullable=False)

    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False)

    quantidade = Column(Integer, nullable=False)

    preco_unitario = Column(Float, nullable=False)

    venda = relationship("Venda", back_populates="itens")

    produto = relationship("Produto")
