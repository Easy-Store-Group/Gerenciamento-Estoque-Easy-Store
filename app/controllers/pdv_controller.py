# ============================================================
# controllers/pdv_controller.py — Ponto de Venda
# ============================================================
# O PDV funciona assim:
# 1. GET /pdv            → tela com produtos + campo de cliente
# 2. O carrinho vive no JavaScript (memória do navegador)
# 3. POST /pdv/finalizar → recebe um JSON com os itens
#                          cria Venda + ItensVenda + Movimentacao
#                          + baixa estoque
#                          + pagamento (somente para ADMIN)
# ============================================================

import json
import logging
import math
from decimal import Decimal
from urllib.parse import quote

logger = logging.getLogger("pdv.pix")

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.venda import Venda, ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.models.pagamento import Pagamento, PagamentoParcela

from app.auth import (
    get_admin,
    get_admin_ou_operador,
)
from app.services.payment_engine import PaymentEngine, calcular_parcelas_credito
from app.services.pix_service import gerar_payload_pix, gerar_qrcode_pix_base64, verificar_status_pix
from app.models.variacao import ProdutoVariacao
from app.services.estoque_service import recalcular_estoque_produto
from app.models.payment_schemas import PaymentMethod



router = APIRouter(prefix="/pdv", tags=["PDV"])

templates = Jinja2Templates(directory="app/templates")

DESCONTO_ASSOCIADO = 5.0  # percentual fixo


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def _redirect_pdv(db: Session, url: str) -> RedirectResponse:
    db.rollback()
    return RedirectResponse(
        url=url,
        status_code=302
    )


def _parse_carrinho_json(raw: str) -> list:
    parsed = json.loads(raw)

    if isinstance(parsed, str):
        parsed = json.loads(parsed)

    if isinstance(parsed, dict):
        parsed = list(parsed.values())

    if not isinstance(parsed, list):
        raise ValueError("carrinho deve ser uma lista")

    return parsed


def _extrair_produto_id(item: dict) -> int | None:

    for chave in (
        "produto_id",
        "id",
        "productId"
    ):

        valor = item.get(chave)

        if valor is None or valor == "":
            continue

        try:
            produto_id = int(valor)

        except (TypeError, ValueError):
            continue

        if produto_id > 0:
            return produto_id

    return None


FORMAS_PAGAMENTO_VALIDAS = {
    "dinheiro",
    "pix",
    "cartao_credito",
    "cartao_debito",
}


