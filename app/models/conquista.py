from sqlalchemy import Column, Integer, String, Float
from app.database import Base

class Conquista(Base):
    __tablename__ = "conquistas"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    nome = Column(String(167), nullable=False, unique=True)

    descricao = Column(String(255), nullable=False)

    xp_requerido = Column(Integer, nullable=False)

    desconto_reais = Column(Float, nullable=False, default=0.0)

    icon = Column(String(255), nullable=False)
