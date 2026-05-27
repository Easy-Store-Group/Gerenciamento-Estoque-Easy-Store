from fastapi import APIRouter, Depends, Request, Form,status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import hash_senha, verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

templates = Jinja2Templates(directory="app/templates")

# exibir tela de login 
@router.get("/login")
def tela_login(request: Request):
    return templates.TemplateResponse(
        request,
        "auth/login.html",
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

    response = RedirectResponse(url="/", status_code=302)

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