def _coerce_float(value):
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pagamentos_do_admin(
    forma_pagamento: str | None,
    valor_recebido: float | None,
    total_liquido: float,
    forma_pagamento_1: str | None = None,
    valor_pagamento_1: float | None = None,
    forma_pagamento_2: str | None = None,
    valor_pagamento_2: float | None = None,
    parcelas_forma_1: int | None = None,
    parcelas_forma_2: int | None = None,
):
    """Normaliza os pagamentos válidos para o admin.

    Suporta pagamento único, combinação de dois métodos e parcelamento em crédito.
    """

    total_liquido = round(float(total_liquido), 2)

    if forma_pagamento_1 or forma_pagamento_2 or valor_pagamento_1 or valor_pagamento_2:
        pagamentos = []
        formas_usadas = set()

        for forma, valor, parcelas in (
            (forma_pagamento_1, valor_pagamento_1, parcelas_forma_1),
            (forma_pagamento_2, valor_pagamento_2, parcelas_forma_2),
        ):
            if forma in (None, ""):
                continue

            if forma not in FORMAS_PAGAMENTO_VALIDAS:
                raise ValueError("forma_pagamento_invalida")

            if forma in formas_usadas:
                raise ValueError("pagamento_duplicado")

            formas_usadas.add(forma)

            valor_float = _coerce_float(valor)
            if valor_float is None or valor_float <= 0:
                raise ValueError("valor_pagamento_invalido")

            if forma == "cartao_credito":
                parcelas_validas = int(parcelas or 1)
                if parcelas_validas < 1 or parcelas_validas > 12:
                    raise ValueError("parcelas_invalidas")

                parcela_valor = round(valor_float / parcelas_validas, 2)
                pagamentos.append({
                    "forma": forma,
                    "valor": round(valor_float, 2),
                    "parcelado": parcelas_validas > 1,
                    "numero_parcelas": parcelas_validas,
                    "valor_parcela": parcela_valor,
                })
                continue

            pagamentos.append({
                "forma": forma,
                "valor": round(valor_float, 2),
                "parcelado": False,
                "numero_parcelas": 1,
                "valor_parcela": round(valor_float, 2),
            })

        if not pagamentos:
            raise ValueError("forma_pagamento")

        if len(pagamentos) != 2:
            raise ValueError("forma_pagamento")

        total_pago = round(sum(item["valor"] for item in pagamentos), 2)
        if total_pago < total_liquido:
            raise ValueError("valor_insuficiente")

        if total_pago > total_liquido and not any(item["forma"] == "dinheiro" for item in pagamentos):
            raise ValueError("valor_insuficiente")

        troco = round(total_pago - total_liquido, 2) if any(item["forma"] == "dinheiro" for item in pagamentos) else 0.0

        pagamentos_validos = []
        for item in pagamentos:
            forma = item["forma"]
            if forma == "dinheiro":
                pagamentos_validos.append({
                    "forma": forma,
                    "valor": round(item["valor"], 2),
                    "valor_recebido": round(item["valor"], 2),
                    "troco": troco,
                    "parcelado": False,
                    "numero_parcelas": 1,
                    "valor_parcela": round(item["valor"], 2),
                })
            else:
                pagamentos_validos.append({
                    "forma": forma,
                    "valor": round(item["valor"], 2),
                    "valor_recebido": None,
                    "troco": None,
                    "parcelado": bool(item.get("parcelado")),
                    "numero_parcelas": item.get("numero_parcelas") or 1,
                    "valor_parcela": item.get("valor_parcela") or round(item["valor"], 2),
                })

        return pagamentos_validos

    if forma_pagamento is None:
        raise ValueError("forma_pagamento")

    if forma_pagamento not in FORMAS_PAGAMENTO_VALIDAS:
        raise ValueError("forma_pagamento_invalida")

    valor_float = _coerce_float(valor_recebido)

    if forma_pagamento == "cartao_credito":
        parcelas_validas = int(parcelas_forma_1 or 1)
        if parcelas_validas < 1 or parcelas_validas > 12:
            raise ValueError("parcelas_invalidas")
        parcela_valor = round(total_liquido / parcelas_validas, 2)
        return [{
            "forma": forma_pagamento,
            "valor": round(total_liquido, 2),
            "valor_recebido": None,
            "troco": None,
            "parcelado": parcelas_validas > 1,
            "numero_parcelas": parcelas_validas,
            "valor_parcela": parcela_valor,
        }]

    if forma_pagamento == "dinheiro":
        if valor_float is None:
            raise ValueError("valor_recebido")

        if valor_float < total_liquido:
            raise ValueError("valor_insuficiente")

        troco = round(valor_float - total_liquido, 2)

        return [{
            "forma": forma_pagamento,
            "valor": round(total_liquido, 2),
            "valor_recebido": round(valor_float, 2),
            "troco": troco,
            "parcelado": False,
            "numero_parcelas": 1,
            "valor_parcela": round(total_liquido, 2),
        }]

    return [{
        "forma": forma_pagamento,
        "valor": round(total_liquido, 2),
        "valor_recebido": None,
        "troco": None,
        "parcelado": False,
        "numero_parcelas": 1,
        "valor_parcela": round(total_liquido, 2),
    }]


# ============================================================
# TELA DO PDV
# ============================================================

