import math

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.auth import get_admin

router = APIRouter(prefix="/clientes", tags=["Clientes"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def listar_clientes(
    request: Request,
    busca: str = "",
    ativo: int = -1,  # -1 = todos, 0 = inativos, 1 = ativos
    ordenar: str = "nome",  # campo para ordenar
    ordem: str = "asc",  # asc ou desc
    pagina: int = 1,
    por_pagina: int = 10,
    db: Session = Depends(get_db),
    usuario=Depends(get_admin),
):
    """Listagem administrativa de clientes com busca, filtro por ativo e ordenação."""

    query = db.query(Cliente)

    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        query = query.filter(
            (Cliente.nome.ilike(termo)) | (Cliente.email.ilike(termo)) | (Cliente.telefone.ilike(termo))
        )

    if ativo in (0, 1):
        query = query.filter(Cliente.ativo == bool(ativo))

    # Ordenação segura: permita apenas campos conhecidos
    ordenacao_mapping = {
        "nome": Cliente.nome,
        "email": Cliente.email,
        "criado_em": Cliente.criado_em,
    }

    coluna = ordenacao_mapping.get(ordenar, Cliente.nome)
    if ordem.lower() == "desc":
        query = query.order_by(coluna.desc())
    else:
        query = query.order_by(coluna)

    total = query.count()
    por_pagina = min(max(por_pagina, 1), 50)
    total_paginas = math.ceil(total / por_pagina) if total else 1
    pagina = min(max(pagina, 1), total_paginas)

    clientes = query.offset((pagina - 1) * por_pagina).limit(por_pagina).all()

    return templates.TemplateResponse(
        "admin/clientes.html",
        {
            "request": request,
            "usuario": usuario,
            "clientes": clientes,
            "busca": busca,
            "ativo": ativo,
            "ordenar": ordenar,
            "ordem": ordem,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_paginas": total_paginas,
            "total": total,
            "page_title": "Clientes",
            "page_subtitle": "Gerencie clientes cadastrados",
            "css_path": "css/cadastros.css",
            "active": "clientes",
        },
    )
