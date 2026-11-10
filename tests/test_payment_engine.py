from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from fastapi.responses import RedirectResponse

from app.models.payment_schemas import PaymentMethod, PaymentItem, SalePaymentSummary
from app.services.payment_engine import PaymentEngine, calcular_parcelas_credito
from app.services.pix_service import gerar_payload_pix, formatar_chave_pix
from app.controllers.pdv_controller import finalizar_venda
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.pagamento import Pagamento


# 1. Pagamento integral em dinheiro
def test_pagamento_integral_em_dinheiro():
    engine = PaymentEngine(sale_total=120.00)
    assert engine.pending_total == Decimal("120.00")
    assert not engine.is_completed

    item = engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("120.00"))
    assert item.method == PaymentMethod.DINHEIRO
    assert item.amount == Decimal("120.00")
    assert engine.paid_total == Decimal("120.00")
    assert engine.pending_total == Decimal("0.00")
    assert engine.is_completed

    summary = engine.get_summary()
    assert summary.sale_total == Decimal("120.00")
    assert summary.paid_total == Decimal("120.00")
    assert summary.pending_total == Decimal("0.00")
    assert summary.is_completed is True
    assert len(summary.payments) == 1


# 2. Pagamento integral via Pix
def test_pagamento_integral_via_pix():
    engine = PaymentEngine(sale_total=175.80)
    item = engine.add_payment(
        method=PaymentMethod.PIX,
        amount=Decimal("175.80"),
        pix_confirmed_manual=True,
    )

    assert item.method == PaymentMethod.PIX
    assert item.amount == Decimal("175.80")
    assert item.pix_confirmed_manual is True
    assert item.pix_payload is not None
    assert "br.gov.bcb.pix" in item.pix_payload
    assert engine.is_completed
    assert engine.pending_total == Decimal("0.00")


# 3. Pagamento combinado de 2 métodos distintos (ex: Pix + Dinheiro)
def test_pagamento_combinado_dois_metodos_distintos():
    engine = PaymentEngine(sale_total=250.00)

    # 1º método: Pix parcial
    item1 = engine.add_payment(
        method=PaymentMethod.PIX,
        amount=Decimal("100.00"),
        pix_confirmed_manual=True,
    )
    assert engine.pending_total == Decimal("150.00")
    assert not engine.is_completed

    # Validação de bloqueio contra método repetido
    with pytest.raises(ValueError, match="Nao e permitido repetir o mesmo metodo"):
        engine.add_payment(method=PaymentMethod.PIX, amount=Decimal("50.00"))

    # 2º método distinto: Dinheiro completando o saldo restante exato
    valor_restante = engine.sugerir_proximo_valor()
    assert valor_restante == Decimal("150.00")

    item2 = engine.add_payment(method=PaymentMethod.DINHEIRO, amount=valor_restante)
    assert engine.paid_total == Decimal("250.00")
    assert engine.pending_total == Decimal("0.00")
    assert engine.is_completed
    assert len(engine.payments) == 2


# 4. Pagamento combinado de Dinheiro + Crédito parcelado
def test_pagamento_combinado_dinheiro_e_credito_parcelado():
    engine = PaymentEngine(sale_total=200.00)

    # 1º método: Dinheiro
    engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("80.00"))
    assert engine.pending_total == Decimal("120.00")

    # 2º método: Crédito em 4x
    item2 = engine.add_payment(
        method=PaymentMethod.CARTAO_CREDITO,
        amount=engine.pending_total,
        installments_count=4,
    )
    assert item2.installments_count == 4
    assert len(item2.installments_detail) == 4

    # Soma exata das parcelas deve totalizar R$ 120,00
    soma_parcelas = sum(d.amount for d in item2.installments_detail)
    assert soma_parcelas == Decimal("120.00")
    assert engine.is_completed


# 5. Parcelamento integral no cartão de crédito em até 12x
def test_parcelamento_integral_cartao_credito_ate_12x():
    valor_total = Decimal("600.00")

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