@router.get("/")
def tela_pdv(
    request: Request,
    busca: str = "",
    pagina: int = 1,
    por_pagina: int = 12,
    db: Session = Depends(get_db),
    usuario=Depends(get_admin_ou_operador)
):

    """
    Carrega a tela do PDV com todos os produtos ativos
    e a lista de clientes para o campo de busca.
    """

    query = (
        db.query(Produto)
        .filter(
            Produto.ativo == True,
            Produto.estoque_atual > 0
        )
    )

    if busca and busca.strip():
        query = query.filter(Produto.nome.ilike(f"%{busca.strip()}%"))

    query = query.order_by(Produto.nome)
    total_produtos = query.count()

    por_pagina = min(max(por_pagina, 1), 50)
    total_paginas = math.ceil(total_produtos / por_pagina) if total_produtos else 1
    pagina = min(max(pagina, 1), total_paginas)

    produtos = (
        query
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )

    clientes = (
        db.query(Cliente)
        .filter(
            Cliente.ativo == True
        )
        .order_by(Cliente.nome)
        .all()
    )

    return templates.TemplateResponse(
        request,
        "admin/pos.html",
        {
            "request": request,
            "usuario": usuario,
            "produtos": produtos,
            "clientes": clientes,
            "busca": busca,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_paginas": total_paginas,
            "total_produtos": total_produtos,
            "css_path": "css/pos.css",
            "active": "pos",
            "page_title": "Ponto de Venda",
            "page_subtitle": "Monte o carrinho e finalize a venda",
            "desconto_associado": DESCONTO_ASSOCIADO,
        }
    )


# ============================================================
# API HELPER PIX & PARCELAS
# ============================================================

@router.get("/api/pix-status")
def api_pix_status(usuario=Depends(get_admin_ou_operador)):
    """Verifica a conectividade e disponibilidade do serviço de pagamento PIX."""
    status_pix = verificar_status_pix()
    resposta = {
        "disponivel": bool(status_pix.get("disponivel")),
        "motivo": status_pix.get("motivo"),
        "codigo": status_pix.get("codigo"),
    }
    return JSONResponse(
        content=resposta,
        headers={"Cache-Control": "private, max-age=15, must-revalidate"},
    )


@router.get("/api/pix-qrcode")
def api_pix_qrcode(
    valor: float,
    forma_pagamento: str = "pix",
    usuario=Depends(get_admin_ou_operador)
):
    """Retorna o código copia e cola e a imagem base64 do QR Code Pix sob demanda.
    
    Regras de Backend:
    1. Valida se a forma solicitada é estritamente 'pix'.
    2. Valida a disponibilidade e configuração da API PIX.
    3. Trata erros, timeout e falhas de conexão de forma segura e sem dados sensíveis nos logs.
    4. Não confia apenas nas verificações do Front-end.
    """
    if str(forma_pagamento).strip().lower() != "pix":
        logger.warning("Tentativa de gerar QR Code Pix com forma de pagamento incompativel: %s", forma_pagamento)
        return {
            "erro": "A geração de QR Code só é permitida quando a forma de pagamento selecionada for PIX.",
            "disponivel": False,
            "codigo": "FORMA_INVALIDA"
        }

    status_pix = verificar_status_pix()
    if not status_pix.get("disponivel"):
        logger.warning("Requisicao de QR Code PIX recusada: servico indisponivel (%s)", status_pix.get("codigo"))
        return {
            "erro": status_pix.get(
                "motivo",
                "PIX temporariamente indisponível. Não foi possível estabelecer conexão com o serviço de pagamento. Escolha outra forma de pagamento ou tente novamente mais tarde."
            ),
            "indisponivel": True,
            "disponivel": False,
            "codigo": status_pix.get("codigo", "INDISPONIVEL")
        }

    try:
        from decimal import Decimal
        val_dec = Decimal(str(valor)).quantize(Decimal("0.01"))
        if val_dec <= Decimal("0.00"):
            return {
                "erro": "Valor para geração do PIX deve ser maior que zero.",
                "disponivel": False,
                "codigo": "VALOR_INVALIDO"
            }
        
        payload = gerar_payload_pix(val_dec)
        qrcode_b64 = gerar_qrcode_pix_base64(payload)
        
        logger.info("QR Code PIX gerado com sucesso sob demanda. Valor: %.2f", float(val_dec))
        return {
            "payload": payload,
            "qrcode_b64": qrcode_b64,
            "valor": float(val_dec),
            "disponivel": True,
            "status": "pendente"
        }
    except Exception as exc:
        logger.error("Excecao na composicao do QR Code PIX: %s", str(exc), exc_info=False)
        return {
            "erro": f"Erro interno ao gerar QR Code PIX: {str(exc)}",
            "disponivel": False,
            "codigo": "ERRO_GERACAO"
        }


