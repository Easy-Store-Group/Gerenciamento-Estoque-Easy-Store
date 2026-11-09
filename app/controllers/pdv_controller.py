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
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session, load_only

from app.database import get_db

from app.models.venda import Venda, ItemVenda
from app.models.produto import Produto
from app.models.cliente import Cliente
from app.models.movimentacao import Movimentacao, Tipo_de_movimentacao
from app.models.pagamento import Pagamento
from app.services.pix_service import PixService

from app.auth import (
    get_admin,
    get_admin_ou_operador,
)

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


def _centavos(value):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            return None
        quantized = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if number != quantized:
            raise ValueError("valor_pagamento_invalido")
        return int(quantized * 100)
    except (InvalidOperation, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) == "valor_pagamento_invalido":
            raise
        return None


def calcular_parcelas_cartao(valor_credito, quantidade):
    centavos = _centavos(valor_credito)
    if centavos is None or centavos <= 0:
        raise ValueError("valor_pagamento_invalido")
    try:
        quantidade = int(quantidade)
    except (TypeError, ValueError) as exc:
        raise ValueError("parcelas_invalidas") from exc
    if quantidade < 1 or quantidade > 12:
        raise ValueError("parcelas_invalidas")
    base, resto = divmod(centavos, quantidade)
    return [(base + (1 if indice < resto else 0)) / 100 for indice in range(quantidade)]


