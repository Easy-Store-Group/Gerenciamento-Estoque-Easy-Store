<<<<<<< HEAD
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
=======
#  t6abela de categorias 
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    nome = Column(String(167), nullable=False, unique=True)

    descricao = Column(String(255), nullable=True)

    ativo = Column(Boolean, default=True)

    # relacionamento
    # lazy = "select" -> carrega os produtos somente quando acessados.
    produtos = relationship("Produto", back_populates="categoria", lazy="select")







>>>>>>> rotas-de-login
