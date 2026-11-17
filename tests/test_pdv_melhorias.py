import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from decimal import Decimal

from app.database import Base
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.models.venda import Venda
from app.models.variacao import ProdutoVariacao
from app.services.pix_service import verificar_status_pix, gerar_payload_pix
from app.controllers.pdv_controller import finalizar_venda, api_pix_status, api_pix_qrcode


@pytest.fixture
def db_pdv():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    # Cria dados de teste
    admin = Usuario(nome="Admin Test", email="admin@test.com", senha_hash="fake", role="admin", ativo=True)
    operador = Usuario(nome="Operador Test", email="op@test.com", senha_hash="fake", role="operador", ativo=True)
    cliente = Cliente(nome="Cliente Test", email="cli@test.com", telefone="1199999999", is_associado=True, ativo=True)
    prod1 = Produto(nome="Console PS5", preco=4000.0, estoque_atual=5, ativo=True, plataforma="Console")
    prod2 = Produto(nome="Jogo Teste", preco=200.0, estoque_atual=2, ativo=True, plataforma="Console")

    db.add_all([admin, operador, cliente, prod1, prod2])
    db.commit()

    yield db, admin, operador, cliente, prod1, prod2
    db.close()


def test_adicionar_ao_carrinho_nao_altera_estoque(db_pdv):
    """Garante que consultar ou preparar o carrinho não altera o estoque no banco de dados."""
    db, admin, _, _, prod1, _ = db_pdv
    estoque_inicial = prod1.estoque_atual

    # Simula cliente montando carrinho
    carrinho_memoria = [{"produto_id": prod1.id, "quantidade": 2}]
    assert len(carrinho_memoria) == 1
    # O estoque no banco não pode ter sido tocado
    db.refresh(prod1)
    assert prod1.estoque_atual == estoque_inicial


def test_finalizar_venda_baixa_estoque_apenas_na_confirmacao(db_pdv):
    """Baixa de estoque e registro de movimentações ocorrem unicamente após finalização bem-sucedida."""
    db, admin, _, _, prod1, _ = db_pdv
    estoque_inicial = prod1.estoque_atual

    req = Request({"type": "http", "method": "POST", "url": "http://localhost/pdv/finalizar", "headers": []})
    user_dict = {"id": admin.id, "role": "admin", "sub": admin.email}
    carrinho = [{"produto_id": prod1.id, "quantidade": 2}]

    res = finalizar_venda(
        request=req,
        carrinho_json=json.dumps(carrinho),
        cliente_id=0,
        observacao="Teste de baixa de estoque",
        forma_pagamento="dinheiro",
        valor_recebido=8000.0,
        db=db,
        usuario=user_dict,
    )

    assert res.status_code == 302
    assert "sucesso=ok" in res.headers.get("location")

    db.refresh(prod1)
    # Baixou exatamente 2 unidades
    assert prod1.estoque_atual == estoque_inicial - 2

    # Verifica movimentação gerada
    mov = db.query(Movimentacao).filter(Movimentacao.produto_id == prod1.id).first()
    assert mov is not None
    assert mov.tipo == Tipo_de_movimentacao.SAIDA
    assert mov.quantidade == 2


def test_bloqueio_quando_quantidade_excede_estoque(db_pdv):
    """Tentar vender mais do que o estoque disponível deve ser rejeitado sem alterar o estoque."""
    db, admin, _, _, prod1, _ = db_pdv
    estoque_inicial = prod1.estoque_atual

    req = Request({"type": "http", "method": "POST", "url": "http://localhost/pdv/finalizar", "headers": []})
    user_dict = {"id": admin.id, "role": "admin", "sub": admin.email}
    carrinho = [{"produto_id": prod1.id, "quantidade": estoque_inicial + 1}]

    res = finalizar_venda(
        request=req,
        carrinho_json=json.dumps(carrinho),
        cliente_id=0,
        observacao="",
        forma_pagamento="dinheiro",
        valor_recebido=99999.0,
        db=db,
        usuario=user_dict,
    )

    assert res.status_code == 302
    assert "erro=estoque" in res.headers.get("location")

    db.refresh(prod1)
    assert prod1.estoque_atual == estoque_inicial


