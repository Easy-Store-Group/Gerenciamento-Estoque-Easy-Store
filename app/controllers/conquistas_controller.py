from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.conquista import Conquista
from app.models.usuario import Usuario

router = APIRouter(prefix="/api/conquistas", tags=["conquistas"])

@router.get("/")
def listar_conquistas(db: Session = Depends(get_db)):
    """Lista todas as conquistas disponíveis"""
    conquistas = db.query(Conquista).order_by(Conquista.xp_requerido).all()
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "descricao": c.descricao,
            "xp_requerido": c.xp_requerido,
            "desconto_reais": c.desconto_reais,
            "icon": c.icon
        }
        for c in conquistas
    ]

@router.get("/usuario/{usuario_id}")
def conquistas_usuario(usuario_id: int, db: Session = Depends(get_db)):
    """Retorna conquistas desbloqueadas do usuário"""
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    conquistadas = db.query(Conquista).filter(
        Conquista.xp_requerido <= usuario.xp_total
    ).order_by(Conquista.xp_requerido).all()

    proxima = db.query(Conquista).filter(
        Conquista.xp_requerido > usuario.xp_total
    ).order_by(Conquista.xp_requerido).first()

    return {
        "usuario_id": usuario_id,
        "xp_total": usuario.xp_total,
        "nivel": usuario.nivel,
        "conquistadas": [
            {
                "id": c.id,
                "nome": c.nome,
                "descricao": c.descricao,
                "icon": c.icon,
                "desbloqueada_em": c.xp_requerido
            }
            for c in conquistadas
        ],
        "proxima_conquista": {
            "nome": proxima.nome,
            "descricao": proxima.descricao,
            "xp_requerido": proxima.xp_requerido,
            "xp_faltante": proxima.xp_requerido - usuario.xp_total,
            "icon": proxima.icon
        } if proxima else None,
        "total_conquistadas": len(conquistadas)
    }

@router.post("/seed")
def seed_conquistas(db: Session = Depends(get_db)):
    """Seed de conquistas iniciais"""
    from app.services.conquistas_seed import seed_conquistas as seed_func
    seed_func(db)
    return {"mensagem": "Conquistas carregadas com sucesso"}
