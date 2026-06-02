from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database import get_db
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.categoria import Categoria
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/caixa", tags=["caixa"])

@router.get("/alertas/estoque")
def alertas_estoque_minimo(db: Session = Depends(get_db)):
    """Retorna produtos com estoque abaixo do mínimo"""
    alertas = db.query(Produto).filter(
        Produto.ativo == True,
        Produto.estoque_atual <= Produto.estoque_minimo
    ).all()

    return [
        {
            "id": p.id,
            "nome": p.nome,
            "estoque_atual": p.estoque_atual,
            "estoque_minimo": p.estoque_minimo,
            "preco": p.preco,
            "urgencia": "crítica" if p.estoque_atual == 0 else "alta" if p.estoque_atual < p.estoque_minimo / 2 else "normal"
        }
        for p in alertas
    ]

@router.get("/resumo/dia")
def resumo_dia(db: Session = Depends(get_db)):
    """Retorna resumo de vendas do dia"""
    inicio_dia = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

    vendas = db.query(Venda).filter(
        Venda.data_venda >= inicio_dia,
        Venda.data_venda <= fim_dia
    ).all()

    total_vendas = sum(v.total for v in vendas)
    total_itens = sum(len(v.itens) for v in vendas)
    total_xp = sum(v.xp_ganho for v in vendas)
    desconto_total = sum(v.desconto_aplicado for v in vendas)

    return {
        "numero_vendas": len(vendas),
        "total_vendas": total_vendas,
        "total_itens": total_itens,
        "total_xp": total_xp,
        "desconto_total": desconto_total,
        "ticket_medio": total_vendas / len(vendas) if vendas else 0
    }

@router.get("/fluxo-caixa")
def fluxo_caixa(dias: int = 30, db: Session = Depends(get_db)):
    """Retorna gráfico de fluxo de caixa dos últimos N dias"""
    data_inicio = datetime.now() - timedelta(days=dias)

    vendas = db.query(Venda).filter(
        Venda.data_venda >= data_inicio
    ).all()

    fluxo = {}
    for venda in vendas:
        data_chave = venda.data_venda.strftime("%Y-%m-%d")
        if data_chave not in fluxo:
            fluxo[data_chave] = 0
        fluxo[data_chave] += venda.total

    return {
        "periodo": f"Últimos {dias} dias",
        "dados": [
            {
                "data": data,
                "total": total
            }
            for data, total in sorted(fluxo.items())
        ]
    }

@router.get("/vendas-por-categoria")
def vendas_por_categoria(db: Session = Depends(get_db)):
    """Retorna total de vendas por categoria"""
    categorias = db.query(Categoria).filter(Categoria.ativo == True).all()

    resultado = []
    for cat in categorias:
        total = db.query(func.sum(Venda.total)).join(
            ItemVenda, Venda.id == ItemVenda.venda_id
        ).join(
            Produto, ItemVenda.produto_id == Produto.id
        ).filter(
            Produto.categoria_id == cat.id
        ).scalar()

        resultado.append({
            "categoria": cat.nome,
            "total": total or 0
        })

    return sorted(resultado, key=lambda x: x["total"], reverse=True)

@router.get("/top-produtos")
def top_produtos(limit: int = 10, db: Session = Depends(get_db)):
    """Retorna produtos mais vendidos"""
    produtos = db.query(
        Produto.id,
        Produto.nome,
        func.sum(ItemVenda.quantidade).label("total_vendido"),
        func.sum(ItemVenda.quantidade * ItemVenda.preco_unitario).label("total_valor")
    ).join(
        ItemVenda, Produto.id == ItemVenda.produto_id
    ).group_by(
        Produto.id, Produto.nome
    ).order_by(
        desc("total_vendido")
    ).limit(limit).all()

    return [
        {
            "id": p[0],
            "nome": p[1],
            "quantidade_vendida": p[2],
            "valor_total": p[3]
        }
        for p in produtos
    ]
