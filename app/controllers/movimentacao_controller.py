from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_admin, get_usuario_logado
from app.database import get_db
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.models.produto import Produto

router = APIRouter(prefix="/movimentacoes", tags=["Movimentações"])
templates = Jinja2Templates(directory="app/templates")


def _contexto_formulario(request, usuario, produtos, produto_id=0, erro=None):
    return {
        "request": request,
        "usuario": usuario,
        "produtos": produtos,
        "produto_id": produto_id,
        "tipos": list(Tipo_de_movimentacao),
        "erro": erro,
        "page_title": "Nova movimentação",
        "page_subtitle": "Registre entradas e saídas de estoque",
        "css_path": "css/movimentacoes.css",
        "active": "movimentacoes",
    }


@router.get("/")
def listar_movimentacoes(
    request: Request,
    produto_id: int = 0,
    tipo: str = "",
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
):
    query = db.query(Movimentacao).order_by(Movimentacao.criando_em.desc())

    if produto_id:
        query = query.filter(Movimentacao.produto_id == produto_id)

    if tipo in {item.value for item in Tipo_de_movimentacao}:
        query = query.filter(Movimentacao.tipo == Tipo_de_movimentacao(tipo))

    # permite visualização por operadores e admins
    role = usuario.get("role") if isinstance(usuario, dict) else getattr(usuario, "role", None)
    if role not in ("admin", "operador"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Acesso negado")

    movimentacoes = query.limit(200).all()
    produtos = db.query(Produto).filter(Produto.ativo == True).order_by(Produto.nome).all()

    return templates.TemplateResponse(
        request,
        "admin/movimentacoes.html",
        {
            "request": request,
            "usuario": usuario,
            "movimentacoes": movimentacoes,
            "produtos": produtos,
            "produto_id": produto_id,
            "tipo": tipo,
            "page_title": "Movimentações",
            "page_subtitle": "Histórico de entradas e saídas do estoque",
            "css_path": "css/movimentacoes.css",
            "active": "movimentacoes",
            # mostre botão de nova movimentação somente para admin (operador faz movimentações via PDV)
            "extra_button": {"href": "/movimentacoes/nova", "label": "Nova movimentação"} if role == "admin" else None,
        },
    )


@router.get("/nova")
def form_nova_movimentacao(
    request: Request,
    produto_id: int = 0,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
):
    produtos = db.query(Produto).filter(Produto.ativo == True).order_by(Produto.nome).all()

    return templates.TemplateResponse(
        request,
        "admin/movimentacao_form.html",
        _contexto_formulario(request, usuario, produtos, produto_id),
    )


@router.post("/nova")
def registrar_movimentacao(
    request: Request,
    produto_id: int = Form(...),
    tipo: str = Form(...),
    quantidade: int = Form(...),
    preco_unitario: float = Form(...),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
):
    produtos = db.query(Produto).filter(Produto.ativo == True).order_by(Produto.nome).all()

    if tipo not in {item.value for item in Tipo_de_movimentacao}:
        return templates.TemplateResponse(
            request,
            "admin/movimentacao_form.html",
            _contexto_formulario(request, usuario, produtos, produto_id, "Tipo de movimentação inválido."),
            status_code=400,
        )

    if quantidade <= 0:
        return templates.TemplateResponse(
            request,
            "admin/movimentacao_form.html",
            _contexto_formulario(request, usuario, produtos, produto_id, "A quantidade deve ser maior que zero."),
            status_code=400,
        )

    produto = (
        db.query(Produto)
        .filter(Produto.id == produto_id, Produto.ativo == True)
        .with_for_update()
        .first()
    )

    if not produto:
        return RedirectResponse(url="/movimentacoes/nova", status_code=302)

    tipo_movimentacao = Tipo_de_movimentacao(tipo)

    if tipo_movimentacao == Tipo_de_movimentacao.SAIDA and quantidade > produto.estoque_atual:
        erro = f"Estoque insuficiente. Disponível: {produto.estoque_atual} unidade(s)."
        return templates.TemplateResponse(
            request,
            "admin/movimentacao_form.html",
            _contexto_formulario(request, usuario, produtos, produto_id, erro),
            status_code=400,
        )

    if tipo_movimentacao == Tipo_de_movimentacao.ENTRADA:
        produto.estoque_atual += quantidade
    else:
        produto.estoque_atual -= quantidade

    db.add(
        Movimentacao(
            tipo=tipo_movimentacao,
            quantidade=quantidade,
            preco_unitario=preco_unitario,
            observacao=observacao.strip() or None,
            produto_id=produto_id,
            usuario_id=usuario.get("id"),
        )
    )
    db.commit()

    return RedirectResponse(url="/movimentacoes?criado=ok", status_code=302)


@router.get("/produto/{produto_id}")
def historico_produto(
    produto_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_usuario_logado),
):
    produto = db.query(Produto).filter(Produto.id == produto_id).first()

    if not produto:
        return RedirectResponse(url="/produtos", status_code=302)

    movimentacoes = (
        db.query(Movimentacao)
        .filter(Movimentacao.produto_id == produto_id)
        .order_by(Movimentacao.criando_em.desc())
        .all()
    )
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
        "admin/movimentacao_historico.html",
        {
            "request": request,
            "usuario": usuario,
            "produto": produto,
            "movimentacoes": movimentacoes,
            "total_entradas": total_entradas,
            "total_saidas": total_saidas,
            "page_title": f"Histórico: {produto.nome}",
            "page_subtitle": "Resumo das movimentações deste produto",
            "css_path": "css/movimentacoes.css",
            "active": "movimentacoes",
        },
    )