def _pagamentos_do_admin(
    forma_pagamento: str | None,
    valor_recebido: float | None,
    total_liquido: float,
    forma_pagamento_1: str | None = None,
    valor_pagamento_1: float | None = None,
    forma_pagamento_2: str | None = None,
    valor_pagamento_2: float | None = None,
):
    """Valida pagamento único ou dois meios, sempre com valores em centavos."""
    total_centavos = _centavos(total_liquido)
    if total_centavos is None or total_centavos <= 0:
        raise ValueError("valor_pagamento_invalido")

    combinado = any(value not in (None, "") for value in (
        forma_pagamento_1, valor_pagamento_1, forma_pagamento_2, valor_pagamento_2
    ))
    if combinado:
        pagamentos = []
        formas_usadas = set()
        for forma, valor in ((forma_pagamento_1, valor_pagamento_1), (forma_pagamento_2, valor_pagamento_2)):
            if not forma or forma not in FORMAS_PAGAMENTO_VALIDAS:
                raise ValueError("forma_pagamento_invalida" if forma else "forma_pagamento")
            if forma in formas_usadas:
                raise ValueError("pagamento_duplicado")
            formas_usadas.add(forma)
            centavos = _centavos(valor)
            if centavos is None or centavos <= 0:
                raise ValueError("valor_pagamento_invalido")
            pagamentos.append((forma, centavos))

        if len(pagamentos) != 2:
            raise ValueError("forma_pagamento")
        pago = sum(valor for _, valor in pagamentos)
        if pago < total_centavos:
            raise ValueError("valor_insuficiente")
        if pago > total_centavos:
            raise ValueError("valor_excedente")
        return [{
            "forma": forma, "valor": valor / 100,
            "valor_recebido": valor / 100 if forma == "dinheiro" else None,
            "troco": 0.0 if forma == "dinheiro" else None,
        } for forma, valor in pagamentos]

    if forma_pagamento is None:
        raise ValueError("forma_pagamento")
    if forma_pagamento not in FORMAS_PAGAMENTO_VALIDAS:
        raise ValueError("forma_pagamento_invalida")

    recebido = _centavos(valor_recebido)
    if forma_pagamento == "dinheiro":
        if recebido is None:
            raise ValueError("valor_recebido")
        if recebido < total_centavos:
            raise ValueError("valor_insuficiente")
        return [{
            "forma": forma_pagamento, "valor": total_centavos / 100,
            "valor_recebido": recebido / 100,
            "troco": (recebido - total_centavos) / 100,
        }]
    return [{
        "forma": forma_pagamento, "valor": total_centavos / 100,
        "valor_recebido": None, "troco": None,
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
# FINALIZAR VENDA
# ============================================================

@router.post("/pix/preview")
def preview_pix(
    carrinho_json: str = Form(...),
    cliente_id: int = Form(0),
    forma_pagamento: str | None = Form(None),
    valor_recebido: float | None = Form(None),
    forma_pagamento_1: str | None = Form(None),
    valor_pagamento_1: float | None = Form(None),
    forma_pagamento_2: str | None = Form(None),
    valor_pagamento_2: float | None = Form(None),
    db: Session = Depends(get_db),
    usuario=Depends(get_admin_ou_operador),
):
    """Calcula e exibe uma cobran?a Pix visual, sem gravar venda ou estoque."""
    try:
        itens = _parse_carrinho_json(carrinho_json.strip())
    except (json.JSONDecodeError, ValueError, AttributeError):
        raise HTTPException(status_code=400, detail="Carrinho inv?lido")
    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    desconto = 0.0
    if cliente_id:
        cliente = db.query(Cliente).filter(Cliente.id == cliente_id, Cliente.ativo == True).first()
        if cliente and cliente.is_associado:
            desconto = DESCONTO_ASSOCIADO

    total_bruto = 0.0
    for item in itens:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="Item inv?lido")
        produto_id = _extrair_produto_id(item)
        try:
            quantidade = int(item.get("quantidade", 0))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Quantidade inv?lida")
        if not produto_id or quantidade <= 0:
            raise HTTPException(status_code=400, detail="Item ou quantidade inv?lidos")
        produto = db.query(Produto).filter(Produto.id == produto_id, Produto.ativo == True).first()
        if not produto:
            raise HTTPException(status_code=404, detail="Produto n?o encontrado ou inativo")
        if produto.estoque_atual < quantidade:
            raise HTTPException(status_code=400, detail=f"Estoque insuficiente para {produto.nome}")
        total_bruto += produto.preco * quantidade

    total_venda = round(total_bruto * (1 - desconto / 100), 2)
    try:
        pagamentos = _pagamentos_do_admin(
            forma_pagamento=forma_pagamento,
            valor_recebido=valor_recebido,
            total_liquido=total_venda,
            forma_pagamento_1=forma_pagamento_1,
            valor_pagamento_1=valor_pagamento_1,
            forma_pagamento_2=forma_pagamento_2,
            valor_pagamento_2=valor_pagamento_2,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    valor_pix = round(sum(item["valor"] for item in pagamentos if item["forma"] == "pix"), 2)
    if valor_pix <= 0:
        raise HTTPException(status_code=400, detail="Selecione Pix para gerar o QR Code")

    cobranca = PixService().gerar_cobranca(0, valor_pix)
    return {
        "total_venda": total_venda,
        "valor_pix": valor_pix,
        "qr_code_base64": cobranca.qr_code_base64,
    }


@router.get("/finalizar")
def finalizar_venda_get(request: Request):
    """Evita 405 em acessos manuais ao endpoint de finalização."""
    return RedirectResponse(
        url="/pdv?erro=metodo_invalido",
        status_code=302,
    )


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

    pix_aprovado: bool = Form(False),

    db: Session = Depends(get_db),

    usuario=Depends(get_admin_ou_operador)
):

    # ========================================================
    # IDENTIFICA SE É ADMIN
    # ========================================================

    role_usuario = usuario.get("role")

    eh_admin = role_usuario == "admin"
    eh_operador = role_usuario == "operador"
    pix_operador = eh_operador and forma_pagamento == "pix"


    # ========================================================
    # VALIDA PAGAMENTO
    # SOMENTE ADMIN PODE INFORMAR PAGAMENTO
    # ========================================================

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


    for item in itens:

        if not isinstance(item, dict):

            return _redirect_pdv(
                db,
                "/pdv?erro=item_invalido"
            )


        produto_id = _extrair_produto_id(item)


        if produto_id is None:

            return _redirect_pdv(
                db,
                "/pdv?erro=item_invalido"
            )


        try:

            qtd = int(
                item.get(
                    "quantidade",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            return _redirect_pdv(
                db,
                "/pdv?erro=quantidade"
            )


        if qtd <= 0:

            return _redirect_pdv(
                db,
                "/pdv?erro=quantidade"
            )


        produto = (
            db.query(Produto)
            .filter(
                Produto.id == produto_id,
                Produto.ativo == True
            )
            .with_for_update()
            .first()
        )


        if not produto:

            return _redirect_pdv(
                db,
                f"/pdv?erro=produto_inexistente&id={produto_id}"
            )


        if produto.estoque_atual < qtd:

            return _redirect_pdv(
                db,
                f"/pdv?erro=estoque&produto={quote(produto.nome)}"
            )


        subtotal = (
            produto.preco * qtd
        )

        total_bruto += subtotal


        itens_validados.append(
            {
                "produto": produto,
                "quantidade": qtd,
                "preco": produto.preco,
                "produto_nome": produto.nome,
            }
        )


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

    if eh_admin or pix_operador:
        try:
            pagamentos_admin = _pagamentos_do_admin(
                forma_pagamento=forma_pagamento,
                valor_recebido=valor_recebido,
                total_liquido=total_liquido,
                forma_pagamento_1=forma_pagamento_1,
                valor_pagamento_1=valor_pagamento_1,
                forma_pagamento_2=forma_pagamento_2,
                valor_pagamento_2=valor_pagamento_2,
            )
        except ValueError as exc:
            return _redirect_pdv(db, f"/pdv?erro={exc}")

        if pagamentos_admin and len(pagamentos_admin) == 1:
            metodo = pagamentos_admin[0]
            if metodo["forma"] == "dinheiro":
                troco = round(float(metodo["troco"] or 0.0), 2)
            else:
                troco = 0.0

    # ========================================================
    # PERSISTE TUDO EM UMA ÚNICA TRANSAÇÃO
    # ========================================================

    tem_pix = (eh_admin or pix_operador) and any(item["forma"] == "pix" for item in pagamentos_admin)
    if tem_pix and not pix_aprovado:
        return _redirect_pdv(db, "/pdv?erro=pix_aprovacao")

    try:

        # ----------------------------------------------------
        # CRIA A VENDA
        # ----------------------------------------------------

        colunas_venda = {coluna["name"] for coluna in inspect(db.get_bind()).get_columns("vendas")}
        if "status" in colunas_venda:
            venda = Venda(
                cliente_id=cliente_id_valido,
                usuario_id=usuario.get("id"),
                desconto_percentual=desconto_percentual,
                total_bruto=round(total_bruto, 2),
                total_liquido=total_liquido,
                observacao=observacao or None,
                status="PAGO" if tem_pix and pix_aprovado else "PENDENTE",
            )
            db.add(venda)
            db.flush()
            venda_id = venda.id
        else:
            venda_id = db.execute(
                text("""INSERT INTO vendas
                    (cliente_id, usuario_id, desconto_percentual, total_bruto, total_liquido, observacao)
                    VALUES (:cliente_id, :usuario_id, :desconto_percentual, :total_bruto, :total_liquido, :observacao)
                    RETURNING id"""),
                {
                    "cliente_id": cliente_id_valido,
                    "usuario_id": usuario.get("id"),
                    "desconto_percentual": desconto_percentual,
                    "total_bruto": round(total_bruto, 2),
                    "total_liquido": total_liquido,
                    "observacao": observacao or None,
                },
            ).scalar_one()


        # ----------------------------------------------------
        # ITENS DA VENDA
        # ----------------------------------------------------

        for item in itens_validados:

            db.add(
                ItemVenda(
                    venda_id=venda_id,

                    produto_id=item["produto"].id,

                    produto_nome=item["produto_nome"],

                    quantidade=item["quantidade"],

                    preco_unitario=item["preco"],
                )
            )


            # Baixa estoque

            item["produto"].estoque_atual -= (
                item["quantidade"]
            )


            # ------------------------------------------------
            # MOVIMENTAÇÃO DE ESTOQUE
            # ------------------------------------------------

            db.add(
                Movimentacao(
                    tipo=Tipo_de_movimentacao.SAIDA,

                    quantidade=item["quantidade"],

                    preco_unitario=item["preco"],

                    observacao=f"Venda PDV #{venda_id}",

                    produto_id=item["produto"].id,

                    usuario_id=usuario.get("id"),
                )
            )


        # ====================================================
        # PAGAMENTO
        # SOMENTE ADMIN
        # ====================================================

        if eh_admin or pix_operador:

            pix_service = PixService()

            for pagamento_data in pagamentos_admin:
                pagamento_kwargs = {
                    "venda_id": venda_id,
                    "forma": pagamento_data["forma"],
                    "valor": pagamento_data["valor"],
                    "valor_recebido": pagamento_data["valor_recebido"],
                    "troco": pagamento_data["troco"],
                    "status": "PAGO" if pagamento_data["forma"] != "pix" or pix_aprovado else "PENDENTE",
                    "provider": "local" if pagamento_data["forma"] == "pix" else None,
                    "provider_charge_id": None,
                    "pix_qr_code": None,
                    "pix_copy_paste": None,
                    "pix_qr_code_url": None,
                    "pix_status": ("PAGO" if pix_aprovado else "PENDENTE") if pagamento_data["forma"] == "pix" else None,
                    "pix_data_pagamento": datetime.utcnow() if pagamento_data["forma"] == "pix" and pix_aprovado else None,
                    "pix_observacao": "Aprovado manualmente pelo operador" if pagamento_data["forma"] == "pix" and pix_aprovado else None,
                }

                if pagamento_data["forma"] == "pix":
                    cobranca = pix_service.gerar_cobranca(venda_id, float(pagamento_data["valor"]))
                    pagamento_kwargs.update({
                        "provider": "local",
                        "provider_charge_id": cobranca.provider_charge_id,
                        "status": "PAGO" if pix_aprovado else "PENDENTE",
                        "pix_qr_code": cobranca.qr_code_base64,
                        "pix_copy_paste": cobranca.copia_cola,
                        "pix_qr_code_url": None,
                        "pix_status": "PAGO" if pix_aprovado else "PENDENTE",
                        "pix_data_pagamento": datetime.utcnow() if pix_aprovado else None,
                        "pix_observacao": "Aprovado manualmente pelo operador" if pix_aprovado else None,
                    })

                colunas_pagamento = {
                    coluna["name"]
                    for coluna in inspect(db.get_bind()).get_columns("pagamentos")
                }
                colunas_modelo_pagamento = set(Pagamento.__table__.columns.keys())
                if colunas_modelo_pagamento.issubset(colunas_pagamento):
                    db.add(Pagamento(**pagamento_kwargs))
                else:
                    db.execute(
                        text("""INSERT INTO pagamentos
                            (venda_id, forma, valor, valor_recebido, troco)
                            VALUES (:venda_id, :forma, :valor, :valor_recebido, :troco)"""),
                        {
                            "venda_id": venda_id,
                            "forma": pagamento_data["forma"],
                            "valor": pagamento_data["valor"],
                            "valor_recebido": pagamento_data["valor_recebido"],
                            "troco": pagamento_data["troco"],
                        },
                    )


        # ----------------------------------------------------
        # COMMIT
        # ----------------------------------------------------

        db.commit()


    except Exception:

        db.rollback()

        return RedirectResponse(
            url="/pdv?erro=salvar",
            status_code=302
        )


    # ========================================================
    # REDIRECIONA PARA O COMPROVANTE
    # ========================================================

    return RedirectResponse(
        url=f"/pdv/venda/{venda_id}?sucesso=ok",
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
        .options(load_only(
            Venda.id, Venda.cliente_id, Venda.usuario_id, Venda.desconto_percentual,
            Venda.total_bruto, Venda.total_liquido, Venda.observacao, Venda.criado_em,
        ))
        .filter(Venda.id == venda_id)
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
        .options(load_only(
            Venda.id, Venda.cliente_id, Venda.desconto_percentual,
            Venda.total_liquido, Venda.criado_em,
        ))
        .order_by(Venda.criado_em.desc())
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


# ============================================================
# PAGAMENTO PIX
# ============================================================

@router.get("/pix/{venda_id}")
def tela_pix_venda(
    venda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_admin_ou_operador),
):
    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        return RedirectResponse(url="/pdv", status_code=302)

    pagamento_pix = (
        db.query(Pagamento)
        .filter(Pagamento.venda_id == venda.id, Pagamento.forma == "pix")
        .order_by(Pagamento.id.desc())
        .first()
    )

    return templates.TemplateResponse(
        request,
        "admin/pix_pagamento.html",
        {
            "request": request,
            "usuario": usuario,
            "venda": venda,
            "pagamento_pix": pagamento_pix,
            "page_title": f"Pagamento Pix - Venda #{venda.id}",
            "page_subtitle": "Cobrança Pix ativa",
            "css_path": "css/pos.css",
            "active": "pos",
        },
    )


@router.post("/pix/{venda_id}/confirmar")
def confirmar_pix_venda(
    venda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_admin_ou_operador),
):
    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        return RedirectResponse(url="/pdv", status_code=302)

    pagamento = (
        db.query(Pagamento)
        .filter(Pagamento.venda_id == venda_id, Pagamento.forma == "pix")
        .order_by(Pagamento.id.desc())
        .first()
    )

    if not pagamento:
        return RedirectResponse(url=f"/pdv?erro=forma_pagamento", status_code=302)

    if pagamento.status == "PAGO":
        return RedirectResponse(url=f"/pdv/venda/{venda.id}?sucesso=ok", status_code=302)
    if pagamento.status != "PENDENTE":
        return RedirectResponse(url=f"/pdv/pix/{venda.id}?erro=pagamento_cancelado", status_code=302)

    pagamento.status = "PAGO"
    pagamento.pix_status = "PAGO"
    pagamento.pix_data_pagamento = datetime.utcnow()
    venda.status = "PAGO"
    db.add(pagamento)
    db.add(venda)
    db.commit()

    return RedirectResponse(url=f"/pdv/venda/{venda.id}?sucesso=ok", status_code=302)


@router.post("/pix/{venda_id}/cancelar")
def cancelar_pix_venda(
    venda_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario=Depends(get_admin_ou_operador),
):
    pagamento = (
        db.query(Pagamento)
        .filter(Pagamento.venda_id == venda_id, Pagamento.forma == "pix")
        .order_by(Pagamento.id.desc())
        .first()
    )

    if pagamento and pagamento.status == "PENDENTE":
        pagamento.status = "CANCELADO"
        pagamento.pix_status = "CANCELADO"
        db.add(pagamento)
        db.commit()

    return RedirectResponse(url=f"/pdv?erro=cancelado", status_code=302)