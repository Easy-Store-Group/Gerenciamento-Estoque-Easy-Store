from sqlalchemy import func

from app.models.produto import Produto
from app.models.variacao import ProdutoVariacao


def recalcular_estoque_produto(db, produto_id: int):

    total = (
        db.query(
            func.sum(
                ProdutoVariacao.estoque_atual
            )
        )
        .filter(
            ProdutoVariacao.produto_id == produto_id,
            ProdutoVariacao.ativa == True
        )
        .scalar()
    ) or 0

    produto = (
        db.query(Produto)
        .filter(
            Produto.id == produto_id
        )
        .first()
    )

    if produto:
        produto.estoque_atual = total