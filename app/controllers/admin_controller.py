# rotas acessiveis apenas por admin

from fastapi import APIRouter, Depends, Request, Form,status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.auth import get_admin,hash_senha

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

templates = Jinja2Templates(directory="app/templates")

# exibir os usuarios do sistema
@router.get("/")
def listar_usuarios(request: Request,
                    db: Session = Depends(get_db),
                    admin = Depends(get_admin)# Bloqueia o acesso para usuarios que nao sejam admin
                    ):
    # buscar os usuarios no banco
    usuarios = db.query(Usuario).order_by(Usuario.nome).all()
    return templates.TemplateResponse(
        request,
        "usuarios/index.html",
        {"request": request,
         "admin": admin,
         "usuarios": usuarios}
    )


# Exibir os usuários do sistema
@router.get("/")
def listar_usuarios(request: Request, db: Session = Depends(get_db), admin = Depends(get_admin)):
    usuarios = db.query(Usuario).order_by(Usuario.nome).all()
    return templates.TemplateResponse(
        request, "usuarios/index.html", {"request": request, "admin": admin, "usuarios": usuarios}
    )

# Tela para criar novo usuário
@router.get("/novo")
def tela_novo_usuario(request: Request, admin = Depends(get_admin)):
    return templates.TemplateResponse(
        request, "usuarios/criar.html", {"request": request, "admin": admin}
    )

# Processar os dados e salvar o novo usuário
@router.post("/novo")
def criar_usuario(
    nome: str = Form(...), email: str = Form(...), senha: str = Form(...),
    role: str = Form("user"), db: Session = Depends(get_db), admin = Depends(get_admin)
):
    novo_usuario = Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), role=role, ativo=True)
    db.add(novo_usuario)
    db.commit()
    return RedirectResponse(url="/usuarios?criado=ok", status_code=status.HTTP_303_SEE_OTHER)

# Tela de edição mapeada conforme o index.html (/usuarios/{id}/editar)
@router.get("/{usuario_id}/editar")
def tela_editar_usuario(usuario_id: int, request: Request, db: Session = Depends(get_db), admin = Depends(get_admin)):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    return templates.TemplateResponse(
        request, "usuarios/criar.html", {"request": request, "admin": admin, "usuario": usuario}
    )

# Salvar as alterações da edição
@router.post("/{usuario_id}/editar")
def editar_usuario(
    usuario_id: int, nome: str = Form(...), email: str = Form(...), role: str = Form(...),
    db: Session = Depends(get_db), admin = Depends(get_admin)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    usuario.nome, usuario.email, usuario.role = nome, email, role
    db.commit()
    return RedirectResponse(url="/usuarios?editado=ok", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/{usuario_id}/toggle-ativo")
def toggle_ativo(usuario_id: int, db: Session = Depends(get_db), admin = Depends(get_admin)):
    # 1. Busca o usuário que você clicou no banco de dados
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    # 2. Faz a inversão do status:
    # Se usuario.ativo for True, vira False. Se for False, vira True.
    usuario.ativo = not usuario.ativo
    
    # 3. Salva a alteração definitiva no banco
    db.commit()
    
    # 4. Atualiza a página para mostrar o novo status
    return RedirectResponse(url="/usuarios", status_code=status.HTTP_303_SEE_OTHER)

# Salvar as alterações da edição (Incluindo alteração opcional de senha)
@router.post("/{usuario_id}/editar")
def editar_usuario(
    usuario_id: int, 
    nome: str = Form(...), 
    email: str = Form(...), 
    role: str = Form(...),
    senha: str = Form(None), # Recebe a senha como opcional (None por padrão)
    db: Session = Depends(get_db), 
    admin = Depends(get_admin)
):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    
    # Atualiza os dados básicos
    usuario.nome = nome
    usuario.email = email
    usuario.role = role
    
    # Se o admin digitou uma nova senha, gera o hash e atualiza
    if senha and senha.strip() != "":
        usuario.senha = hash_senha(senha)
        
    db.commit()
    return RedirectResponse(url="/usuarios?editado=ok", status_code=status.HTTP_303_SEE_OTHER)