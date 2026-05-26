from sqlalchemy import Column, String, Boolean, Integer
from sqlalchemy.orm import relationship
from app.database import Base

class Categoria(Base): 
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(String(100), nullable=False, unique=True)
    ativo = Column(Boolean, default=True)

    #Relacionamento
    #lazy="select" carrega os produtos apenas quando acessados
    produtos = relationship("Produto", back_populates="categoria", lazy="select")