# 6. Validação do código Pix copia e cola e cálculo do CRC16
def test_validacao_codigo_pix_copia_e_cola_e_crc16():
    chave_raw = "(55) 11 98297-4525"
    chave_fmt = formatar_chave_pix(chave_raw)
    assert chave_fmt == "+5511982974525"

    payload = gerar_payload_pix(
        valor=Decimal("99.90"),
        chave=chave_raw,
        nome_recebedor="EASY STORE",
        cidade_recebedor="SAO PAULO",
    )

    # Tags TLV EMV / BR Code e CRC16
    assert payload.startswith("000201")
    assert "26360014br.gov.bcb.pix0114+5511982974525" in payload
    assert "52040000" in payload
    assert "5303986" in payload
    assert "540599.90" in payload
    assert "5802BR" in payload
    assert "5910EASY STORE" in payload
    assert "6009SAO PAULO" in payload
    assert "62070503***" in payload
    assert "6304" in payload
    # Payload termina com os 4 caracteres hex do CRC16
    crc_extraido = payload[-4:]
    assert len(crc_extraido) == 4
    assert crc_extraido.isalnum()


# 7. Erro ao lançar valor superior ao saldo restante
def test_erro_ao_lancar_valor_superior_ao_saldo_restante():
    engine = PaymentEngine(sale_total=100.00)

    # Tenta valor maior que o total
    with pytest.raises(ValueError, match="excede o saldo pendente"):
        engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("150.00"))

    # Paga R$ 70,00 e depois tenta pagar R$ 40,00 (saldo restante é R$ 30,00)
    engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("70.00"))
    with pytest.raises(ValueError, match="excede o saldo pendente"):
        engine.add_payment(method=PaymentMethod.PIX, amount=Decimal("40.00"))


# 8. Divisão exata de centavos nas parcelas sem erros de arredondamento
def test_divisao_exata_de_centavos_nas_parcelas():
    # R$ 100,00 em 3x = 1x R$ 33,34 + 2x R$ 33,33
    detalhes_3x = calcular_parcelas_credito(Decimal("100.00"), 3)
    assert len(detalhes_3x) == 3
    assert [d.amount for d in detalhes_3x] == [
        Decimal("33.34"),
        Decimal("33.33"),
        Decimal("33.33"),
    ]
    assert sum(d.amount for d in detalhes_3x) == Decimal("100.00")

    # R$ 10,00 em 6x = 4x R$ 1,67 + 2x R$ 1,66
    detalhes_6x = calcular_parcelas_credito(Decimal("10.00"), 6)
    assert [d.amount for d in detalhes_6x] == [
        Decimal("1.67"),
        Decimal("1.67"),
        Decimal("1.67"),
        Decimal("1.67"),
        Decimal("1.66"),
        Decimal("1.66"),
    ]
    assert sum(d.amount for d in detalhes_6x) == Decimal("10.00")


# 9. Bloqueio automático ao tentar adicionar mais de 2 métodos de pagamento
def test_bloqueio_automatico_ao_tentar_adicionar_mais_de_dois_metodos():
    engine = PaymentEngine(sale_total=100.00)
    engine.add_payment(method=PaymentMethod.DINHEIRO, amount=Decimal("40.00"))
    engine.add_payment(method=PaymentMethod.PIX, amount=Decimal("30.00"))

    with pytest.raises(ValueError, match="no maximo 2 metodos de pagamento"):
        engine.add_payment(method=PaymentMethod.CARTAO_DEBITO, amount=Decimal("30.00"))


# 10. Conclusão da venda com validação de saldo restante zerado
def test_conclusao_da_venda_com_saldo_restante_zerado():
    request = MagicMock()
    request.form = {
        "forma_pagamento_1": "dinheiro",
        "valor_pagamento_1": "50.00",
        "forma_pagamento_2": "pix",
        "valor_pagamento_2": "50.00",
    }

    produto = Produto(
        id=1,
        nome="Produto Teste",
        preco=100.0,
        plataforma="PC",
        estoque_atual=10,
        ativo=True,
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = produto

    def mock_add(instancia):
        if isinstance(instancia, Venda):
            instancia.id = 100

    db.add.side_effect = mock_add

    response = finalizar_venda(
        request=request,
        carrinho_json='[{"produto_id": 1, "quantidade": 1}]',
        cliente_id=0,
        observacao="Fechamento de venda com saldo zerado",
        forma_pagamento_1="dinheiro",
        valor_pagamento_1=50.0,
        forma_pagamento_2="pix",
        valor_pagamento_2=50.0,
        db=db,
        usuario={"role": "admin", "id": 1},
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 302
    assert response.headers["location"] == "/pdv/venda/100?sucesso=ok"

    db.commit.assert_called_once()
    itens_adicionados = [call.args[0] for call in db.add.call_args_list]
    pagamentos_adicionados = [item for item in itens_adicionados if isinstance(item, Pagamento)]
    assert len(pagamentos_adicionados) == 2
    assert sum(p.valor for p in pagamentos_adicionados) == 100.0
