from sqlalchemy import Column, String, Boolean, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    nome = Column(String(200), nullable=False, index=True)
    preco = Column(Float, nullable=False, default=0.0)
    estoque = Column(Integer, nullable=False, default=0)
    ativo = Column(Boolean, default=True)
    
    imagem_path = Column(String(255))

    categoria_id = Column(Integer, ForeignKey("categorias.id", ondelete="SET NULL"), nullable=True)

    categoria = relationship("Categoria", back_populates="produtos")

    #Metodo
    @property
    def imagem_url(self):
        if self.imagem_path:
            return f"/static/{self.imagem_path}"
        else:
            return "/static/img/place-holder.png"