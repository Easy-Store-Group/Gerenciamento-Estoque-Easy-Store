from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from app.auth import get_usuario_opcional

from app.controllers import auth_controller
from app.controllers import admin_controller
from app.controllers import categoria_controller
from app.controllers import produto_controller

app = FastAPI(title="Sistema estoque")

# configurar o fastapi para servir os arquivos
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates") 

# Incluir os routers dos controles 
app.include_router(auth_controller.router)
app.include_router(admin_controller.router)
app.include_router(categoria_controller.router)
app.include_router(produto_controller.router)

# Tela inicial 
@app.get("/")
def home(request: Request,
         usuario =  Depends(get_usuario_opcional)
         ):
    if usuario is None:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"request": request}
        )
    
    # logado - exibir a tela principal com os dados do usuario
    return templates.TemplateResponse(
        request,
        "home.html",
        {"request": request, "usuario": usuario}
    )

@app.get("/sobre", response_class=HTMLResponse)
def sobre(request: Request):
    return templates.TemplateResponse(
        request,
        "sobre-nos/index.html",
        {"request": request}
    )