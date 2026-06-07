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
            "css_path": "css/cliente.css",
        },
    )
