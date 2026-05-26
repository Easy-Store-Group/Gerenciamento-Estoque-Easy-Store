from sqlalchemy import Column, Integer, String, Boolean, DateTime 
from sqlalchemy.sql import func
from app.database import Base

# criar tabela usuario 
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    nome = Column(String(167), nullable=False)
    
    email = Column(String(167), unique=True, index=True, nullable=False)

    senha_hash = Column(String(255), nullable=False)

    # perfil do usuario admin - operador 
    role = Column(String(20), nullable=False, default="operador")

    ativo = Column(Boolean, default=True)

    # preenchhido automatico pelo banco de dados ao criar o registro 
    criado_em = Column(DateTime, server_default=func.now())

    