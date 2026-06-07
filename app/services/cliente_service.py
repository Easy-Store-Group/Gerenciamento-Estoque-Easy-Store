from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.usuario import Usuario


def obter_ou_criar_cliente(db: Session, usuario_id: int) -> Cliente | None:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        return None

    cliente = db.query(Cliente).filter(Cliente.usuario_id == usuario.id).first()
    if cliente:
        return cliente

    cliente = db.query(Cliente).filter(Cliente.email == usuario.email).first()
    if cliente:
        cliente.usuario_id = usuario.id
        if not cliente.nome:
            cliente.nome = usuario.nome
        db.commit()
        db.refresh(cliente)
        return cliente

    cliente = Cliente(
        nome=usuario.nome,
        email=usuario.email,
        usuario_id=usuario.id,
        is_associado=False,
        ativo=True,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return cliente
