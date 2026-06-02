from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.usuario import Usuario
from app.models.categoria import Categoria
from app.models.produto import Produto
from app.services.conquistas_seed import seed_conquistas
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def seed_database():
    db = SessionLocal()

    Base.metadata.create_all(bind=engine)

    # Seed de categorias
    categorias_data = [
        {"nome": "Consoles", "descricao": "Consoles de videogame"},
        {"nome": "Jogos", "descricao": "Jogos para diferentes plataformas"},
        {"nome": "Acessórios", "descricao": "Acessórios para consoles e periféricos"},
        {"nome": "Colecionáveis", "descricao": "Itens colecionáveis e edições especiais"},
    ]

    for cat_data in categorias_data:
        cat_existe = db.query(Categoria).filter(Categoria.nome == cat_data["nome"]).first()
        if not cat_existe:
            categoria = Categoria(**cat_data, ativo=True)
            db.add(categoria)
    db.commit()

    # Seed de usuários
    usuarios_data = [
        {"nome": "Admin", "email": "admin@easystroke.com", "role": "admin"},
        {"nome": "Vendedor", "email": "vendedor@easystore.com", "role": "operador"},
        {"nome": "João Gamer", "email": "joao@example.com", "role": "cliente"},
    ]

    for user_data in usuarios_data:
        user_existe = db.query(Usuario).filter(Usuario.email == user_data["email"]).first()
        if not user_existe:
            usuario = Usuario(
                nome=user_data["nome"],
                email=user_data["email"],
                senha_hash=pwd_context.hash("password123"),
                role=user_data["role"],
                ativo=True,
                xp_total=0,
                nivel=1,
                moedas_resgate=0
            )
            db.add(usuario)
    db.commit()

    # Seed de produtos
    categorias = db.query(Categoria).all()
    categoria_map = {c.nome: c for c in categorias}

    produtos_data = [
        {
            "nome": "PlayStation 5",
            "preco": 3999.90,
            "plataforma": "PS5",
            "descricao": "Console PlayStation 5 versão digital",
            "estoque_atual": 5,
            "estoque_minimo": 2,
            "categoria_id": categoria_map["Consoles"].id if "Consoles" in categoria_map else None
        },
        {
            "nome": "Xbox Series X",
            "preco": 4499.90,
            "plataforma": "Xbox",
            "descricao": "Console Xbox Series X",
            "estoque_atual": 3,
            "estoque_minimo": 1,
            "categoria_id": categoria_map["Consoles"].id if "Consoles" in categoria_map else None
        },
        {
            "nome": "Elden Ring",
            "preco": 299.90,
            "plataforma": "PS5/Xbox",
            "descricao": "Jogo Elden Ring para PS5 e Xbox",
            "estoque_atual": 15,
            "estoque_minimo": 5,
            "categoria_id": categoria_map["Jogos"].id if "Jogos" in categoria_map else None
        },
        {
            "nome": "DualSense PS5",
            "preco": 450.00,
            "plataforma": "PS5",
            "descricao": "Controle DualSense para PlayStation 5",
            "estoque_atual": 20,
            "estoque_minimo": 10,
            "categoria_id": categoria_map["Acessórios"].id if "Acessórios" in categoria_map else None
        },
        {
            "nome": "Fone Gamer Corsair",
            "preco": 549.90,
            "plataforma": "Multi",
            "descricao": "Fone gamer de alta qualidade",
            "estoque_atual": 8,
            "estoque_minimo": 3,
            "categoria_id": categoria_map["Acessórios"].id if "Acessórios" in categoria_map else None
        },
        {
            "nome": "Funko Pop Zelda",
            "preco": 89.90,
            "plataforma": "Colecionável",
            "descricao": "Figura colecionável Funko Pop de Zelda",
            "estoque_atual": 12,
            "estoque_minimo": 5,
            "categoria_id": categoria_map["Colecionáveis"].id if "Colecionáveis" in categoria_map else None
        },
    ]

    for prod_data in produtos_data:
        prod_existe = db.query(Produto).filter(Produto.nome == prod_data["nome"]).first()
        if not prod_existe:
            produto = Produto(**prod_data, ativo=True)
            db.add(produto)
    db.commit()

    # Seed de conquistas
    seed_conquistas(db)

    print("✅ Banco de dados seedado com sucesso!")
    db.close()

if __name__ == "__main__":
    seed_database()
