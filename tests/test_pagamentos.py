from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.responses import RedirectResponse
from starlette.requests import Request
import json

from app.database import Base
from app.models.payment_schemas import PaymentMethod, PaymentItem, SalePaymentSummary
from app.services.payment_service import PaymentEngine, calcular_parcelas_credito
from app.services.pix_service import gerar_payload_pix, formatar_chave_pix
from app.controllers.pdv_controller import _pagamentos_do_admin, detalhe_venda, finalizar_venda
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.pagamento import Pagamento, PagamentoParcela
from app.models.usuario import Usuario


# 1. Pagamento 100% em Dinheiro
def test_pagamento_100_dinheiro():
    engine = PaymentEngine(sale_total=100.00)
    assert engine.pending_total == Decimal("100.00")
    assert not engine.is_completed

    item = engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("100.00"))
    assert item.method == PaymentMethod.DINHEIRO
    assert item.amount == Decimal("100.00")
    assert engine.paid_total == Decimal("100.00")
    assert engine.pending_total == Decimal("0.00")
    assert engine.is_completed

    summary = engine.get_summary()
    assert summary.sale_total == Decimal("100.00")
    assert summary.paid_total == Decimal("100.00")
    assert summary.pending_total == Decimal("0.00")
    assert summary.is_completed is True
    assert len(summary.payments) == 1


# 2. Pagamento 100% via Pix
def test_pagamento_100_pix():
    engine = PaymentEngine(sale_total=150.50)
    item = engine.add_payment(
        method=PaymentMethod.PIX,
        amount=Decimal("150.50"),
        pix_confirmed_manual=True,
    )

    assert item.method == PaymentMethod.PIX
    assert item.amount == Decimal("150.50")
    assert item.pix_confirmed_manual is True
    assert item.pix_payload is not None
    assert "br.gov.bcb.pix" in item.pix_payload
    assert engine.is_completed
    assert engine.pending_total == Decimal("0.00")


# 3. Pagamento combinado: Pix + Dinheiro (completando o total)
def test_pagamento_combinado_pix_e_dinheiro():
    engine = PaymentEngine(sale_total=200.00)
    
    # 1º pagamento Pix parcial
    item1 = engine.add_payment(
        method=PaymentMethod.PIX,
        amount=Decimal("80.00"),
        pix_confirmed_manual=True,
    )
    assert engine.pending_total == Decimal("120.00")
    assert not engine.is_completed

    # 2º pagamento preenche automaticamente com o saldo restante sugerido
    valor_sugerido = engine.sugerir_proximo_valor()
    assert valor_sugerido == Decimal("120.00")

    item2 = engine.add_payment(method=PaymentMethod.DINHEIRO, amount=valor_sugerido)
    assert engine.paid_total == Decimal("200.00")
    assert engine.pending_total == Decimal("0.00")
    assert engine.is_completed
    assert len(engine.payments) == 2


# 4. Pagamento combinado: Dinheiro + Cartão de Crédito Parcelado (verificando soma das parcelas)
def test_pagamento_combinado_dinheiro_e_credito_parcelado():
    engine = PaymentEngine(sale_total=150.00)

    # 1º método: Dinheiro
    engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("50.00"))
    assert engine.pending_total == Decimal("100.00")

    # 2º método: Cartão de Crédito em 3x
    item2 = engine.add_payment(
        method=PaymentMethod.CARTAO_CREDITO,
        amount=engine.pending_total,
        installments_count=3,
    )
    assert item2.installments_count == 3
    assert len(item2.installments_detail) == 3

    # Soma exata das parcelas deve ser R$ 100,00
    soma_parcelas = sum(d.amount for d in item2.installments_detail)
    assert soma_parcelas == Decimal("100.00")
    assert engine.is_completed


# 5. Pagamento 100% Cartão de Crédito Parcelado (1x a 12x)
def test_pagamento_100_cartao_credito_1x_a_12x():
    valor_total = Decimal("300.00")

    for parcelas in range(1, 13):
        engine = PaymentEngine(sale_total=valor_total)
        item = engine.add_payment(
            method=PaymentMethod.CARTAO_CREDITO,
            amount=valor_total,
            installments_count=parcelas,
        )
        assert item.installments_count == parcelas
        assert len(item.installments_detail) == parcelas
        soma = sum(d.amount for d in item.installments_detail)
        assert soma == valor_total
        assert engine.is_completed


