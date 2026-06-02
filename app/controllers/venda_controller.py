from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.auth import get_admin
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.usuario import Usuario
from app.services.gamification_service import (
    calcular_nivel_from_xp,
    verificar_nova_conquista,
    calcular_desconto_por_nivel
)
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/vendas", tags=["vendas"])

class ItemCarrinho(BaseModel):
    produto_id: int
    quantidade: int

class FinalizarVendaRequest(BaseModel):
    itens: List[ItemCarrinho]
    metodos_pagamento: str
    usuario_id: Optional[int] = None
    usuario_email: Optional[str] = None

class VendaResponse(BaseModel):
    id: int
    total: float
    xp_ganho: int
    desconto_aplicado: float
    conquista: Optional[dict] = None
    nivel_novo: Optional[int] = None

@router.get("/produtos/busca")
def buscar_produtos(q: str = "", db: Session = Depends(get_db)):
    produtos = db.query(Produto).filter(
        Produto.ativo == True,
        (Produto.nome.ilike(f"%{q}%") | Produto.descricao.ilike(f"%{q}%"))
    ).all()
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "preco": p.preco,
            "estoque": p.estoque_atual,
            "categoria": p.categoria.nome if p.categoria else "Sem categoria",
            "imagem": p.imagem_url
        }
        for p in produtos
    ]

@router.get("/produtos")
def listar_produtos(categoria_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(Produto).filter(Produto.ativo == True)
    if categoria_id:
        query = query.filter(Produto.categoria_id == categoria_id)
    produtos = query.all()
    return [
        {
            "id": p.id,
            "nome": p.nome,
            "preco": p.preco,
            "estoque": p.estoque_atual,
            "categoria": p.categoria.nome if p.categoria else "Sem categoria",
            "imagem": p.imagem_url
        }
        for p in produtos
    ]

@router.post("/finalizar", response_model=VendaResponse)
def finalizar_venda(dados: FinalizarVendaRequest, db: Session = Depends(get_db)):
    if not dados.itens:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    total = 0.0
    itens_venda = []

    for item in dados.itens:
        produto = db.query(Produto).filter(Produto.id == item.produto_id).first()
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto {item.produto_id} não encontrado")

        if produto.estoque_atual < item.quantidade:
            raise HTTPException(status_code=400, detail=f"Estoque insuficiente para {produto.nome}")

        subtotal = produto.preco * item.quantidade
        total += subtotal

        item_venda = ItemVenda(
            produto_id=item.produto_id,
            quantidade=item.quantidade,
            preco_unitario=produto.preco
        )
        itens_venda.append(item_venda)
        produto.estoque_atual -= item.quantidade

    xp_ganho = int(total)

    usuario = None
    desconto_nivel = 0
    conquista = None
    nivel_novo = None

    # Buscar usuário por ID ou email
    if dados.usuario_id:
        usuario = db.query(Usuario).filter(Usuario.id == dados.usuario_id).first()
    elif dados.usuario_email:
        usuario = db.query(Usuario).filter(Usuario.email == dados.usuario_email).first()

    if usuario:
        xp_anterior = usuario.xp_total
        usuario.xp_total += xp_ganho
        nivel_novo = calcular_nivel_from_xp(usuario.xp_total)

        if nivel_novo > usuario.nivel:
            usuario.nivel = nivel_novo
            desconto_nivel = calcular_desconto_por_nivel(nivel_novo)

        conquista = verificar_nova_conquista(xp_anterior, usuario.xp_total)
        if conquista:
            desconto_nivel = max(desconto_nivel, conquista.get("desconto", 0))

    desconto_aplicado = desconto_nivel
    total_final = total - desconto_aplicado

    venda = Venda(
        usuario_id=dados.usuario_id or 1,
        total=total_final,
        xp_ganho=xp_ganho,
        desconto_aplicado=desconto_aplicado,
        metodos_pagamento=dados.metodos_pagamento
    )
    venda.itens = itens_venda

    db.add(venda)
    if usuario:
        db.add(usuario)
    db.commit()

    return VendaResponse(
        id=venda.id,
        total=venda.total,
        xp_ganho=venda.xp_ganho,
        desconto_aplicado=venda.desconto_aplicado,
        conquista=conquista,
        nivel_novo=nivel_novo
    )

@router.delete("/cancelar/{venda_id}")
def cancelar_venda(venda_id: int, db: Session = Depends(get_db), admin = Depends(get_admin)):
    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    for item in venda.itens:
        produto = db.query(Produto).filter(Produto.id == item.produto_id).first()
        if produto:
            produto.estoque_atual += item.quantidade

    if venda.usuario_id:
        usuario = db.query(Usuario).filter(Usuario.id == venda.usuario_id).first()
        if usuario:
            usuario.xp_total = max(0, usuario.xp_total - venda.xp_ganho)
            usuario.nivel = calcular_nivel_from_xp(usuario.xp_total)
            db.add(usuario)

    db.delete(venda)
    db.commit()

    return {"mensagem": "Venda cancelada com sucesso"}

@router.get("/historico/{usuario_id}")
def historico_vendas(usuario_id: int, limit: int = 10, db: Session = Depends(get_db)):
    vendas = db.query(Venda).filter(
        Venda.usuario_id == usuario_id
    ).order_by(desc(Venda.data_venda)).limit(limit).all()

    return [
        {
            "id": v.id,
            "total": v.total,
            "xp_ganho": v.xp_ganho,
            "desconto": v.desconto_aplicado,
            "data": v.data_venda,
            "metodos": v.metodos_pagamento
        }
        for v in vendas
    ]

@router.get("/usuario/{usuario_id}")
def info_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "xp_total": usuario.xp_total,
        "nivel": usuario.nivel,
        "moedas_resgate": usuario.moedas_resgate,
        "proximo_nivel_xp": 100 * usuario.nivel
    }

@router.get("/usuario-por-email")
def info_usuario_por_email(email: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "xp_total": usuario.xp_total,
        "nivel": usuario.nivel,
        "moedas_resgate": usuario.moedas_resgate,
        "proximo_nivel_xp": 100 * usuario.nivel
    }
