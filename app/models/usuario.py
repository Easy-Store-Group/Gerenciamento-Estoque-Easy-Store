from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True)

    nome = Column(String(100), nullable=False)

    email = Column(String(100), unique=True, nullable=False, index=True)

    senha_hash = Column(String(255), nullable=False)

    #Perfil do usuario(admin ou operador)
    role = Column(String(20), nullable=False, default="operador")

    ativo = Column(Boolean, default=True)

    #preenchido automatico peli banco de dados ao criar o registro
    criado_em = Column(DateTime, server_default=func.now())
    