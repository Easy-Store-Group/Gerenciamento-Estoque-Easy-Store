from app.database import Session, engine, Base
from app.models.usuario import Usuario
from app.auth import hash_senha

usuarios = [
    {
        "nome": "Zamboni",
        "email":"zamboni@admin.com",
        "senha":"zamb@1234",
        "role":"admin"
    },
]

def criar_usuario():
    db = Session()

    try:
        for usuario in usuarios:
            existentes = db.query(Usuario).filter_by(email = usuario["email"]).first()
            if existentes:
                print(f"já existe esse email {usuario["email"]} no banco")
                continue
            else:
                novo_admin = Usuario(
                    nome=usuario["nome"],
                    senha_hash=hash_senha(usuario["senha"]),
                    email=usuario["email"],
                    role=usuario["role"]
                    )
                db.add(novo_admin)
        db.commit()
    except Exception as erro:
        db.rollback()
        print(erro)
    finally:
        db.close()
criar_usuario()