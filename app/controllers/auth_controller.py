from fastapi import APIRouter, Depends, Request, Form,status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.models.venda import Venda
from app.database import get_db
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.auth import hash_senha, verificar_senha, criar_token, get_usuario_opcional
from app.auth import criar_token_personalizado, decodificar_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

templates = Jinja2Templates(directory="app/templates")

class RegisterRequest(BaseModel):
    nome: str
    email: str
    senha: str
    plano_premium: bool = False

class LoginRequest(BaseModel):
    email: str
    senha: str

def _criar_conta_cliente(
    db: Session,
    nome: str,
    email: str,
    senha: str,
    telefone: str = "",
    plano_premium: bool = False,
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
        is_associado=plano_premium,
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
        novo_usuario = _criar_conta_cliente(
            db,
            dados.nome,
            dados.email,
            dados.senha,
            plano_premium=dados.plano_premium,
        )
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
    plano_premium: bool = Form(False),
    db: Session = Depends(get_db),
):
    try:
        novo_usuario = _criar_conta_cliente(db, nome, email, senha, telefone, plano_premium)
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

@router.get("/produtos")
def tela_produtos_publicos(
    request: Request,
    categoria_id: int = 0,
    busca: str = "",
    db: Session = Depends(get_db),
    usuario = Depends(get_usuario_opcional),
):
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

    return templates.TemplateResponse(
        request,
        "produtos_publicos.html",
        {
            "request": request,
            "usuario": usuario,
            "produtos": produtos,
            "categorias": categorias,
            "categoria_id": categoria_id,
            "busca": busca,
        },
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


# Esqueci senha - exibir formulário para enviar email
@router.get("/forgot")
def tela_esqueci_senha(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/forgot.html",
        {"request": request},
    )


# Recebe email e gera token de reset (em vez de enviar email, exibimos link para desenvolvimento)
@router.post("/forgot")
def enviar_token_reset(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        return templates.TemplateResponse(
            request,
            "auth/forgot.html",
            {"request": request, "mensagem": "Se o e-mail estiver cadastrado, você receberá instruções."},
        )

    token_data = {"sub": usuario.email, "action": "reset_password"}
    # token curto: 20 minutos
    token = criar_token_personalizado(token_data, minutos=20)

    reset_link = f"/auth/reset-password?token={token}"

    # Para ambiente de produção aqui você enviaria um e-mail com o link.
    return templates.TemplateResponse(
        request,
        "auth/forgot.html",
        {"request": request, "mensagem": "Link de reset gerado abaixo (em produção, seria enviado por e-mail)", "reset_link": reset_link},
    )


@router.get("/reset-password")
def tela_reset_senha(request: Request, token: str = ""):
    return templates.TemplateResponse(
        request,
        "auth/reset_password.html",
        {"request": request, "token": token},
    )


@router.post("/reset-password")
def resetar_senha(
    request: Request,
    token: str = Form(...),
    nova_senha: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = decodificar_token(token)
    except Exception:
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {"request": request, "erro": "Token inválido ou expirado."},
        )

    if payload.get("action") != "reset_password":
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {"request": request, "erro": "Token inválido."},
        )

    email = payload.get("sub")
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario:
        return templates.TemplateResponse(
            request,
            "auth/reset_password.html",
            {"request": request, "erro": "Usuário não encontrado."},
        )

    usuario.senha_hash = hash_senha(nova_senha)
    db.add(usuario)
    db.commit()

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"request": request, "mensagem": "Senha alterada com sucesso. Faça login."},
    )
