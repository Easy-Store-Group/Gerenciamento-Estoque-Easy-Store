from fastapi import APIRouter, Depends, Request, Form,status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
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

def _criar_conta_cliente(
    db: Session,
    nome: str,
    email: str,
    senha: str,
    telefone: str = "",
) -> Usuario:
    usuario_existe = db.query(Usuario).filter(Usuario.email == email).first()
    if usuario_existe:
        raise ValueError("Email já cadastrado")

    novo_usuario = Usuario(
        nome=nome.strip(),
        email=email.strip().lower(),
        senha_hash=hash_senha(senha),
        role="cliente",
        ativo=True,
        xp_total=0,
        nivel=1,
        moedas_resgate=0,
    )
    db.add(novo_usuario)
    db.flush()

    db.add(Cliente(
        nome=novo_usuario.nome,
        email=novo_usuario.email,
        telefone=telefone.strip() or None,
        usuario_id=novo_usuario.id,
        is_associado=False,
        ativo=True,
    ))
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


def _login_response(usuario: Usuario, destino: str) -> RedirectResponse:
    token_data = {
        "sub": usuario.email,
        "nome": usuario.nome,
        "role": usuario.role,
        "id": usuario.id,
    }
    token = criar_token(token_data)
    response = RedirectResponse(url=destino, status_code=302)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=3600,
        samesite="lax",
    )
    return response


@router.post("/api/register")
def registrar_usuario_api(dados: RegisterRequest, db: Session = Depends(get_db)):
    try:
        novo_usuario = _criar_conta_cliente(db, dados.nome, dados.email, dados.senha)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"mensagem": "Usuário registrado com sucesso", "usuario_id": novo_usuario.id}


@router.post("/register")
def registrar_usuario(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    telefone: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        novo_usuario = _criar_conta_cliente(db, nome, email, senha, telefone)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"request": request, "erro": str(exc)},
            status_code=400,
        )

    return _login_response(novo_usuario, "/cliente")

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
            {"request": request, "erro": "E-mail ou senha incorretos."}
        )
    
    if not usuario.ativo:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"request": request, "erro": "Usuário inativo."}
        )

    if usuario.role == "admin":
        destino = "/admin"
    elif usuario.role == "operador":
        destino = "/pdv"
    elif usuario.role == "cliente":
        destino = "/cliente"
    else:
        destino = "/"

    return _login_response(usuario, destino)

@router.get("/logout")
def sair():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("access_token")
    return response