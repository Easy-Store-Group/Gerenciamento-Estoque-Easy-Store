from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Cor(Base):
    __tablename__ = "cores"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(String(100), nullable=False, unique=True, index=True)
    codigo_hex = Column(String(9), nullable=True)  # Ex: #FF5733
    ativa = Column(Boolean, default=True)

    # Relacionamento com variações
    variacoes = relationship("ProdutoVariacao", back_populates="cor")


class Tamanho(Base):
    __tablename__ = "tamanhos"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(String(100), nullable=False, unique=True, index=True)
    ativa = Column(Boolean, default=True)

    # Relacionamento com variações
    variacoes = relationship("ProdutoVariacao", back_populates="tamanho_obj")
