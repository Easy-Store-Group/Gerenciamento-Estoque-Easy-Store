from unittest.mock import MagicMock

import pytest
from fastapi.responses import RedirectResponse

from app.controllers.pdv_controller import _pagamentos_do_admin, finalizar_venda
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


def test_pagamento_combinado_cartao_e_dinheiro_calcula_troco():
    pagamentos = _pagamentos_do_admin(
        forma_pagamento=None,
        valor_recebido=None,
        total_liquido=80.0,
        forma_pagamento_1="cartao_credito",
        valor_pagamento_1=30.0,
        forma_pagamento_2="dinheiro",
        valor_pagamento_2=60.0,
    )

    assert sum(item["valor"] for item in pagamentos) == 90.0
    dinheiro = next(item for item in pagamentos if item["forma"] == "dinheiro")
    assert dinheiro["troco"] == 10.0


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
        db=db,
        usuario={"role": "admin", "id": 1},
    )

    assert isinstance(response, RedirectResponse)
    assert response.status_code == 302
    assert response.headers["location"] == "/pdv?erro=salvar"
    db.rollback.assert_called_once()
