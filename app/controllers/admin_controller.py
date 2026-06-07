# rotas acessiveis apenas por admin

from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import get_admin, hash_senha

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

templates = Jinja2Templates(directory="app/templates")

@router.get("/")
def listar_usuarios(request: Request, db: Session = Depends(get_db), admin = Depends(get_admin)):
    usuarios = db.query(Usuario).order_by(Usuario.nome).all()
    return templates.TemplateResponse(
        request,
        "admin/usuarios.html",
        {
            "request": request,
            "usuario": admin,
            "usuarios": usuarios,
            "page_title": "Usuários",
            "page_subtitle": "Gerencie acessos e status dos usuários",
            "css_path": "css/cadastros.css",
            "active": "usuarios",
        }
    )

@router.get("/novo")
def tela_novo_usuario(request: Request, admin = Depends(get_admin)):
    return templates.TemplateResponse(
        request,
        "admin/usuarios_form.html",
        {
            "request": request,
            "usuario": admin,
            "editando": None,
            "page_title": "Novo usuário",
            "page_subtitle": "Crie um novo operador ou administrador",
            "css_path": "css/cadastros.css",
            "active": "usuarios",
        }
    )

@router.post("/novo")
def criar_usuario(
    nome: str = Form(...), email: str = Form(...), senha: str = Form(...),
    role: str = Form("operador"), db: Session = Depends(get_db), admin = Depends(get_admin)
):
    novo_usuario = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), role=role, ativo=True)
    db.add(novo_usuario)
    db.commit()
    return RedirectResponse(url="/usuarios?criado=ok", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/{usuario_id}/editar")
def tela_editar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db), admin = Depends(get_admin)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    return templates.TemplateResponse(
        request,
        "admin/usuarios_form.html",
        {
            "request": request,
            "usuario": admin,
            "editando": usuario,
            "page_title": "Editar usuário",
            "page_subtitle": "Atualize perfil e status do usuário",
            "css_path": "css/cadastros.css",
            "active": "usuarios",
        }
    )

@router.post("/{usuario_id}/editar")
def editar_usuario(
    usuario_id: int,
    nome: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    senha: str = Form(None),
    db: Session = Depends(get_db),
    admin = Depends(get_admin)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    usuario.nome = nome
    usuario.email = email
    usuario.role = role

    if senha and senha.strip() != "":
        usuario.senha_hash = hash_senha(senha)

    db.commit()
    return RedirectResponse(url="/usuarios?editado=ok", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{usuario_id}/toggle-ativo")
def toggle_ativo(usuario_id: int, db: Session = Depends(get_db), admin = Depends(get_admin)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    usuario.ativo = not usuario.ativo
    db.commit()
    return RedirectResponse(url="/usuarios", status_code=status.HTTP_303_SEE_OTHER)
