from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi.responses import RedirectResponse

from app.models.payment_schemas import PaymentMethod, PaymentItem, SalePaymentSummary
from app.services.payment_service import PaymentEngine, calcular_parcelas_credito
from app.services.pix_service import gerar_payload_pix, formatar_chave_pix
from app.controllers.pdv_controller import _pagamentos_do_admin, finalizar_venda
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.pagamento import Pagamento


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
