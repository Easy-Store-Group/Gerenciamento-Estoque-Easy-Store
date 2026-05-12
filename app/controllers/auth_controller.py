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

