from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id         = Column(Integer, primary_key=True, index=True)
    nome       = Column(String(150), nullable=False, index=True)
    email      = Column(String(167), nullable=True, unique=True, index=True)
    telefone   = Column(String(20), nullable=True)

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    # is_associado define se o cliente tem 5% de desconto
    is_associado = Column(Boolean, default=False, nullable=False)

    ativo      = Column(Boolean, default=True)
    criado_em  = Column(DateTime, server_default=func.now())

    usuario = relationship("Usuario", back_populates="cliente_perfil")
    vendas  = relationship("Venda", back_populates="cliente", lazy="select")
