from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import hash_senha, verificar_senha, criar_token

router = APIRouter()

templates = Jinja2Templates(directory="app/templates")

#Rota de cadastro
@router.get("/cadastro")
def tela_cadastro(request: Request):
    return templates.TemplateResponse("cadastro.html", {"request": request})

#Exibir tela de login
@router.get("/login")
def tela_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# Criar o usuario no banco - cadastrar usuario
@router.post("/cadastro")
def cadastrar_usuario(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db),
):
    

 #Verificar se o e-mail está cadastrado
    usuario_existente = db.query(Usuario).filter_by(email=email).first()

    if usuario_existente:
        return templates.TemplateResponse(
            request,
            "auth/cadastro.html",
            {"request": request, "erro": "Este e-mail já está cadastrado"}
        )
    #Criar o novo usuario com senha hash
    novo_usuario = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha))  

    db.add(novo_usuario)
    db.commit()

    # Redirecionar para login após cadastro
    return  RedirectResponse(url="/auth/login?cadastro=ok",status_code=302)