# 6. Validação do código Copia e Cola do Pix (presença das tags TLV e chave formatada)
def test_validacao_codigo_copia_e_cola_pix():
    chave_original = "(55) 11 98297-4525"
    chave_formatada = formatar_chave_pix(chave_original)
    assert chave_formatada == "+5511982974525"

    payload = gerar_payload_pix(
        valor=Decimal("25.50"),
        chave=chave_original,
        nome_recebedor="EASY STORE",
        cidade_recebedor="SAO PAULO",
    )

    # Verificação das Tags TLV do Banco Central
    assert payload.startswith("000201")  # Tag 00: 01
    assert "26360014br.gov.bcb.pix0114+5511982974525" in payload  # Tag 26: Pix gui + chave
    assert "52040000" in payload  # Tag 52: Merchant Category
    assert "5303986" in payload   # Tag 53: BRL
    assert "540525.50" in payload  # Tag 54: Valor
    assert "5802BR" in payload     # Tag 58: Country Code
    assert "5910EASY STORE" in payload  # Tag 59: Merchant Name
    assert "6009SAO PAULO" in payload   # Tag 60: Merchant City
    assert "62070503***" in payload     # Tag 62: Additional Data (txid)
    assert "6304" in payload            # Tag 63: Checksum CRC16


# 7. Erro ao tentar pagar valor superior ao total pendente
def test_erro_ao_tentar_pagar_valor_superior_ao_pendente():
    engine = PaymentEngine(sale_total=100.00)

    # Tenta pagar mais que o total inicial
    with pytest.raises(ValueError, match="excede o saldo pendente"):
        engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("120.00"))

    # Paga R$ 60,00 e depois tenta pagar R$ 50,00 (saldo restante é R$ 40,00)
    engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("60.00"))
    with pytest.raises(ValueError, match="excede o saldo pendente"):
        engine.add_payment(method=PaymentMethod.PIX, amount=Decimal("50.00"))


# 8. Arredondamento exato de centavos nas parcelas (ex: R$ 10,00 em 6x = 4x de R$ 1,67 + 2x de R$ 1,66)
def test_arredondamento_exato_centavos_parcelas():
    # Cenário explícito da especificação: R$ 10,00 em 6x
    detalhes = calcular_parcelas_credito(Decimal("10.00"), 6)
    assert len(detalhes) == 6

    # 4 parcelas de 1.67 e 2 parcelas de 1.66
    valores = [d.amount for d in detalhes]
    assert valores == [
        Decimal("1.67"),
        Decimal("1.67"),
        Decimal("1.67"),
        Decimal("1.67"),
        Decimal("1.66"),
        Decimal("1.66"),
    ]
    assert sum(valores) == Decimal("10.00")

    # Outro exemplo de centavos: R$ 100,00 em 3x = 1x 33,34 + 2x 33,33
    detalhes_3x = calcular_parcelas_credito(Decimal("100.00"), 3)
    assert [d.amount for d in detalhes_3x] == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert sum(d.amount for d in detalhes_3x) == Decimal("100.00")


# 9. Bloqueio ao tentar adicionar o 3º método de pagamento
def test_bloqueio_terceiro_metodo_pagamento():
    engine = PaymentEngine(sale_total=100.00)
    engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("30.00"))
    engine.add_payment(method=PaymentMethod.PIX, amount=Decimal("30.00"))

    with pytest.raises(ValueError, match="no maximo 2 metodos de pagamento"):
        engine.add_payment(method=PaymentMethod.CARTAO_DEBITO, amount=Decimal("40.00"))



