from fastapi import APIRouter, Depends, Request, Form,status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import bcrypt

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import hash_senha, verificar_senha, criar_token

router = APIRouter(prefix="/auth", tags=["Autenticação"])

templates = Jinja2Templates(directory="app/templates")


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
    senha_correta = ( usuario is not None and bcrypt.checkpw(senha.encode(), usuario.senha_hash.encode()) )
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
        key="access_token",
        value=token,
        httponly=True,
        max_age=3600,
        samesite="lax"
    )
 
    # redirecionar para a pagina inicial
    return response 
