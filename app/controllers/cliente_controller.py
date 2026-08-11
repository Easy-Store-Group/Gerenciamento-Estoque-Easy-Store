import os
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_cliente
from app.database import get_db
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.models.venda import Venda
from app.services.cliente_service import obter_ou_criar_cliente

router = APIRouter(prefix="/cliente", tags=["Cliente"])
templates = Jinja2Templates(directory="app/templates")

WHATSAPP_NUMERO_LOJA = os.getenv("WHATSAPP_NUMERO_LOJA", "5511915724817")


def montar_link_reserva_whatsapp(produto: Produto, nome_cliente: str = "") -> str:
    saudacao = f"Meu nome e {nome_cliente}. " if nome_cliente else ""
    mensagem = (
        f"Ola! {saudacao}Gostaria de reservar o produto {produto.nome} "
        f"por R$ {produto.preco:.2f}."
    )
    return f"https://wa.me/{WHATSAPP_NUMERO_LOJA}?text={quote(mensagem)}"


@router.get("/")
def portal_cliente(
    request: Request,
    secao: str = "produtos",
    categoria_id: int = 0,
    busca: str = "",
    db: Session = Depends(get_db),
    usuario=Depends(get_cliente),
):
    cliente = obter_ou_criar_cliente(db, usuario.get("id"))
    if not cliente:
        return RedirectResponse(url="/auth/login", status_code=302)

    categorias = (
        db.query(Categoria)
        .filter(Categoria.ativo == True)
        .order_by(Categoria.nome)
        .all()
    )

    query = db.query(Produto).filter(Produto.ativo == True)
    if categoria_id:
        query = query.filter(Produto.categoria_id == categoria_id)
    if busca.strip():
        query = query.filter(Produto.nome.ilike(f"%{busca.strip()}%"))
    produtos = query.order_by(Produto.nome).all()
    links_reserva = {
        produto.id: montar_link_reserva_whatsapp(produto, cliente.nome)
        for produto in produtos
    }

    compras = (
        db.query(Venda)
        .filter(Venda.cliente_id == cliente.id)
        .order_by(Venda.criado_em.desc())
        .limit(50)
        .all()
    )

    secoes_validas = {"produtos", "categorias", "compras"}
    secao_ativa = secao if secao in secoes_validas else "produtos"

    return templates.TemplateResponse(
        request,
        "cliente/portal.html",
        {
            "request": request,
            "usuario": usuario,
            "cliente": cliente,
            "produtos": produtos,
            "categorias": categorias,
            "compras": compras,
            "secao_ativa": secao_ativa,
            "categoria_id": categoria_id,
            "busca": busca,
            "links_reserva": links_reserva,
            "css_path": "css/cliente.css",
        },
    )
