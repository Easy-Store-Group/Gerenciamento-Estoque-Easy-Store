NIVEL_THRESHOLDS = {
    1: 0,
    2: 100,
    3: 300,
    4: 600,
    5: 1000,
    10: 5000,
}

CONQUISTAS_AUTOMATICAS = {
    100: {"nome": "Primeira Compra", "desconto": 5},
    500: {"nome": "Gamer Casual", "desconto": 10},
    1000: {"nome": "Gamer Pro", "desconto": 20},
    5000: {"nome": "Lendário", "desconto": 50},
}

def calcular_nivel_from_xp(xp_total):
    nivel = 1
    for nivel_key in sorted(NIVEL_THRESHOLDS.keys(), reverse=True):
        if xp_total >= NIVEL_THRESHOLDS[nivel_key]:
            nivel = nivel_key
            break
    return nivel

def verificar_nova_conquista(xp_anterior, xp_novo):
    conquista = None
    for xp_requerido, dados in sorted(CONQUISTAS_AUTOMATICAS.items()):
        if xp_anterior < xp_requerido <= xp_novo:
            conquista = {
                "nome": dados["nome"],
                "desconto": dados["desconto"],
                "xp_requerido": xp_requerido
            }
    return conquista

def calcular_desconto_por_nivel(nivel):
    desconto_mapa = {
        5: 10,
        10: 20,
    }
    return desconto_mapa.get(nivel, 0)
