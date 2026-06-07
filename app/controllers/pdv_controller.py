# ============================================================
# controllers/pdv_controller.py — Ponto de Venda
# ============================================================
# O PDV funciona assim:
# 1. GET /pdv            → tela com produtos + campo de cliente
# 2. O carrinho vive no JavaScript (memória do navegador)
# 3. POST /pdv/finalizar → recebe um JSON com os itens
#                          cria Venda + ItensVenda + Movimentacao + baixa estoque
# ============================================================

import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.venda import Venda, ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.auth import get_usuario_logado

router = APIRouter(prefix="/pdv", tags=["PDV"])
templates = Jinja2Templates(directory="app/templates")

DESCONTO_ASSOCIADO = 10.0  # percentual fixo


def _redirect_pdv(db: Session, url: str) -> RedirectResponse:
    db.rollback()
    return RedirectResponse(url=url, status_code=302)


def _parse_carrinho_json(raw: str) -> list:
    parsed = json.loads(raw)

    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    if isinstance(parsed, dict):
        parsed = list(parsed.values())

    if not isinstance(parsed, list):
        raise ValueError("carrinho deve ser uma lista")

    return parsed


def _extrair_produto_id(item: dict) -> int | None:
    for chave in ("produto_id", "id", "productId"):
        valor = item.get(chave)
        if valor is None or valor == "":
            continue
        try:
            produto_id = int(valor)
        except (TypeError, ValueError):
            continue
        if produto_id > 0:
            return produto_id
    return None


@router.get("/")
def tela_pdv(
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """
    Carrega a tela do PDV com todos os produtos ativos
    e a lista de clientes para o campo de busca.
    """
    produtos  = (
        db.query(Produto)
        .filter(Produto.ativo == True, Produto.estoque_atual > 0)
        .order_by(Produto.nome)
        .all()
    )
    clientes  = (
        db.query(Cliente)
        .filter(Cliente.ativo == True)
        .order_by(Cliente.nome)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "admin/pos.html",
        {
            "request":             request,
            "usuario":             usuario,
            "produtos":            produtos,
            "clientes":            clientes,
            "css_path":            "css/pos.css",
            "active":              "pos",
            "page_title":          "Ponto de Venda",
            "page_subtitle":       "Monte o carrinho e finalize a venda",
            "desconto_associado":  DESCONTO_ASSOCIADO,
        }
    )


@router.post("/finalizar")
def finalizar_venda(
    request: Request,
    carrinho_json: str = Form(...),  # JSON serializado pelo JS
    cliente_id: int    = Form(0),    # 0 = sem cliente identificado
    observacao: str    = Form(""),
    db: Session        = Depends(get_db),
    usuario            = Depends(get_usuario_logado)
):

    try:
        itens = _parse_carrinho_json(carrinho_json.strip())
    except (json.JSONDecodeError, ValueError, AttributeError):
        return _redirect_pdv(db, "/pdv?erro=json")

    if not itens:
        return _redirect_pdv(db, "/pdv?erro=vazio")

    # Busca o cliente e verifica se é associado
    cliente             = None
    desconto_percentual = 0.0
    cliente_id_valido   = None

    if cliente_id:
        cliente = db.query(Cliente).filter(
            Cliente.id == cliente_id,
            Cliente.ativo == True
        ).first()

        if cliente:
            cliente_id_valido = cliente.id
            if cliente.is_associado:
                desconto_percentual = DESCONTO_ASSOCIADO

    # ── Valida estoque e calcula totais ──────────────────────
    total_bruto = 0.0
    itens_validados = []

    for item in itens:
        if not isinstance(item, dict):
            return _redirect_pdv(db, "/pdv?erro=item_invalido")

        produto_id = _extrair_produto_id(item)
        if produto_id is None:
            return _redirect_pdv(db, "/pdv?erro=item_invalido")

        try:
            qtd = int(item.get("quantidade", 0))
        except (TypeError, ValueError):
            return _redirect_pdv(db, "/pdv?erro=quantidade")

        if qtd <= 0:
            return _redirect_pdv(db, "/pdv?erro=quantidade")

        produto = db.query(Produto).filter(
            Produto.id == produto_id,
            Produto.ativo == True
        ).with_for_update().first()

        if not produto:
            return _redirect_pdv(
                db,
                f"/pdv?erro=produto_inexistente&id={produto_id}",
            )

        if produto.estoque_atual < qtd:
            return _redirect_pdv(
                db,
                f"/pdv?erro=estoque&produto={quote(produto.nome)}",
            )

        subtotal    = produto.preco * qtd
        total_bruto += subtotal

        itens_validados.append({
            "produto":       produto,
            "quantidade":    qtd,
            "preco":         produto.preco,
            "produto_nome":  produto.nome,
        })

    # ── Calcula desconto e total final
    desconto_valor = total_bruto * (desconto_percentual / 100)
    total_liquido  = total_bruto - desconto_valor

    # ── Persiste tudo em uma única transação
    try:
        venda = Venda(
            cliente_id          = cliente_id_valido,
            usuario_id          = usuario.get("id"),
            desconto_percentual = desconto_percentual,
            total_bruto         = round(total_bruto, 2),
            total_liquido       = round(total_liquido, 2),
            observacao          = observacao or None,
        )
        db.add(venda)
        db.flush()  # gera o venda.id sem commitar ainda

        for item in itens_validados:
            db.add(ItemVenda(
                venda_id       = venda.id,
                produto_id     = item["produto"].id,
                produto_nome   = item["produto_nome"],
                quantidade     = item["quantidade"],
                preco_unitario = item["preco"],
            ))
            item["produto"].estoque_atual -= item["quantidade"]
            db.add(Movimentacao(
                tipo=Tipo_de_movimentacao.SAIDA,
                quantidade=item["quantidade"],
                preco_unitario=item["preco"],
                observacao=f"Venda PDV #{venda.id}",
                produto_id=item["produto"].id,
                usuario_id=usuario.get("id"),
            ))

        db.commit()
    except Exception:
        db.rollback()
        return RedirectResponse(url="/pdv?erro=salvar", status_code=302)

    return RedirectResponse(
        url=f"/pdv/venda/{venda.id}?sucesso=ok",
        status_code=302
    )


@router.get("/venda/{venda_id}")
def detalhe_venda(
    venda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """Comprovante da venda — exibido imediatamente após finalizar."""
    venda = db.query(Venda).filter(Venda.id == venda_id).first()

    if not venda:
        return RedirectResponse(url="/pdv", status_code=302)

    return templates.TemplateResponse(
        request,
        "admin/comprovante.html",
        {
            "request": request,
            "usuario": usuario,
            "venda": venda,
            "page_title": f"Venda #{venda.id}",
            "page_subtitle": "Comprovante da venda finalizada",
            "css_path": "css/vendas.css",
            "active": "pos",
        }
    )


@router.get("/historico")
def historico_vendas(
    request: Request,
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_logado)
):
    """Histórico de todas as vendas."""
    vendas = (
        db.query(Venda)
        .order_by(Venda.criado_em.desc())
        .limit(100)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/vendas.html",
        {
            "request": request,
            "usuario": usuario,
            "vendas": vendas,
            "page_title": "Vendas",
            "page_subtitle": "Histórico de vendas do PDV",
            "css_path": "css/vendas.css",
            "active": "pos",
        }
    )
