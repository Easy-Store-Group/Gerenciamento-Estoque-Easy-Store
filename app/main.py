from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.auth import get_usuario_opcional, get_admin, get_operador
from app.database import get_db
from app.models.produto import Produto
from app.models.categoria import Categoria
from app.models.usuario import Usuario

from app.controllers import auth_controller
from app.controllers import admin_controller
from app.controllers import categoria_controller
from app.controllers import produto_controller
from app.controllers import movimentacao_controller

app = FastAPI(title="Sistema estoque")

# configurar o fastapi para servir os arquivos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates") 

# Incluir os routers dos controles
app.include_router(auth_controller.router)
app.include_router(admin_controller.router)
app.include_router(categoria_controller.router)
app.include_router(produto_controller.router)
app.include_router(venda_controller.router)
app.include_router(caixa_controller.router)
app.include_router(conquistas_controller.router)
app.include_router(movimentacao_controller.router)
app.include_router(movimentacao_controller.router)

# Tela inicial 
@app.get("/")
def home(request: Request,
         usuario =  Depends(get_usuario_opcional)
         ):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request, "usuario": usuario}
    )

@app.get("/admin")
def admin_dashboard(request: Request,
                    db: Session = Depends(get_db),
                    admin = Depends(get_admin)):
    total_produtos = db.query(Produto).count()
    total_categorias = db.query(Categoria).count()
    total_usuarios = db.query(Usuario).count()
    ativos_produtos = db.query(Produto).filter(Produto.ativo == True).count()

    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "request": request,
            "usuario": admin,
            "page_title": "Dashboard",
            "page_subtitle": "Visão geral rápida do painel EasyStore",
            "css_path": "css/admin.css",
            "active": "home",
            "total_produtos": total_produtos,
            "total_categorias": total_categorias,
            "total_usuarios": total_usuarios,
            "ativos_produtos": ativos_produtos,
        }
    )


@app.get("/admin/caixa")
def admin_caixa(request: Request, admin = Depends(get_admin)):
    return templates.TemplateResponse(
        request,
        "admin/dashboard-caixa.html",
        {"request": request}
    )


@app.get("/admin/pos")
def admin_pos(request: Request, admin = Depends(get_admin)):
    return templates.TemplateResponse(
        request,
        "admin/pos.html",
        {
            "request": request,
        }
    )


@app.get("/operador")
def operador_dashboard(request: Request,
                       db: Session = Depends(get_db),
                       operador = Depends(get_operador)):
    produtos = db.query(Produto).filter(Produto.ativo == True).order_by(Produto.nome).all()

    return templates.TemplateResponse(
        request,
        "operador/index.html",
        {
            "request": request,
            "usuario": operador,
            "page_title": "Painel do Operador",
            "page_subtitle": "Acompanhe produtos e mantenha o atendimento em dia.",
            "produtos": produtos,
        }
    )


@app.get("/perfil", response_class=HTMLResponse)
def perfil(request: Request):
    return templates.TemplateResponse(
        request,
        "perfil.html",
        {"request": request}
    )


@app.get("/sobre-nos", response_class=HTMLResponse)
def sobre(request: Request):
    return templates.TemplateResponse(
        request,
        "sobre-nos/index.html",
        {"request": request}
    )