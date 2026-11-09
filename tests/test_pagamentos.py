from unittest.mock import MagicMock



import pytest
from fastapi.responses import RedirectResponse

from app.controllers.pdv_controller import (
    _pagamentos_do_admin, calcular_parcelas_cartao, finalizar_venda
)
from app.models.produto import Produto


def test_pagamento_combinado_dinheiro_e_pix_valido():
    pagamentos = _pagamentos_do_admin(
        forma_pagamento=None,
        valor_recebido=None,
        total_liquido=100.0,
        forma_pagamento_1="dinheiro",
        valor_pagamento_1=40.0,
        forma_pagamento_2="pix",
        valor_pagamento_2=60.0,
    )

    assert len(pagamentos) == 2
    assert sum(item["valor"] for item in pagamentos) == 100.0
    assert pagamentos[0]["forma"] == "dinheiro"
    assert pagamentos[0]["troco"] == 0.0


def test_pagamento_combinado_rejeita_excedente_mesmo_com_dinheiro():
    with pytest.raises(ValueError, match="valor_excedente"):
        _pagamentos_do_admin(
            forma_pagamento=None,
            valor_recebido=None,
            total_liquido=80.0,
            forma_pagamento_1="cartao_credito",
            valor_pagamento_1=30.0,
            forma_pagamento_2="dinheiro",
            valor_pagamento_2=60.0,
        )


def test_pagamento_integral_com_metodo_unico():
    pagamentos = _pagamentos_do_admin(
        forma_pagamento="cartao_debito",
        valor_recebido=None,
        total_liquido=52.35,
    )
    assert pagamentos == [{
        "forma": "cartao_debito", "valor": 52.35,
        "valor_recebido": None, "troco": None,
    }]


def test_pagamento_combina_metodos_credito_e_pix_exatamente():
    pagamentos = _pagamentos_do_admin(
        forma_pagamento=None, valor_recebido=None, total_liquido=101.01,
        forma_pagamento_1="cartao_credito", valor_pagamento_1=61.01,
        forma_pagamento_2="pix", valor_pagamento_2=40.00,
    )
    assert sum(round(item["valor"] * 100) for item in pagamentos) == 10101


def test_pagamento_combinado_rejeita_diferenca_de_um_centavo():
    with pytest.raises(ValueError, match="valor_excedente"):
        _pagamentos_do_admin(
            forma_pagamento=None, valor_recebido=None, total_liquido=100.00,
            forma_pagamento_1="dinheiro", valor_pagamento_1=60.01,
            forma_pagamento_2="pix", valor_pagamento_2=40.00,
        )


def test_parcelas_do_credito_integral_e_combinado_somam_valor_alocado():
    parcelas_integral = calcular_parcelas_cartao(100, 3)
    parcelas_combinadas = calcular_parcelas_cartao(61.01, 3)
    assert sum(round(valor * 100) for valor in parcelas_integral) == 10000
    assert parcelas_integral == [33.34, 33.33, 33.33]
    assert parcelas_combinadas == [20.34, 20.34, 20.33]
    assert sum(round(valor * 100) for valor in parcelas_combinadas) == 6101


def test_parcelamento_rejeita_quantidade_fora_do_limite():
    with pytest.raises(ValueError, match="parcelas_invalidas"):
        calcular_parcelas_cartao(100, 13)


def test_pagamento_combined_rejeita_valor_invalido():
    with pytest.raises(ValueError, match="valor_insuficiente"):
        _pagamentos_do_admin(
            forma_pagamento=None,
            valor_recebido=None,
            total_liquido=100.0,
            forma_pagamento_1="pix",
            valor_pagamento_1=40.0,
            forma_pagamento_2="dinheiro",
            valor_pagamento_2=30.0,
        )


def test_pagamento_combined_rejeita_metodo_duplicado():
    with pytest.raises(ValueError, match="pagamento_duplicado"):
        _pagamentos_do_admin(
            forma_pagamento=None,
            valor_recebido=None,
            total_liquido=90.0,
            forma_pagamento_1="pix",
            valor_pagamento_1=45.0,
            forma_pagamento_2="pix",
            valor_pagamento_2=45.0,
        )


def test_finalizar_venda_faz_rollback_se_commit_falhar():
    request = MagicMock()
    request.form = {
        "forma_pagamento_1": "dinheiro",
        "valor_pagamento_1": "60",
        "forma_pagamento_2": "pix",
        "valor_pagamento_2": "40",
    }

    produto = Produto(
        id=1,
        nome="Produto teste",
        preco=100.0,
        plataforma="PC",
        estoque_atual=10,
        ativo=True,
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = produto
    db.commit.side_effect = Exception("DB fail")

    response = finalizar_venda(
        request=request,
        carrinho_json='[{"produto_id": 1, "quantidade": 1}]',
        cliente_id=0,
        observacao="",
        forma_pagamento_1="dinheiro",
        valor_pagamento_1=60.0,
        forma_pagamento_2="pix",
        valor_pagamento_2=40.0,
        pix_aprovado=True,
        db=db,
        usuario={"role": "admin", "id": 1},
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 302
    assert response.headers["location"] == "/pdv?erro=salvar"
    db.rollback.assert_called_once()
