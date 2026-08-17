from app.database import Session
from app.models.categoria import Categoria
from app.models.produto import Produto

def seed_camisas():
    db = Session()
    try:
        # Verifica se a categoria já existe
        cat = db.query(Categoria).filter(Categoria.nome == 'Camisas').first()
        if not cat:
            cat = Categoria(nome='Camisas', descricao='Camisas e camisetas', ativo=True)
            db.add(cat)
            db.commit()
            db.refresh(cat)
            print(f"Categoria criada: {cat.nome} (id={cat.id})")
        else:
            print(f"Categoria já existe: {cat.nome} (id={cat.id})")

        # Cria produtos para os tamanhos se não existirem
        tamanhos = ['P','M','G','GG']
        created = 0
        for t in tamanhos:
            nome = f'Camisa {t}'
            p = db.query(Produto).filter(Produto.nome == nome).first()
            if not p:
                p = Produto(
                    nome=nome,
                    preco=49.90,
                    plataforma='Roupas',
                    descricao=f'Camisa tamanho {t}',
                    estoque_atual=10,
                    estoque_minimo=1,
                    ativo=True,
                    imagem_path='img/camisa-placeholder.png',
                    categoria_id=cat.id
                )
                db.add(p)
                created += 1
        if created:
            db.commit()
            print(f"{created} produtos de camisas criados.")
        else:
            print("Produtos de camisas já existem.")
    finally:
        db.close()


if __name__ == '__main__':
    seed_camisas()