# 10. Finalização e persistência completa da venda com saldo pendente igual a zero
def test_finalizacao_e_persistencia_completa_da_venda():
    request = MagicMock()
    request.form = {
        "forma_pagamento_1": "dinheiro",
        "valor_pagamento_1": "40.00",
        "forma_pagamento_2": "pix",
        "valor_pagamento_2": "60.00",
    }

    produto = Produto(
        id=1,
        nome="Jogo Teste",
        preco=100.0,
        plataforma="PC",
        estoque_atual=10,
        ativo=True,
    )

    db = MagicMock()
    # Mock do retorno da query de produto
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = produto

    # Venda mock
    def mock_add(instancia):
        if isinstance(instancia, Venda):
            instancia.id = 42

    db.add.side_effect = mock_add

    response = finalizar_venda(
        request=request,
        carrinho_json='[{"produto_id": 1, "quantidade": 1}]',
        cliente_id=0,
        observacao="Venda teste com persistência",
        forma_pagamento_1="dinheiro",
        valor_pagamento_1=40.0,
        forma_pagamento_2="pix",
        valor_pagamento_2=60.0,
        pix_confirmado="true",
        db=db,
        usuario={"role": "admin", "id": 1},
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 302
    assert response.headers["location"] == "/pdv/venda/42?sucesso=ok"

    # Confirma que o commit foi executado com sucesso
    db.commit.assert_called_once()

    # Confirma que itens e pagamentos foram persistidos no db
    itens_adicionados = [call.args[0] for call in db.add.call_args_list]
    pagamentos_adicionados = [item for item in itens_adicionados if isinstance(item, Pagamento)]
    assert len(pagamentos_adicionados) == 2
    assert sum(p.valor for p in pagamentos_adicionados) == 100.0


@pytest.mark.parametrize(
    ("pagamentos", "credito_index", "valor_credito", "parcelas"),
    [
        (
            {"forma_pagamento": "cartao_credito", "valor_recebido": 1000.0, "parcelas_forma_1": 5},
            0, 1000.0, 5,
        ),
        (
            {
                "forma_pagamento_1": "pix", "valor_pagamento_1": 400.0,
                "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 600.0,
                "parcelas_forma_2": 3,
            },
            1, 600.0, 3,
        ),
        (
            {
                "forma_pagamento_1": "dinheiro", "valor_pagamento_1": 400.0,
                "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 600.0,
                "parcelas_forma_2": 3,
            },
            1, 600.0, 3,
        ),
        (
            {
                "forma_pagamento_1": "cartao_credito", "valor_pagamento_1": 600.0,
                "parcelas_forma_1": 3,
                "forma_pagamento_2": "cartao_debito", "valor_pagamento_2": 400.0,
            },
            0, 600.0, 3,
        ),
    ],
)
def test_pagamentos_admin_preservam_parcelamento_e_valores_divididos(
    pagamentos, credito_index, valor_credito, parcelas
):
    argumentos = {"forma_pagamento": None, "valor_recebido": None, **pagamentos}
    resultado = _pagamentos_do_admin(**argumentos, total_liquido=1000.0)

    quantidade_esperada = 1 if "forma_pagamento" in pagamentos else 2
    assert len(resultado) == quantidade_esperada
    credito = resultado[credito_index]
    assert credito["forma"] == "cartao_credito"
    assert credito["valor"] == valor_credito
    assert credito["numero_parcelas"] == parcelas
    assert credito["valor_parcela"] == round(valor_credito / parcelas, 2)
    assert credito["parcelado"] is (parcelas > 1)
    assert round(sum(pagamento["valor"] for pagamento in resultado), 2) == 1000.0


def test_credito_a_vista_e_centavos_sao_calculados_corretamente():
    a_vista = _pagamentos_do_admin(
        forma_pagamento="cartao_credito", valor_recebido=1000.0,
        total_liquido=1000.0, parcelas_forma_1=1,
    )[0]
    com_centavos = _pagamentos_do_admin(
        forma_pagamento="cartao_credito", valor_recebido=999.99,
        total_liquido=999.99, parcelas_forma_1=3,
    )[0]

    assert a_vista["parcelado"] is False
    assert a_vista["numero_parcelas"] == 1
    assert a_vista["valor_parcela"] == 1000.0
    assert com_centavos["valor"] == 999.99
    assert com_centavos["valor_parcela"] == 333.33


@pytest.mark.parametrize(
    ("valor", "quantidade"),
    [
        ("300.00", 3),
        ("600.00", 5),
        ("1200.00", 12),
        ("99.99", 3),
        ("249.90", 8),
        ("1099.97", 12),
    ],
)
def test_cenarios_solicitados_somam_exatamente_o_total_do_credito(valor, quantidade):
    parcelas = calcular_parcelas_credito(Decimal(valor), quantidade)

    assert len(parcelas) == quantidade
    assert sum((parcela.amount for parcela in parcelas), Decimal("0.00")) == Decimal(valor)
    assert [parcela.number for parcela in parcelas] == list(range(1, quantidade + 1))


@pytest.mark.parametrize(
    "pagamentos",
    [
        {
            "forma_pagamento_1": "pix", "valor_pagamento_1": 400.0,
            "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 599.0,
            "parcelas_forma_2": 3,
        },
        {
            "forma_pagamento_1": "pix", "valor_pagamento_1": 400.0,
            "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 0.0,
            "parcelas_forma_2": 3,
        },
        {
            "forma_pagamento_1": "pix", "valor_pagamento_1": 400.0,
            "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 600.0,
            "parcelas_forma_2": 13,
        },
    ],
)
def test_pagamentos_admin_rejeitam_divergencia_valor_credito_ou_parcelas_invalidas(pagamentos):
    with pytest.raises(ValueError):
        argumentos = {"forma_pagamento": None, "valor_recebido": None, **pagamentos}
        _pagamentos_do_admin(**argumentos, total_liquido=1000.0)


def test_seletores_de_parcelas_sao_enviados_no_formulario():
    from pathlib import Path

    template = Path("app/templates/admin/pos.html").read_text(encoding="utf-8")
    assert 'id="select-parcelas-forma-1" name="parcelas_forma_1"' in template
    assert 'id="select-parcelas-forma-2" name="parcelas_forma_2"' in template


@pytest.mark.parametrize(
    ("preco", "dados_pagamento", "esperado"),
    [
        (
            1000.0,
            {"forma_pagamento": "cartao_credito", "valor_recebido": 1000.0, "parcelas_forma_1": 5},
            [("cartao_credito", 1000.0, True, 5, 200.0)],
        ),
        (
            1000.0,
            {
                "forma_pagamento_1": "pix", "valor_pagamento_1": 400.0,
                "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 600.0,
                "parcelas_forma_2": 3,
            },
            [("pix", 400.0, False, 1, 400.0), ("cartao_credito", 600.0, True, 3, 200.0)],
        ),
        (
            1000.0,
            {
                "forma_pagamento_1": "dinheiro", "valor_pagamento_1": 400.0,
                "forma_pagamento_2": "cartao_credito", "valor_pagamento_2": 600.0,
                "parcelas_forma_2": 3,
            },
            [("dinheiro", 400.0, False, 1, 400.0), ("cartao_credito", 600.0, True, 3, 200.0)],
        ),
        (
            1000.0,
            {
                "forma_pagamento_1": "cartao_credito", "valor_pagamento_1": 600.0,
                "parcelas_forma_1": 3,
                "forma_pagamento_2": "cartao_debito", "valor_pagamento_2": 400.0,
            },
            [("cartao_credito", 600.0, True, 3, 200.0), ("cartao_debito", 400.0, False, 1, 400.0)],
        ),
        (
            999.99,
            {"forma_pagamento": "cartao_credito", "valor_recebido": 999.99, "parcelas_forma_1": 3},
            [("cartao_credito", 999.99, True, 3, 333.33)],
        ),
        (
            1000.0,
            {"forma_pagamento": "cartao_credito", "valor_recebido": 1000.0, "parcelas_forma_1": 1},
            [("cartao_credito", 1000.0, False, 1, 1000.0)],
        ),
        (
            1000.0,
            {"forma_pagamento": "cartao_credito", "valor_recebido": 1000.0, "parcelas_forma_1": 12},
            [("cartao_credito", 1000.0, True, 12, 83.33)],
        ),
    ],
)
def test_finalizar_venda_persiste_valores_e_parcelas_do_credito(
    monkeypatch, preco, dados_pagamento, esperado
):
    import app.controllers.pdv_controller as pdv_controller

    monkeypatch.setattr(pdv_controller, "verificar_status_pix", lambda: {"disponivel": True})
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        usuario = Usuario(nome="Admin teste", email="admin-parcelas@example.test", senha_hash="x", role="admin")
        produto = Produto(
            nome="Produto para teste de parcelas", preco=preco, plataforma="PC",
            estoque_atual=10, ativo=True,
        )
        db.add(usuario)
        db.add(produto)
        db.commit()

        response = finalizar_venda(
            request=MagicMock(),
            carrinho_json='[{"produto_id": %s, "quantidade": 1}]' % produto.id,
            cliente_id=0,
            observacao="Teste de persistência de parcelas",
            pix_confirmado="true" if any(v == "pix" for v in dados_pagamento.values()) else "false",
            db=db,
            usuario={"role": "admin", "id": usuario.id},
            **dados_pagamento,
        )

        assert isinstance(response, RedirectResponse)
        assert response.headers["location"].endswith("?sucesso=ok")
        venda_id = int(response.headers["location"].split("/pdv/venda/")[1].split("?")[0])
        venda_salva = db.query(Venda).filter(Venda.id == venda_id).one()
        pagamentos_salvos = db.query(Pagamento).filter(Pagamento.venda_id == venda_id).all()
        assert len(pagamentos_salvos) == len(esperado)
        assert round(sum(p.valor for p in pagamentos_salvos), 2) == venda_salva.total_liquido
        assert [
            (p.forma, round(p.valor, 2), p.parcelado, p.numero_parcelas, round(p.valor_parcela, 2))
            for p in pagamentos_salvos
        ] == esperado
        for pagamento in pagamentos_salvos:
            detalhes = db.query(PagamentoParcela).filter(
                PagamentoParcela.pagamento_id == pagamento.id
            ).order_by(PagamentoParcela.numero).all()
            if pagamento.forma == "cartao_credito" and pagamento.parcelado:
                assert len(detalhes) == pagamento.numero_parcelas
                assert [parcela.numero for parcela in detalhes] == list(
                    range(1, pagamento.numero_parcelas + 1)
                )
                assert sum((parcela.valor for parcela in detalhes), Decimal("0.00")) == Decimal(
                    str(pagamento.valor)
                ).quantize(Decimal("0.01"))
            else:
                assert detalhes == []
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_parcelas_persistem_e_comprovante_reconsulta_venda(monkeypatch):
    import app.controllers.pdv_controller as pdv_controller
    from app.main import app as application

    monkeypatch.setattr(pdv_controller, "verificar_status_pix", lambda: {"disponivel": True})
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        usuario = Usuario(nome="Admin comprovante", email="admin-comprovante@example.test", senha_hash="x", role="admin")
        produto = Produto(
            nome="Produto parcelado", preco=1000.0, plataforma="PC",
            estoque_atual=10, ativo=True,
        )
        db.add_all([usuario, produto])
        db.commit()

        response = finalizar_venda(
            request=MagicMock(),
            carrinho_json='[{"produto_id": %s, "quantidade": 1}]' % produto.id,
            cliente_id=0,
            observacao="Pix mais crédito",
            forma_pagamento_1="pix",
            valor_pagamento_1=400.0,
            forma_pagamento_2="cartao_credito",
            valor_pagamento_2=600.0,
            parcelas_forma_2=3,
            pix_confirmado="true",
            db=db,
            usuario={"role": "admin", "id": usuario.id},
        )
        assert response.status_code == 302
        venda_id = int(response.headers["location"].split("/pdv/venda/")[1].split("?")[0])

        db.expire_all()
        venda_salva = db.query(Venda).filter(Venda.id == venda_id).one()
        credito = next(p for p in venda_salva.pagamentos if p.forma == "cartao_credito")
        detalhes = db.query(PagamentoParcela).filter(
            PagamentoParcela.pagamento_id == credito.id
        ).order_by(PagamentoParcela.numero).all()
        assert credito.valor == 600.0
        assert credito.numero_parcelas == 3
        assert [(p.numero, p.valor) for p in detalhes] == [
            (1, Decimal("200.00")), (2, Decimal("200.00")), (3, Decimal("200.00")),
        ]
        assert sum((p.valor for p in detalhes), Decimal("0.00")) == Decimal("600.00")
        assert db.query(PagamentoParcela).filter(
            PagamentoParcela.pagamento_id == next(p for p in venda_salva.pagamentos if p.forma == "pix").id
        ).count() == 0

        request = Request({
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": f"/pdv/venda/{venda_id}",
            "raw_path": f"/pdv/venda/{venda_id}".encode(),
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "app": application,
        })
        comprovante = detalhe_venda(venda_id, request, db, {"role": "admin", "id": usuario.id})
        html = comprovante.body.decode("utf-8")
        assert "Cartão de crédito" in html
        assert "3x" in html
        assert "Total destinado ao cartão" not in html
        assert "Parcela 1/3" not in html and "Parcela 3/3" not in html
        assert "Vencimento da fatura" not in html
        assert "R$ 600.00" in html
        assert "R$ 200.00" not in html

        venda_antiga = Venda(
            usuario_id=usuario.id,
            total_bruto=1000.0,
            total_liquido=1000.0,
        )
        db.add(venda_antiga)
        db.flush()
        db.add(Pagamento(
            venda_id=venda_antiga.id,
            forma="cartao_credito",
            valor=1000.0,
            parcelado=True,
            numero_parcelas=5,
            valor_parcela=1000.0,
        ))
        db.commit()
        comprovante_antigo = detalhe_venda(
            venda_antiga.id, request, db, {"role": "admin", "id": usuario.id}
        )
        html_antigo = comprovante_antigo.body.decode("utf-8")
        assert "5x" in html_antigo
        assert "Parcela 1/5" not in html_antigo

        venda_a_vista = Venda(
            usuario_id=usuario.id,
            total_bruto=1000.0,
            total_liquido=1000.0,
        )
        db.add(venda_a_vista)
        db.flush()
        db.add(Pagamento(
            venda_id=venda_a_vista.id,
            forma="cartao_credito",
            valor=1000.0,
            parcelado=False,
            numero_parcelas=1,
            valor_parcela=1000.0,
        ))
        db.commit()
        comprovante_a_vista = detalhe_venda(
            venda_a_vista.id, request, db, {"role": "admin", "id": usuario.id}
        )
        assert "Parcelamento" not in comprovante_a_vista.body.decode("utf-8")
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.parametrize(
    ("forma", "valor_recebido", "parcelas"),
    [
        ("dinheiro", 1000.0, None),
        ("pix", None, None),
        ("cartao_credito", 1000.0, 1),
        ("cartao_credito", 1000.0, 12),
        ("cartao_debito", None, None),
    ],
)
def test_todas_as_formas_individuais_reais(forma, valor_recebido, parcelas):
    resultado = _pagamentos_do_admin(
        forma_pagamento=forma,
        valor_recebido=valor_recebido,
        total_liquido=1000.0,
        parcelas_forma_1=parcelas,
    )
    assert len(resultado) == 1
    assert resultado[0]["forma"] == forma
    assert round(resultado[0]["valor"], 2) == 1000.0


@pytest.mark.parametrize(
    ("forma1", "forma2", "valor1", "valor2"),
    [
        ("dinheiro", "pix", 400.0, 600.0),
        ("dinheiro", "cartao_credito", 400.0, 600.0),
        ("dinheiro", "cartao_debito", 400.0, 600.0),
        ("pix", "cartao_credito", 400.0, 600.0),
        ("pix", "cartao_debito", 400.0, 600.0),
        ("cartao_credito", "cartao_debito", 600.0, 400.0),
    ],
)
def test_combinacoes_reais_permitidas(forma1, forma2, valor1, valor2):
    resultado = _pagamentos_do_admin(
        forma_pagamento=None,
        valor_recebido=None,
        total_liquido=1000.0,
        forma_pagamento_1=forma1,
        valor_pagamento_1=valor1,
        forma_pagamento_2=forma2,
        valor_pagamento_2=valor2,
        parcelas_forma_1=3 if forma1 == "cartao_credito" else None,
        parcelas_forma_2=3 if forma2 == "cartao_credito" else None,
    )
    assert len(resultado) == 2
    assert round(sum(p["valor"] for p in resultado), 2) == 1000.0


def test_rejeita_soma_insuficiente_em_pagamento_combinado():
    with pytest.raises(ValueError, match="valor_insuficiente"):
        _pagamentos_do_admin(
            forma_pagamento=None,
            valor_recebido=None,
            total_liquido=1000.0,
            forma_pagamento_1="dinheiro",
            valor_pagamento_1=300.0,
            forma_pagamento_2="pix",
            valor_pagamento_2=600.0,
        )


def test_rejeita_soma_excedente_sem_dinheiro():
    with pytest.raises(ValueError, match="valor_insuficiente"):
        _pagamentos_do_admin(
            forma_pagamento=None,
            valor_recebido=None,
            total_liquido=1000.0,
            forma_pagamento_1="pix",
            valor_pagamento_1=600.0,
            forma_pagamento_2="cartao_debito",
            valor_pagamento_2=500.0,
        )


def test_finalizacao_rejeita_pix_sem_confirmacao():
    import app.controllers.pdv_controller as pdv_controller

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        usuario = Usuario(nome="Admin PIX", email="admin-pix@example.test", senha_hash="x", role="admin")
        produto = Produto(nome="PIX", preco=100.0, plataforma="PC", estoque_atual=5, ativo=True)
        db.add_all([usuario, produto])
        db.commit()

        response = pdv_controller.finalizar_venda(
            request=MagicMock(),
            carrinho_json=json.dumps([{"produto_id": produto.id, "quantidade": 1}]),
            cliente_id=0,
            observacao="",
            forma_pagamento="pix",
            valor_recebido=100.0,
            chave_idempotencia="pix-pendente",
            pix_confirmado="false",
            db=db,
            usuario={"role": "admin", "id": usuario.id},
        )
        assert response.headers["location"] == "/pdv?erro=pix_nao_confirmado"
        assert db.query(Venda).count() == 0
        assert db.query(Pagamento).count() == 0
        assert db.query(Produto).filter(Produto.id == produto.id).one().estoque_atual == 5
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_idempotencia_redireciona_sem_duplicar_venda(monkeypatch):
    import app.controllers.pdv_controller as pdv_controller

    monkeypatch.setattr(pdv_controller, "verificar_status_pix", lambda: {"disponivel": True})
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        usuario = Usuario(nome="Admin Idempotente", email="admin-idempotente@example.test", senha_hash="x", role="admin")
        produto = Produto(nome="Dinheiro", preco=100.0, plataforma="PC", estoque_atual=5, ativo=True)
        db.add_all([usuario, produto])
        db.commit()

        args = dict(
            request=MagicMock(),
            carrinho_json=json.dumps([{"produto_id": produto.id, "quantidade": 1}]),
            cliente_id=0,
            observacao="",
            forma_pagamento="dinheiro",
            valor_recebido=100.0,
            chave_idempotencia="venda-unica-001",
            pix_confirmado="false",
            db=db,
            usuario={"role": "admin", "id": usuario.id},
        )
        primeira = pdv_controller.finalizar_venda(**args)
        segunda = pdv_controller.finalizar_venda(**args)

        venda_id = int(primeira.headers["location"].split("/pdv/venda/")[1].split("?")[0])
        assert segunda.headers["location"] == f"/pdv/venda/{venda_id}?sucesso=ok"
        assert db.query(Venda).filter(Venda.chave_idempotencia == "venda-unica-001").count() == 1
        assert db.query(Pagamento).filter(Pagamento.venda_id == venda_id).count() == 1
        assert db.query(Produto).filter(Produto.id == produto.id).one().estoque_atual == 4
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_fluxo_pdv_separa_modal_de_processamento():
    from pathlib import Path

    pdv = Path("app/static/js/pdv.js").read_text(encoding="utf-8")
    template = Path("app/templates/admin/pos.html").read_text(encoding="utf-8")

    inicio_confirmar = pdv.index("confirmar.addEventListener")
    inicio_finalizar = pdv.index("async function finalizarVenda")
    trecho_confirmado = pdv[inicio_confirmar:inicio_finalizar]

    assert "estadoPagamentoPDV = 'processing'" in trecho_confirmado
    assert "await finalizarVenda()" in trecho_confirmado
    assert 'data-loading="local"' in template
    trecho_abertura = pdv[pdv.index("function abrirConfirmacaoPagamento"):inicio_finalizar]
    assert "EasyStoreLoading.begin" not in trecho_abertura


def test_pdv_preserva_carrinho_em_erro_e_limpa_somente_no_comprovante():
    from pathlib import Path

    pdv = Path("app/static/js/pdv.js").read_text(encoding="utf-8")

    assert "sessionStorage.setItem(PDV_CART_STORAGE_KEY" in pdv
    assert "sessionStorage.getItem(PDV_CART_STORAGE_KEY" in pdv
    assert "limparCarrinhoPersistidoPDV()" in pdv
    assert "respostaUrl.pathname.includes('/pdv/venda/')" in pdv
    assert "throw new Error(erro ? `Pagamento não concluído" in pdv
