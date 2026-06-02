from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Venda(Base):
    __tablename__ = "vendas"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)

    total = Column(Float, nullable=False)

    xp_ganho = Column(Integer, nullable=False, default=0)

    desconto_aplicado = Column(Float, nullable=False, default=0.0)

    metodos_pagamento = Column(String(255), nullable=False)

    data_venda = Column(DateTime, server_default=func.now())

    itens = relationship("ItemVenda", back_populates="venda", cascade="all, delete-orphan")