@router.get("/api/calcular-parcelas")
def api_calcular_parcelas(valor: float, parcelas: int = 1, usuario=Depends(get_admin_ou_operador)):
    """Retorna o detalhamento exato de parcelas para Cartão de Crédito."""
    try:
        from decimal import Decimal
        val_dec = Decimal(str(valor)).quantize(Decimal("0.01"))
        detalhes = calcular_parcelas_credito(val_dec, parcelas)
        return {
            "valor": float(val_dec),
            "parcelas": parcelas,
            "detalhes": [{"number": d.number, "amount": float(d.amount)} for d in detalhes]
        }
    except Exception as exc:
        return {"erro": str(exc)}


# ============================================================
# FINALIZAR VENDA
# ============================================================

@router.get("/finalizar")
def finalizar_venda_get(request: Request):
    """Evita 405 em acessos manuais ao endpoint de finalização."""
    return RedirectResponse(
        url="/pdv?erro=metodo_invalido",
        status_code=302,
    )


from fastapi.params import Form as FormParam


def _clean_form_val(val):
    if val is None or isinstance(val, FormParam):
        return None
    return val


@router.post("/finalizar")
def finalizar_venda(
    request: Request,

    carrinho_json: str = Form(...),

    cliente_id: int = Form(0),

    observacao: str = Form(""),

    # --------------------------------------------------------
    # Campos de pagamento.
    #
    # Esses campos só existem na tela quando o usuário é ADMIN.
    # Para operador eles ficam como None.
    # --------------------------------------------------------

    forma_pagamento: str | None = Form(None),

    valor_recebido: float | None = Form(None),

    forma_pagamento_1: str | None = Form(None),

    valor_pagamento_1: float | None = Form(None),

    forma_pagamento_2: str | None = Form(None),

    valor_pagamento_2: float | None = Form(None),

    parcelas_forma_1: int | None = Form(None),

    parcelas_forma_2: int | None = Form(None),

    chave_idempotencia: str | None = Form(None),

    pix_confirmado: str | None = Form(None),

    db: Session = Depends(get_db),

    usuario=Depends(get_admin_ou_operador)
):

    forma_pagamento = _clean_form_val(forma_pagamento)
    valor_recebido = _clean_form_val(valor_recebido)
    forma_pagamento_1 = _clean_form_val(forma_pagamento_1)
    valor_pagamento_1 = _clean_form_val(valor_pagamento_1)
    forma_pagamento_2 = _clean_form_val(forma_pagamento_2)
    valor_pagamento_2 = _clean_form_val(valor_pagamento_2)
    parcelas_forma_1 = _clean_form_val(parcelas_forma_1)
    parcelas_forma_2 = _clean_form_val(parcelas_forma_2)
    chave_idempotencia = _clean_form_val(chave_idempotencia)
    pix_confirmado = _clean_form_val(pix_confirmado)

    if chave_idempotencia:
        venda_existente = db.query(Venda).filter(Venda.chave_idempotencia == chave_idempotencia).first()
        if venda_existente:
            return RedirectResponse(
                url=f"/pdv/venda/{venda_existente.id}?sucesso=ok",
                status_code=302,
            )

    usa_pix = forma_pagamento == "pix" or forma_pagamento_1 == "pix" or forma_pagamento_2 == "pix"
    if usa_pix and str(pix_confirmado).lower() != "true":
        return _redirect_pdv(db, "/pdv?erro=pix_nao_confirmado")

    # ========================================================
    # IDENTIFICA SE É ADMIN
    # ========================================================

    role_usuario = usuario.get("role")

    eh_admin = role_usuario == "admin"


    # ========================================================
    # VALIDA PAGAMENTO
    # SOMENTE ADMIN PODE INFORMAR PAGAMENTO
    # ========================================================

    if eh_admin:
        pagamentos_admin = []
    else:
        # Operador não possui forma de pagamento.
        forma_pagamento = None
        valor_recebido = None
        pagamentos_admin = []

    # ========================================================
    # LÊ O CARRINHO
    # ========================================================

    try:

        itens = _parse_carrinho_json(
            carrinho_json.strip()
        )

    except (
        json.JSONDecodeError,
        ValueError,
        AttributeError
    ):

        return _redirect_pdv(
            db,
            "/pdv?erro=json"
        )


    if not itens:

        return _redirect_pdv(
            db,
            "/pdv?erro=vazio"
        )


    # ========================================================
    # CLIENTE E DESCONTO
    # ========================================================

    cliente = None

    desconto_percentual = 0.0

    cliente_id_valido = None


    if cliente_id:

        cliente = (
            db.query(Cliente)
            .filter(
                Cliente.id == cliente_id,
                Cliente.ativo == True
            )
            .first()
        )


        if cliente:

            cliente_id_valido = cliente.id

            if cliente.is_associado:

                desconto_percentual = DESCONTO_ASSOCIADO


    # ========================================================
    # VALIDA ESTOQUE E CALCULA TOTAL
    # ========================================================

    total_bruto = 0.0

    itens_validados = []

    # Agrupa itens do carrinho para prevenir produtos repetidos e garantir verificação atômica
    itens_agrupados = {}
    for item in itens:
        if not isinstance(item, dict):
            return _redirect_pdv(db, "/pdv?erro=item_invalido")

        produto_id = _extrair_produto_id(item)
        if produto_id is None:
            return _redirect_pdv(db, "/pdv?erro=item_invalido")

        try:
            qtd = int(item.get("quantidade", 0))
        except (TypeError, ValueError):
            return _redirect_pdv(db, "/pdv?erro=quantidade")

        if qtd <= 0:
            return _redirect_pdv(db, "/pdv?erro=quantidade")

        variacao_id = item.get("variacao_id")
        try:
            variacao_id = int(variacao_id) if variacao_id is not None and str(variacao_id).strip() != "" else None
        except (TypeError, ValueError):
            variacao_id = None

        chave = (produto_id, variacao_id)
        itens_agrupados[chave] = itens_agrupados.get(chave, 0) + qtd

    # Validação e travamento de concorrência com with_for_update() ordenado por ID (previne deadlocks)
    produtos_ids_ordenados = sorted(set(pid for pid, _ in itens_agrupados.keys()))
    produtos_lock = {}
    for pid in produtos_ids_ordenados:
        p_obj = (
            db.query(Produto)
            .filter(Produto.id == pid, Produto.ativo == True)
            .with_for_update()
            .first()
        )
        if not p_obj:
            return _redirect_pdv(db, f"/pdv?erro=produto_inexistente&id={pid}")
        produtos_lock[pid] = p_obj

    # Verifica também variações se existirem
    variacoes_lock = {}
    for (pid, vid), qtd_total in itens_agrupados.items():
        if vid is not None:
            v_obj = (
                db.query(ProdutoVariacao)
                .filter(ProdutoVariacao.id == vid, ProdutoVariacao.produto_id == pid, ProdutoVariacao.ativa == True)
                .with_for_update()
                .first()
            )
            if not v_obj:
                return _redirect_pdv(db, f"/pdv?erro=produto_inexistente&id={pid}")
            variacoes_lock[vid] = v_obj

    # Valida estoque acumulado por produto e por variação
    estoque_demandado_produto = {}
    for (pid, vid), qtd in itens_agrupados.items():
        estoque_demandado_produto[pid] = estoque_demandado_produto.get(pid, 0) + qtd

        if vid is not None:
            v_obj = variacoes_lock[vid]
            if v_obj.estoque_atual < qtd:
                return _redirect_pdv(db, f"/pdv?erro=estoque&produto={quote(produtos_lock[pid].nome)}")

    for pid, qtd_demandada in estoque_demandado_produto.items():
        p_obj = produtos_lock[pid]
        if p_obj.estoque_atual < qtd_demandada:
            return _redirect_pdv(db, f"/pdv?erro=estoque&produto={quote(p_obj.nome)}")

    # Constrói itens validados e totais com precisão
    for (pid, vid), qtd in itens_agrupados.items():
        p_obj = produtos_lock[pid]
        v_obj = variacoes_lock.get(vid)

        preco_unit = v_obj.preco if (v_obj and v_obj.preco is not None) else p_obj.preco
        nome_exibicao = p_obj.nome
        if v_obj:
            detalhe = []
            if v_obj.cor: detalhe.append(v_obj.cor.nome)
            if v_obj.tamanho: detalhe.append(v_obj.tamanho.nome)
            if detalhe:
                nome_exibicao = f"{p_obj.nome} [{ ' - '.join(detalhe) }]"

        subtotal = round(preco_unit * qtd, 2)
        total_bruto += subtotal

        itens_validados.append({
            "produto": p_obj,
            "variacao": v_obj,
            "quantidade": qtd,
            "preco": preco_unit,
            "produto_nome": nome_exibicao,
        })


    # ========================================================
    # CALCULA DESCONTO
    # ========================================================

    desconto_valor = (
        total_bruto *
        (desconto_percentual / 100)
    )

    total_liquido = (
        total_bruto -
        desconto_valor
    )


    total_liquido = round(
        total_liquido,
        2
    )


    # ========================================================
    # VALIDA VALOR RECEBIDO / PAGAMENTOS COMBINADOS
    # ========================================================

    troco = 0.0

    if eh_admin:
        try:
            pagamentos_admin = _pagamentos_do_admin(
                forma_pagamento=forma_pagamento,
                valor_recebido=valor_recebido,
                total_liquido=total_liquido,
                forma_pagamento_1=forma_pagamento_1,
                valor_pagamento_1=valor_pagamento_1,
                forma_pagamento_2=forma_pagamento_2,
                valor_pagamento_2=valor_pagamento_2,
                parcelas_forma_1=parcelas_forma_1,
                parcelas_forma_2=parcelas_forma_2,
            )
        except ValueError as exc:
            return _redirect_pdv(db, f"/pdv?erro={exc}")

        if pagamentos_admin:
            # Validação obrigatória da API PIX se PIX estiver entre os métodos escolhidos
            usa_pix = any(p.get("forma") == "pix" for p in pagamentos_admin)
            if usa_pix:
                status_pix = verificar_status_pix()
                if not status_pix.get("disponivel"):
                    return _redirect_pdv(db, "/pdv?erro=pix_indisponivel")

            # Calcula o troco total da operação (quando há dinheiro)
            troco = round(sum(float(metodo.get("troco") or 0.0) for metodo in pagamentos_admin), 2)

    # ========================================================
    # PERSISTE TUDO EM UMA ÚNICA TRANSAÇÃO
    # ========================================================

    try:

        # ----------------------------------------------------
        # CRIA A VENDA
        # ----------------------------------------------------

        venda = Venda(
            cliente_id=cliente_id_valido,

            usuario_id=usuario.get("id"),

            desconto_percentual=desconto_percentual,

            total_bruto=round(
                total_bruto,
                2
            ),

            total_liquido=total_liquido,

            observacao=observacao or None,

            chave_idempotencia=chave_idempotencia,
        )


        db.add(venda)

        # Gera o ID da venda
        db.flush()


        # ----------------------------------------------------
        # ITENS DA VENDA
        # ----------------------------------------------------

        for item in itens_validados:

            db.add(
                ItemVenda(
                    venda_id=venda.id,
                    produto_id=item["produto"].id,
                    produto_nome=item["produto_nome"],
                    quantidade=item["quantidade"],
                    preco_unitario=item["preco"],
                )
            )

            # Baixa definitiva de estoque apenas na conclusão da venda
            item["produto"].estoque_atual -= item["quantidade"]

            # Se for uma variação, baixa também o estoque da variação e recalcula
            if item.get("variacao"):
                item["variacao"].estoque_atual -= item["quantidade"]

            # ------------------------------------------------
            # MOVIMENTAÇÃO DE ESTOQUE (Rastreabilidade)
            # ------------------------------------------------

            db.add(
                Movimentacao(
                    tipo=Tipo_de_movimentacao.SAIDA,
                    quantidade=item["quantidade"],
                    preco_unitario=item["preco"],
                    observacao=f"Venda PDV #{venda.id} - {item['produto_nome']}",
                    produto_id=item["produto"].id,
                    usuario_id=usuario.get("id"),
                )
            )


        # ====================================================
        # PAGAMENTO
        # SOMENTE ADMIN
        # ====================================================

        if eh_admin:

            for pagamento_data in pagamentos_admin:
                pagamento = Pagamento(
                    venda_id=venda.id,
                    forma=pagamento_data["forma"],
                    valor=pagamento_data["valor"],
                    valor_recebido=pagamento_data["valor_recebido"],
                    troco=pagamento_data["troco"],
                    parcelado=bool(pagamento_data.get("parcelado", False)),
                    numero_parcelas=int(pagamento_data.get("numero_parcelas") or 1),
                    valor_parcela=pagamento_data.get("valor_parcela"),
                )
                if pagamento.forma == "cartao_credito" and pagamento.parcelado:
                    detalhes_parcelas = calcular_parcelas_credito(
                        Decimal(str(pagamento.valor)),
                        pagamento.numero_parcelas,
                    )
                    pagamento.parcelas_detalhe = [
                        PagamentoParcela(numero=detalhe.number, valor=detalhe.amount)
                        for detalhe in detalhes_parcelas
                    ]
                db.add(pagamento)


        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()

    except Exception:
        db.rollback()
        logger.exception("Erro ao salvar venda PDV. Dados do carrinho: %s", carrinho_json)

        return RedirectResponse(
            url="/pdv?erro=salvar",
            status_code=302
        )


    # ========================================================
    # REDIRECIONA PARA O COMPROVANTE
    # ========================================================

    return RedirectResponse(
        url=f"/pdv/venda/{venda.id}?sucesso=ok",
        status_code=302
    )


