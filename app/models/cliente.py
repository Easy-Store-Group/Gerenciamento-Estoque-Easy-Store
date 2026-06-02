from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id         = Column(Integer, primary_key=True, index=True)
    nome       = Column(String(150), nullable=False, index=True)

    # Matrícula do aluno SENAI — único, usado para identificar o associado
    matricula  = Column(String(50), nullable=True, unique=True)

    telefone   = Column(String(20), nullable=True)

    # is_associado define se o cliente tem 10% de desconto
    is_associado = Column(Boolean, default=False, nullable=False)

    ativo      = Column(Boolean, default=True)
    criado_em  = Column(DateTime, server_default=func.now())