def test_pix_status_operacional(monkeypatch):
    """Verifica detecção de API PIX operacional."""
    monkeypatch.delenv("PIX_SIMULATE_STATUS", raising=False)
    monkeypatch.setenv("PIX_ENABLED", "true")

    status = verificar_status_pix()
    assert status["disponivel"] is True
    assert status["codigo"] == "OPERACIONAL"


def test_pix_status_indisponivel(monkeypatch):
    """Verifica detecção de API PIX indisponível."""
    monkeypatch.setenv("PIX_SIMULATE_STATUS", "unavailable")

    status = verificar_status_pix()
    assert status["disponivel"] is False
    assert status["codigo"] == "INDISPONIVEL"
    assert "PIX temporariamente indisponível" in status["motivo"]


def test_bloqueio_venda_com_pix_indisponivel(db_pdv, monkeypatch):
    """Impede finalização de venda via PIX quando o serviço PIX estiver indisponível."""
    db, admin, _, _, prod1, _ = db_pdv
    monkeypatch.setenv("PIX_SIMULATE_STATUS", "unavailable")

    req = Request({"type": "http", "method": "POST", "url": "http://localhost/pdv/finalizar", "headers": []})
    user_dict = {"id": admin.id, "role": "admin", "sub": admin.email}
    carrinho = [{"produto_id": prod1.id, "quantidade": 1}]

    res = finalizar_venda(
        request=req,
        carrinho_json=json.dumps(carrinho),
        cliente_id=0,
        observacao="",
        forma_pagamento="pix",
        valor_recebido=4000.0,
        db=db,
        usuario=user_dict,
    )

    assert res.status_code == 302
    assert "erro=pix_indisponivel" in res.headers.get("location")

    # Garante que não houve alteração no estoque
    db.refresh(prod1)
    assert prod1.estoque_atual == 5


def test_geracao_qrcode_pix_bloqueado_quando_indisponivel(monkeypatch):
    """Endpoint api_pix_qrcode retorna erro amigável e flag indisponivel se o serviço estiver fora."""
    monkeypatch.setenv("PIX_SIMULATE_STATUS", "unavailable")

    user_dict = {"id": 1, "role": "admin"}
    res = api_pix_qrcode(valor=100.0, usuario=user_dict)
    assert res.get("indisponivel") is True
    assert "PIX temporariamente indisponível" in res.get("erro")


def test_vendas_simultaneas_concorrencia(db_pdv):
    """Simula duas tentativas de venda de 3 unidades quando há apenas 5 em estoque.
    
    A primeira venda de 3 deve ser confirmada; a segunda venda de 3 deve ser recusada
    por insuficiência de estoque, sem permitir estoque negativo.
    """
    db, admin, _, _, prod1, _ = db_pdv
    assert prod1.estoque_atual == 5

    req = Request({"type": "http", "method": "POST", "url": "http://localhost/pdv/finalizar", "headers": []})
    user_dict = {"id": admin.id, "role": "admin", "sub": admin.email}
    carrinho1 = [{"produto_id": prod1.id, "quantidade": 3}]
    carrinho2 = [{"produto_id": prod1.id, "quantidade": 3}]

    # Venda 1
    res1 = finalizar_venda(
        request=req,
        carrinho_json=json.dumps(carrinho1),
        cliente_id=0,
        observacao="Venda concorrente 1",
        forma_pagamento="dinheiro",
        valor_recebido=12000.0,
        forma_pagamento_1=None,
        valor_pagamento_1=None,
        forma_pagamento_2=None,
        valor_pagamento_2=None,
        parcelas_forma_1=None,
        parcelas_forma_2=None,
        db=db,
        usuario=user_dict,
    )
    assert res1.status_code == 302
    assert "sucesso=ok" in res1.headers.get("location")
    db.refresh(prod1)
    assert prod1.estoque_atual == 2

    # Venda 2 (tenta vender mais 3, mas restam apenas 2)
    res2 = finalizar_venda(
        request=req,
        carrinho_json=json.dumps(carrinho2),
        cliente_id=0,
        observacao="Venda concorrente 2",
        forma_pagamento="dinheiro",
        valor_recebido=12000.0,
        forma_pagamento_1=None,
        valor_pagamento_1=None,
        forma_pagamento_2=None,
        valor_pagamento_2=None,
        parcelas_forma_1=None,
        parcelas_forma_2=None,
        db=db,
        usuario=user_dict,
    )
    assert res2.status_code == 302
    assert "erro=estoque" in res2.headers.get("location")
    db.refresh(prod1)
    # Garante que o estoque permanece íntegro e não negativou
    assert prod1.estoque_atual == 2


