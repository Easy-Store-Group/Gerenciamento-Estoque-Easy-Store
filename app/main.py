from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import get_admin, get_usuario_opcional
from app.controllers import auth_controller
from app.controllers import admin_controller
from app.controllers import categoria_controller
from app.controllers import movimentacao_controller
from app.controllers import pdv_controller
from app.controllers import produto_controller
from app.controllers import cliente_controller
from app.database import get_db
from app.models.categoria import Categoria
from app.models.cliente import Cliente
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.models.venda import Venda

app = FastAPI(title="Sistema estoque")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")

from app.errors import (
    NaoAutenticadoError,
    PermissaoNegadaError,
    RecursoNaoEncontradoError,
    EstoqueInsuficienteError,
    OperacaoInvalidaError,
    handler_nao_autenticado,
    handler_permissao_negada,
    handler_recurso_nao_encontrado,
    handler_estoque_insuficiente,
    handler_operacao_invalida,
)

# Registra handlers de exceções customizadas (API -> JSON ; Frontend -> HTML/redirect)
app.add_exception_handler(NaoAutenticadoError, handler_nao_autenticado)
app.add_exception_handler(PermissaoNegadaError, handler_permissao_negada)
app.add_exception_handler(RecursoNaoEncontradoError, handler_recurso_nao_encontrado)
app.add_exception_handler(EstoqueInsuficienteError, handler_estoque_insuficiente)
app.add_exception_handler(OperacaoInvalidaError, handler_operacao_invalida)

app.include_router(auth_controller.router)
app.include_router(admin_controller.router)
app.include_router(categoria_controller.router)
app.include_router(produto_controller.router)
app.include_router(movimentacao_controller.router)
app.include_router(pdv_controller.router)
app.include_router(cliente_controller.router)


@app.get("/")
def home(request: Request, usuario=Depends(get_usuario_opcional)):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "usuario": usuario},
    )


@app.get("/admin")
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin),
):
    total_produtos = db.query(Produto).count()
    total_categorias = db.query(Categoria).count()
    total_usuarios = db.query(Usuario).count()
    ativos_produtos = db.query(Produto).filter(Produto.ativo == True).count()
    ultimas_vendas = (
        db.query(Venda)
        .order_by(Venda.criado_em.desc())
        .limit(8)
        .all()
    )

    hoje = datetime.now().date()
    dias_grafico = [hoje - timedelta(days=dia) for dia in range(6, -1, -1)]
    inicio_periodo = datetime.combine(dias_grafico[0], datetime.min.time())
    vendas_periodo = db.query(Venda).filter(Venda.criado_em >= inicio_periodo).all()
    totais_por_dia = {dia: 0.0 for dia in dias_grafico}

    for venda in vendas_periodo:
        if venda.criado_em:
            dia_venda = venda.criado_em.date()
            if dia_venda in totais_por_dia:
                totais_por_dia[dia_venda] += venda.total_liquido or 0.0

    maior_total = max(totais_por_dia.values()) or 1
    vendas_grafico = [
        {
            "label": dia.strftime("%d/%m"),
            "total": total,
            "percentual": round((total / maior_total) * 100),
        }
        for dia, total in totais_por_dia.items()
    ]

    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "request": request,
            "usuario": admin,
            "page_title": "Dashboard",
            "page_subtitle": "Visão geral rápida do painel EasyStore",
            "css_path": "css/dashboard.css",
            "active": "home",
            "total_produtos": total_produtos,
            "total_categorias": total_categorias,
            "total_usuarios": total_usuarios,
            "ativos_produtos": ativos_produtos,
            "vendas_grafico": vendas_grafico,
            "ultimas_vendas": ultimas_vendas,
        },
    )


@app.get("/admin/pos")
def admin_pos(
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin),
):
    produtos = (
        db.query(Produto)
        .filter(Produto.ativo == True, Produto.estoque_atual > 0)
        .order_by(Produto.nome)
        .all()
    )
    clientes = (
        db.query(Cliente)
        .filter(Cliente.ativo == True)
        .order_by(Cliente.nome)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "admin/pos.html",
        {
            "request": request,
            "usuario": admin,
            "produtos": produtos,
            "clientes": clientes,
            "desconto_associado": 10.0,
            "css_path": "css/pos.css",
            "active": "pos",
        },
    )


@app.get("/sobre-nos", response_class=HTMLResponse)
def sobre(request: Request):
    return templates.TemplateResponse(
        request,
        "sobre-nos/index.html",
        {"request": request},
    )
