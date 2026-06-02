CONQUISTAS_SEED = [
    {
        "nome": "Primeira Compra",
        "descricao": "Realize sua primeira compra na loja",
        "xp_requerido": 50,
        "desconto_reais": 5.0,
        "icon": "🎮"
    },
    {
        "nome": "Colecionador",
        "descricao": "Acumule 100 XP em compras",
        "xp_requerido": 100,
        "desconto_reais": 10.0,
        "icon": "🏆"
    },
    {
        "nome": "Gamer Casual",
        "descricao": "Atinja 500 XP",
        "xp_requerido": 500,
        "desconto_reais": 15.0,
        "icon": "🎯"
    },
    {
        "nome": "Gamer Pro",
        "descricao": "Atinja 1000 XP",
        "xp_requerido": 1000,
        "desconto_reais": 20.0,
        "icon": "⭐"
    },
    {
        "nome": "Lendário",
        "descricao": "Atinja 5000 XP",
        "xp_requerido": 5000,
        "desconto_reais": 50.0,
        "icon": "👑"
    },
    {
        "nome": "Comprador Leal",
        "descricao": "Realize 10 compras",
        "xp_requerido": 300,
        "desconto_reais": 12.0,
        "icon": "💎"
    },
]

def seed_conquistas(db):
    from app.models.conquista import Conquista

    for dados in CONQUISTAS_SEED:
        conquista_existe = db.query(Conquista).filter(
            Conquista.nome == dados["nome"]
        ).first()

        if not conquista_existe:
            conquista = Conquista(
                nome=dados["nome"],
                descricao=dados["descricao"],
                xp_requerido=dados["xp_requerido"],
                desconto_reais=dados["desconto_reais"],
                icon=dados["icon"]
            )
            db.add(conquista)

    db.commit()
