from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.models.produto import Produto
from app.auth import get_usuario_logado, get_admin

router = APIRouter(prefix="/movimentacoes", tags=["Movimentações"])

templates = Jinja2Templates(directory="app/templates")


# ============================================================
# HISTÓRICO GERAL — somente admin
# ============================================================

@router.get("/")
def listar_movimentacoes(
    request: Request,
    produto_id: int = 0,     # filtra por produto específico
    tipo: str = "",          # "entrada" ou "saida"
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    """
    Exibe o histórico completo de movimentações com filtros
    por produto e tipo. Acessível apenas por admins.
    """
    query = db.query(Movimentacao).order_by(Movimentacao.criando_em.desc())

    if produto_id:
        query = query.filter(Movimentacao.produto_id == produto_id)

    if tipo in ("entrada", "saida", "cancelamento", "ajuste"):
        query = query.filter(Movimentacao.tipo == tipo)

    movimentacoes = query.limit(200).all()  # limita para não sobrecarregar
    produtos      = db.query(Produto).filter(Produto.ativo == True).all()

    return templates.TemplateResponse(
        request,
        "movimentacoes/index.html",
        {
            "request":        request,
            "usuario":        admin,
            "movimentacoes":  movimentacoes,
            "produtos":       produtos,
            "produto_id":     produto_id,
            "tipo":           tipo,
        }
    )


# ============================================================
# REGISTRAR MOVIMENTAÇÃO
# ============================================================

@router.get("/nova")
def form_nova_movimentacao(
    request: Request,
    produto_id: int = 0,   # pré-seleciona o produto se vier da página de detalhe
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """
    Exibe o formulário de registro de movimentação.
    Pode receber produto_id via query string para
    pré-selecionar o produto direto da página de detalhe.
    """
    produtos = db.query(Produto).filter(Produto.ativo == True).all()

    return templates.TemplateResponse(
        request,
        "movimentacoes/form.html",
        {
            "request":    request,
            "usuario":    usuario,
            "produtos":   produtos,
            "produto_id": produto_id,
            "tipos":      Tipo_de_movimentacao,  # passa o enum para o template
        }
    )


@router.post("/nova")
def registrar_movimentacao(
    request: Request,
    produto_id: int     = Form(...),
    tipo: str           = Form(...),
    quantidade: int     = Form(...),
    preco_unitario: float = Form(...),
    observacao: str     = Form(""),
    db: Session         = Depends(get_db),
    usuario             = Depends(get_usuario_logado)
):
    """
    Registra a movimentação e atualiza o estoque do produto
    em uma única transação — garante consistência.

    Se qualquer operação falhar, o rollback desfaz tudo:
    nem a movimentação é salva nem o estoque é alterado.
    """
    produtos = db.query(Produto).filter(Produto.ativo == True).all()

    # Valida se o tipo enviado é válido
    if tipo not in (Tipo_de_movimentacao.ENTRADA, Tipo_de_movimentacao.SAIDA):
        return templates.TemplateResponse(
            request,
            "movimentacoes/form.html",
            {
                "request":    request,
                "usuario":    usuario,
                "produtos":   produtos,
                "produto_id": produto_id,
                "tipos":      Tipo_de_movimentacao,
                "erro":       "Tipo de movimentação inválido.",
            },
            status_code=400
        )

    if quantidade <= 0:
        return templates.TemplateResponse(
            request,
            "movimentacoes/form.html",
            {
                "request":    request,
                "usuario":    usuario,
                "produtos":   produtos,
                "produto_id": produto_id,
                "tipos":      Tipo_de_movimentacao,
                "erro":       "A quantidade deve ser maior que zero.",
            },
            status_code=400
        )

    # Busca o produto com lock para evitar race condition:
    # se dois usuários registrarem saída ao mesmo tempo,
    # with_for_update() garante que um espera o outro terminar.
    produto = db.query(Produto).filter(
        Produto.id == produto_id
    ).with_for_update().first()

    if not produto:
        return RedirectResponse(url="/movimentacoes/nova", status_code=302)

    # Impede saída maior que o estoque disponível
    if tipo == Tipo_de_movimentacao.SAIDA and quantidade > produto.estoque_atual:
        return templates.TemplateResponse(
            request,
            "movimentacoes/form.html",
            {
                "request":    request,
                "usuario":    usuario,
                "produtos":   produtos,
                "produto_id": produto_id,
                "tipos":      Tipo_de_movimentacao,
                "erro": (
                    f"Estoque insuficiente. "
                    f"Disponível: {produto.estoque_atual} unidade(s)."
                ),
            },
            status_code=400
        )

    # ----------------------------------------------------------
    # Atualiza o estoque do produto
    # ----------------------------------------------------------
    if tipo == Tipo_de_movimentacao.ENTRADA:
        produto.estoque_atual += quantidade
    else:
        produto.estoque_atual -= quantidade

    # ----------------------------------------------------------
    # Registra a movimentação no histórico
    # ----------------------------------------------------------
    movimentacao = Movimentacao(
        tipo           = tipo,
        quantidade     = quantidade,
        preco_unitario = preco_unitario,
        observacao     = observacao or None,
        produto_id     = produto_id,
        usuario_id     = usuario.get("id"),
    )

    db.add(movimentacao)
    db.commit()  # salva produto (estoque) + movimentação juntos

    return RedirectResponse(
        url=f"/produtos/{produto_id}?movimentacao=ok",
        status_code=302
    )


# ============================================================
# HISTÓRICO POR PRODUTO — acessível por qualquer logado
# ============================================================

@router.get("/produto/{produto_id}")
def historico_produto(
    produto_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """
    Exibe o histórico de movimentações de um produto específico
    com o resumo de entradas, saídas e saldo.
    """
    produto = db.query(Produto).filter(Produto.id == produto_id).first()

    if not produto:
        return RedirectResponse(url="/produtos", status_code=302)

    movimentacoes = (
        db.query(Movimentacao)
        .filter(Movimentacao.produto_id == produto_id)
        .order_by(Movimentacao.criando_em.desc())
        .all()
    )

    # Resumo calculado em Python a partir do histórico
    total_entradas = sum(
        m.quantidade for m in movimentacoes
        if m.tipo == Tipo_de_movimentacao.ENTRADA
    )
    total_saidas = sum(
        m.quantidade for m in movimentacoes
        if m.tipo == Tipo_de_movimentacao.SAIDA
    )

    return templates.TemplateResponse(
        request,
        "movimentacoes/historico.html",
        {
            "request":        request,
            "usuario":        usuario,
            "produto":        produto,
            "movimentacoes":  movimentacoes,
            "total_entradas": total_entradas,
            "total_saidas":   total_saidas,
        }
    )