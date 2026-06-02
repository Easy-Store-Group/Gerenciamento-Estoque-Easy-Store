from fastapi import APIRouter, Depends, Request, Form,status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import hash_senha, verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

templates = Jinja2Templates(directory="app/templates")

class RegisterRequest(BaseModel):
    nome: str
    email: str
    senha: str

class LoginRequest(BaseModel):
    email: str
    senha: str

@router.post("/register")
def registrar_usuario(dados: RegisterRequest, db: Session = Depends(get_db)):
    usuario_existe = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if usuario_existe:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    novo_usuario = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role="cliente",
        ativo=True,
        xp_total=0,
        nivel=1,
        moedas_resgate=0
    )

    db.add(novo_usuario)
    db.commit()

    return {"mensagem": "Usuário registrado com sucesso", "usuario_id": novo_usuario.id}

@router.post("/login-json")
def fazer_login_json(dados: LoginRequest, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()

    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")

    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário inativo")

    token_data = {
        "sub": usuario.email,
        "nome": usuario.nome,
        "id": usuario.id
    }
    token = criar_token(token_data)

    return {
        "usuario_id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "token": token
    }

# exibir tela de login
@router.get("/login")
def tela_login(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {'request': request}
    )

# exibir tela de cadastro
@router.get("/register")
def tela_register(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {'request': request}
    )

@router.post("/login")
def fazer_login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):

    usuario = db.query(Usuario).filter_by(email=email).first()

    senha_correta = usuario is not None and verificar_senha(senha, usuario.senha_hash)
    if not senha_correta:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"request": request, "erro": "E-mail ou senha incorretos.(Somente para administradores)"}
        )
    
    if not usuario.ativo:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"request": request, "erro": "usuario inativo!"}
        )

    token_data = {
        "sub": usuario.email,
        "nome": usuario.nome,
        "role": usuario.role,
        "id": usuario.id,
        }

    token = criar_token(token_data)

    response = RedirectResponse(url="/admin", status_code=302)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=3600,
        samesite="lax"
    )

    return response 

@router.get("/logout")
def sair():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response