# ============================================================
# DETALHE DA VENDA
# ============================================================

@router.get("/venda/{venda_id}")
def detalhe_venda(
    venda_id: int,

    request: Request,

    db: Session = Depends(get_db),

    usuario=Depends(get_admin_ou_operador)
):

    """
    Comprovante da venda — exibido imediatamente após finalizar.
    """

    venda = (
        db.query(Venda)
        .filter(
            Venda.id == venda_id
        )
        .first()
    )


    if not venda:

        return RedirectResponse(
            url="/pdv",
            status_code=302
        )


    return templates.TemplateResponse(
        request,
        "admin/comprovante.html",
        {
            "request": request,

            "usuario": usuario,

            "venda": venda,

            "page_title":
                f"Venda #{venda.id}",

            "page_subtitle":
                "Comprovante da venda finalizada",

            "css_path":
                "css/vendas.css",

            "active": "pos",
        }
    )


# ============================================================
# HISTÓRICO DE VENDAS
# ============================================================

@router.get("/historico")
def historico_vendas(
    request: Request,

    pagina: int = 1,

    por_pagina: int = 10,

    db: Session = Depends(get_db),

    usuario=Depends(get_admin)
):

    """
    Histórico de todas as vendas.
    Somente administradores.
    """

    query = (
        db.query(Venda)
        .order_by(
            Venda.criado_em.desc()
        )
    )


    total_vendas = query.count()


    por_pagina = min(
        max(
            por_pagina,
            1
        ),
        10
    )


    total_paginas = (
        math.ceil(
            total_vendas /
            por_pagina
        )
        if total_vendas
        else 1
    )


    pagina = min(
        max(
            pagina,
            1
        ),
        total_paginas
    )


    vendas = (
        query
        .offset(
            (pagina - 1) *
            por_pagina
        )
        .limit(
            por_pagina
        )
        .all()
    )


    return templates.TemplateResponse(
        request,
        "admin/vendas.html",
        {
            "request": request,

            "usuario": usuario,

            "vendas": vendas,

            "pagina": pagina,

            "por_pagina": por_pagina,

            "total_paginas":
                total_paginas,

            "total_vendas":
                total_vendas,

            "page_title":
                "Vendas",

            "page_subtitle":
                "Histórico de vendas do PDV",

            "css_path":
                "css/vendas.css",

            "active": "pos",
        }
    )
