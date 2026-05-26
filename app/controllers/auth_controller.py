from fastapi import APIRouter, Depends, Request, Form,status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import hash_senha, verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

templates = Jinja2Templates(directory="app/templates")

# rota de cadastro 
@router.get("/cadastro")
def tela_cadastro(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/cadastro.html",
        {"request": request}
    )

# exibir tela de login 
@router.get("/login")
def tela_login(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {'request': request}
    )

# criar o usuario no banco - cadastrar usuario
@router.post("/cadastro")
def cadastrar_user(
    request: Request,
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    # verificar se o e-mail está cadastrado
    user_existente = db.query(Usuario).filter_by(email=email).first()

    if user_existente:
        # retorna o formulario com mensagem de erro
       return templates.TemplateResponse(
    request,
    "auth/cadastro.html",
    {"request": request, "erro": "este e-mail ja esta cadastrado"}
)
    
    # criar um novo usuario com senha hash
    novo_usuario = Usuario(
        nome=nome,
        email=email,
        senha_hash=hash_senha(senha)
    )
    # adicionar o novo usuario ao banco de dados
    db.add(novo_usuario)
    db.commit()
    # redirecionar para a tela de login
    return RedirectResponse(url="/auth/login?cadastro=ok", status_code=302)

# rota de login
@router.post("/login")
def fazer_login(
    request: Request,
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    # buscar o usuario pelo email
    usuario = db.query(Usuario).filter_by(email=email).first()

    # verificar a senha com bcrypt
    senha_correta = ( usuario is not None and (senha, usuario.senha_hash) )
    if not senha_correta:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"request": request, "erro": "email ou senha incorretos"}
        )
    
    if not usuario.ativo:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"request": request, "erro": "usuario inativo!"}
        )


    # Gere o token JWT
    token_data = {
        "sub": usuario.email,
        "nome": usuario.nome,
        "role": usuario.role,
        "id": usuario.id,
        }

    token = criar_token(token_data)
    # salvar o token em cookie HTTPOnly
    response = RedirectResponse(url="/", status_code=302)

    response.set_cookie(
        key="acess_token",
        value=token,
        httponly=True,
        max_age=3600,
        samesite="lax"
    )
 
    # redirecionar para a pagina inicial
    return response 

# rota de sair - logout
@router.get("/logout")
def sair():
    response = RedirectResponse(url="/auth/login", status_code=302)
    response.delete_cookie("acess_token")
    return response