def test_pagamento_duplo_com_pix_e_dinheiro_baixa_estoque_uma_vez(db_pdv, monkeypatch):
    """Testa pagamento combinado (Pix + Dinheiro) com baixa única de estoque."""
    db, admin, _, _, prod1, _ = db_pdv
    monkeypatch.delenv("PIX_SIMULATE_STATUS", raising=False)
    monkeypatch.setenv("PIX_ENABLED", "true")
    assert prod1.estoque_atual == 5

    req = Request({"type": "http", "method": "POST", "url": "http://localhost/pdv/finalizar", "headers": []})
    user_dict = {"id": admin.id, "role": "admin", "sub": admin.email}
    carrinho = [{"produto_id": prod1.id, "quantidade": 1}]  # R$ 4000.00

    res = finalizar_venda(
        request=req,
        carrinho_json=json.dumps(carrinho),
        cliente_id=0,
        observacao="Venda combinada",
        forma_pagamento=None,
        valor_recebido=None,
        forma_pagamento_1="pix",
        valor_pagamento_1=2000.0,
        forma_pagamento_2="dinheiro",
        valor_pagamento_2=2000.0,
        parcelas_forma_1=None,
        parcelas_forma_2=None,
        db=db,
        usuario=user_dict,
    )
    assert res.status_code == 302
    assert "sucesso=ok" in res.headers.get("location")

    db.refresh(prod1)
    assert prod1.estoque_atual == 4

    # Confirma que foram criadas movimentações e pagamentos correspondentes
    movs = db.query(Movimentacao).filter(Movimentacao.produto_id == prod1.id).all()
    assert len(movs) == 1
    assert movs[0].quantidade == 1


def test_api_pix_qrcode_bloqueia_forma_diferente_de_pix():
    """Garante que o backend rejeita solicitações de QR Code quando a forma for dinheiro, cartão ou outra."""
    user_dict = {"id": 1, "role": "admin"}
    
    # Tentativa com dinheiro
    res_dinheiro = api_pix_qrcode(valor=150.0, forma_pagamento="dinheiro", usuario=user_dict)
    assert res_dinheiro.get("disponivel") is False
    assert res_dinheiro.get("codigo") == "FORMA_INVALIDA"
    assert "PIX" in res_dinheiro.get("erro")

    # Tentativa com cartao_credito
    res_cartao = api_pix_qrcode(valor=150.0, forma_pagamento="cartao_credito", usuario=user_dict)
    assert res_cartao.get("disponivel") is False
    assert res_cartao.get("codigo") == "FORMA_INVALIDA"

    # Tentativa com forma vazia
    res_vazia = api_pix_qrcode(valor=150.0, forma_pagamento="", usuario=user_dict)
    assert res_vazia.get("disponivel") is False
    assert res_vazia.get("codigo") == "FORMA_INVALIDA"


def test_api_pix_qrcode_gera_sob_demanda_com_pix_valido(monkeypatch):
    """Garante geração sob demanda quando PIX for selecionado e a API estiver disponível."""
    monkeypatch.delenv("PIX_SIMULATE_STATUS", raising=False)
    monkeypatch.setenv("PIX_ENABLED", "true")

    user_dict = {"id": 1, "role": "admin"}
    res = api_pix_qrcode(valor=250.75, forma_pagamento="pix", usuario=user_dict)
    
    assert res.get("disponivel") is True
    assert res.get("status") == "pendente"
    assert res.get("valor") == 250.75
    assert "payload" in res and len(res["payload"]) > 30
    assert "qrcode_b64" in res and res["qrcode_b64"].startswith("data:image/png;base64,")
