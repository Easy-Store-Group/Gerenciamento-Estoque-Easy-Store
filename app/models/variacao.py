from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class ProdutoVariacao(Base):
    __tablename__ = "produto_variacoes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Relacionamento com produto
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), nullable=False)
    produto = relationship("Produto", back_populates="variacoes")
    
    # Cores e tamanhos
    cor_id = Column(Integer, ForeignKey("cores.id", ondelete="RESTRICT"), nullable=True)
    cor = relationship("Cor", back_populates="variacoes")
    
    tamanho_id = Column(Integer, ForeignKey("tamanhos.id", ondelete="RESTRICT"), nullable=True)
    tamanho_obj = relationship("Tamanho", back_populates="variacoes")
    
    # Estoque
    estoque_atual = Column(Integer, default=0)
    ativa = Column(Boolean, default=True)
    
    # Imagem da variação
    imagem = Column(String(255), nullable=True)  # Caminho da imagem no servidor
    
    # Constraint: uma cor+tamanho por produto
    __table_args__ = (UniqueConstraint("produto_id", "cor_id", "tamanho_id", name="uq_produto_cor_tamanho"),)
