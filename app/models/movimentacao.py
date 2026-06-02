from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class Tipo_de_movimentacao(str, enum.Enum):
    ENTRADA = "entrada"
    SAIDA = "saida"

class Movimentacao(Base):
    __tablename__ = "movimentacoes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    tipo = Column(Enum(Tipo_de_movimentacao), nullable=False)

    quantidade = Column(Integer, nullable=False)

    preco_unitario = Column(Float, nullable=False, default=0.0)

    observacao = Column(String(255), nullable=True)

    criando_em = Column(DateTime, server_default=func.now())

    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False)

    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=False)

    # relacionamento
    produto = relationship("Produto", backref="movimentacoes")
    usuario = relationship("Usuario", backref="movimentacoes")

    @property
    def valor_total(self):
        return self.quantidade * self.preco_unitario