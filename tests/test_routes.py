import json
import tempfile
from pathlib import Path

from app.auth import criar_token
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app

from app.models.produto import Produto
from app.models.venda import Venda
from app.models.usuario import Usuario
from app.models.pagamento import Pagamento


def admin_client(client):
    client.cookies.set(
        "access_token",
        criar_token({"sub": "admin@example.test", "role": "admin", "id": 1}),
    )
    return client


def test_rotas_de_tela_administrativas_nao_retornam_500(client):
    admin = admin_client(client)
    rotas = [
        "/admin", "/admin/pos", "/usuarios/", "/usuarios/novo",
        "/categorias/", "/categorias/nova", "/produtos/",
        "/produtos/novo", "/produtos/variacoes", "/movimentacoes/",
        "/movimentacoes/nova", "/pdv/", "/pdv/historico",
    ]
    for rota in rotas:
        resposta = admin.get(rota)
        assert resposta.status_code != 500, f"{rota}: {resposta.text[:300]}"
        assert resposta.status_code == 200, f"{rota}: {resposta.status_code}"
        if rota == "/pdv/":
            assert 'id="pix-modal"' in resposta.text
            assert "Aprovar pagamento" in resposta.text


def test_rotas_publicas_e_autorizacao(client):
    for rota in ("/", "/sobre-nos", "/auth/produtos", "/api/cores",
                 "/api/tamanhos", "/api/produtos", "/api/produtos/com-variacoes"):
        resposta = client.get(rota)
        assert resposta.status_code == 200, f"{rota}: {resposta.status_code}"

    assert client.get("/admin").status_code == 401
    client.cookies.set(
        "access_token",
        criar_token({"sub": "operador@example.test", "role": "operador", "id": 1}),
    )
    assert client.get("/admin").status_code == 403
    assert client.get("/pdv/").status_code == 200


def test_crud_categoria_produto_movimentacao_e_variacao(client, db_session):
    admin = admin_client(client)

    criada = admin.post("/categorias/nova", data={"nome": "Acess?rios"}, follow_redirects=False)
    assert criada.status_code == 302
    duplicada = admin.post("/categorias/nova", data={"nome": "ACESS?RIOS"})
    assert duplicada.status_code == 400

    categoria = admin.get("/categorias/")
    assert categoria.status_code == 200

    produto_response = admin.post(
        "/produtos/novo",
        data={"nome": "Produto smoke", "preco": "12.50", "plataforma": "PC",
              "estoque_atual": "5", "categoria_id": "1", "variacoes_json": "[]"},
        follow_redirects=False,
    )
    assert produto_response.status_code == 302
    produto = db_session.query(Produto).filter_by(nome="Produto smoke").one()

    cor = admin.post("/api/cores", json={"nome": "Azul", "codigo_hex": "#0000FF"})
    assert cor.status_code == 200
    tamanho = admin.post("/api/tamanhos", json={"nome": "M"})
    assert tamanho.status_code == 200
    variacao = admin.post(
        "/api/variacoes",
        json={"produto_id": produto.id, "cor_id": cor.json()["id"],
              "tamanho_id": tamanho.json()["id"], "estoque_atual": 3, "preco": 12.5},
    )
    assert variacao.status_code == 200, variacao.text
    variacao_id = variacao.json()["id"]
    assert admin.get(f"/api/variacoes/{variacao_id}").status_code == 200
    atualizada = admin.put(f"/api/variacoes/{variacao_id}?estoque=4")
    assert atualizada.status_code == 200
    assert admin.put(f"/api/variacoes/{variacao_id}?estoque=-1").status_code == 400
    assert admin.put(f"/api/variacoes/{variacao_id}/entrada?quantidade=0").status_code == 400
    assert admin.put(f"/api/variacoes/{variacao_id}/entrada?quantidade=2").status_code == 200
    assert admin.put(f"/api/variacoes/{variacao_id}/saida?quantidade=1").status_code == 200
    assert admin.put(f"/api/variacoes/{variacao_id}/saida?quantidade=999").status_code == 400
    assert admin.delete(f"/api/variacoes/{variacao_id}/imagem").status_code == 200
    assert admin.put(f"/api/cores/{cor.json()['id']}", json={"nome": "Verde", "codigo_hex": "#00FF00"}).status_code == 200
    assert admin.put(f"/api/tamanhos/{tamanho.json()['id']}", json={"nome": "G"}).status_code == 200
    assert admin.delete(f"/api/variacoes/{variacao_id}").status_code == 200
    assert admin.delete(f"/api/cores/{cor.json()['id']}").status_code == 200
    assert admin.delete(f"/api/tamanhos/{tamanho.json()['id']}").status_code == 200

    movimento = admin.post(
        "/movimentacoes/nova",
        data={"produto_id": str(produto.id), "tipo": "entrada", "quantidade": "2",
              "preco_unitario": "12.5", "observacao": "teste isolado"},
        follow_redirects=False,
    )
    assert movimento.status_code == 302
    assert admin.get(f"/movimentacoes/produto/{produto.id}").status_code == 200


def test_pagamento_combinado_persiste_venda_pagamentos_e_baixa_estoque(client):
    diretorio = tempfile.TemporaryDirectory()
    engine = create_engine(
        f"sqlite:///{Path(diretorio.name) / 'pagamento_combinado.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessaoTeste = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessaoTeste() as db:
        produto = Produto(nome="Venda combinada", preco=50.00, plataforma="PC",
                          estoque_atual=5, ativo=True)
        db.add(produto)
        db.commit()
        produto_id = produto.id

    def get_db_teste():
        db = SessaoTeste()
        try:
            yield db
        finally:
            db.close()

    override_anterior = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = get_db_teste
    try:
        admin = admin_client(client)
        response = admin.post(
            "/pdv/finalizar",
            data={
                "carrinho_json": json.dumps([{"produto_id": produto_id, "quantidade": 2}]),
                "cliente_id": "0",
                "forma_pagamento_1": "cartao_credito",
                "valor_pagamento_1": "60.00",
                "forma_pagamento_2": "dinheiro",
                "valor_pagamento_2": "40.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert "/pdv/venda/" in response.headers["location"]
        comprovante = admin.get(response.headers["location"], follow_redirects=False)
        assert comprovante.status_code == 200
        assert "100.0" in comprovante.text or "100,00" in comprovante.text
        with SessaoTeste() as db:
            venda_id = int(response.headers["location"].split("/")[-1].split("?")[0])
            venda = db.get(Venda, venda_id)
            assert venda.total_liquido == 100.00
            assert [p.valor for p in venda.pagamentos] == [60.00, 40.00]
            assert db.get(Produto, produto_id).estoque_atual == 3
    finally:
        app.dependency_overrides[get_db] = override_anterior
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        diretorio.cleanup()


def test_fluxo_pdv_pix_ate_confirmacao_manual(client):
    diretorio_temporario = tempfile.TemporaryDirectory()
    engine_legado = create_engine(
        f"sqlite:///{Path(diretorio_temporario.name) / 'legacy_pix_test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine_legado)
    SessaoLegada = sessionmaker(autocommit=False, autoflush=False, bind=engine_legado)
    with SessaoLegada() as db:
        produto = Produto(nome="Item Pix", preco=25.75, plataforma="PC", estoque_atual=4, ativo=True)
        db.add(produto)
        db.commit()
        produto_id = produto.id
        db.execute(text("ALTER TABLE vendas DROP COLUMN status"))
        for coluna in ("pix_observacao", "pix_data_pagamento", "pix_status", "pix_qr_code_url",
                       "pix_copy_paste", "pix_qr_code", "provider_charge_id", "provider", "status"):
            db.execute(text(f"ALTER TABLE pagamentos DROP COLUMN {coluna}"))
        db.commit()

    def get_db_legado():
        db = SessaoLegada()
        try:
            yield db
        finally:
            db.close()

    override_anterior = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = get_db_legado
    try:
        with TestClient(app) as test_client:
            admin = test_client
            admin.cookies.set(
                "access_token",
                criar_token({"sub": "operador@example.test", "role": "operador", "id": 1}),
            )
            dados = {
                "carrinho_json": json.dumps([{"produto_id": produto_id, "quantidade": 1}]),
                "cliente_id": "0",
                "forma_pagamento": "pix",
            }

            preview = admin.post("/pdv/pix/preview", data=dados)
            assert preview.status_code == 200
            assert preview.json()["total_venda"] == 25.75
            assert preview.json()["valor_pix"] == 25.75
            assert preview.json()["qr_code_base64"]
            with SessaoLegada() as db:
                assert db.execute(text("SELECT COUNT(*) FROM vendas")).scalar_one() == 0
                assert db.get(Produto, produto_id).estoque_atual == 4

            sem_aprovar = admin.post("/pdv/finalizar", data=dados, follow_redirects=False)
            assert sem_aprovar.status_code == 302
            assert "pix_aprovacao" in sem_aprovar.headers["location"]
            with SessaoLegada() as db:
                assert db.execute(text("SELECT COUNT(*) FROM vendas")).scalar_one() == 0

            aprovado = admin.post(
                "/pdv/finalizar", data={**dados, "pix_aprovado": "1"}, follow_redirects=False
            )
            assert aprovado.status_code == 302
            assert "/pdv/venda/" in aprovado.headers["location"]
            with SessaoLegada() as db:
                assert db.execute(text("SELECT COUNT(*) FROM vendas")).scalar_one() == 1
            comprovante = admin.get(aprovado.headers["location"], follow_redirects=False)
            assert comprovante.status_code == 200, comprovante.headers.get("location")
            assert "25.75" in comprovante.text
            with SessaoLegada() as db:
                venda_id = int(aprovado.headers["location"].split("/")[-1].split("?")[0])
                venda = db.execute(
                    text("SELECT id, total_liquido FROM vendas WHERE id = :id"), {"id": venda_id}
                ).one()
                pagamento = db.execute(
                    text("SELECT forma, valor FROM pagamentos WHERE venda_id = :id"), {"id": venda_id}
                ).one()
                assert venda.total_liquido == 25.75
                assert pagamento.forma == "pix"
                assert pagamento.valor == 25.75
                assert db.get(Produto, produto_id).estoque_atual == 3
            assert "Estoque: 3 un" in admin.get("/pdv/").text
    finally:
        app.dependency_overrides[get_db] = override_anterior
        Base.metadata.drop_all(bind=engine_legado)
        engine_legado.dispose()
        diretorio_temporario.cleanup()


def test_todas_as_rotas_get_mapeadas_nao_retornam_500(client):
    admin = admin_client(client)
    rotas_admin = [
        "/admin", "/admin/pos", "/usuarios/", "/usuarios/novo",
        "/usuarios/999/editar", "/categorias/", "/categorias/nova",
        "/categorias/999/editar", "/produtos/", "/produtos/novo",
        "/produtos/variacoes", "/produtos/999/editar", "/movimentacoes/",
        "/movimentacoes/nova", "/movimentacoes/produto/999", "/pdv/",
        "/pdv/finalizar", "/pdv/venda/999", "/pdv/historico", "/pdv/pix/999",
        "/clientes/",
    ]
    rotas_publicas = [
        "/", "/sobre-nos", "/auth/login", "/auth/register",
        "/auth/produtos", "/auth/logout", "/auth/forgot",
        "/auth/reset-password?token=invalido", "/api/cores", "/api/tamanhos",
        "/api/produtos", "/api/produtos/com-variacoes",
        "/api/variacoes/produto/999", "/api/variacoes/999",
    ]
    for rota in rotas_admin + rotas_publicas:
        resposta = admin.get(rota)
        assert resposta.status_code != 500, f"GET {rota}: {resposta.text[:300]}"

    cliente = client
    cliente.cookies.set(
        "access_token",
        criar_token({"sub": "cliente@example.test", "role": "cliente", "id": 2}),
    )
    resposta_cliente = cliente.get("/cliente/")
    assert resposta_cliente.status_code != 500, resposta_cliente.text[:300]



def test_dashboard_funciona_com_schema_legado_sem_status(client, db_session):
    venda = Venda(
        cliente_id=None,
        usuario_id=None,
        desconto_percentual=0,
        total_bruto=58.4,
        total_liquido=58.4,
        status="PENDENTE",
    )
    db_session.add(venda)
    db_session.commit()
    venda_id = venda.id

    # Reproduz em mem?ria a tabela SQLite atual, que n?o possui a coluna status.
    db_session.execute(text("ALTER TABLE vendas DROP COLUMN status"))
    db_session.commit()

    resposta = admin_client(client).get("/admin")
    assert resposta.status_code == 200, resposta.text[:500]
    assert "R$ 58.40" in resposta.text
    assert f"#{venda_id}" in resposta.text


def test_crud_usuario_e_ids_inexistentes(client, db_session):
    admin = admin_client(client)
    criado = admin.post(
        "/usuarios/novo",
        data={"nome": "Operador Teste", "email": "operador@example.test",
              "senha": "senha123", "role": "operador"},
        follow_redirects=False,
    )
    assert criado.status_code == 303
    usuario = db_session.query(Usuario).filter_by(email="operador@example.test").one()
    assert admin.get(f"/usuarios/{usuario.id}/editar").status_code == 200
    atualizado = admin.post(
        f"/usuarios/{usuario.id}/editar",
        data={"nome": "Operador Atualizado", "email": "operador@example.test",
              "role": "operador"},
        follow_redirects=False,
    )
    assert atualizado.status_code == 303
    assert admin.post(f"/usuarios/{usuario.id}/toggle-ativo", follow_redirects=False).status_code == 303
    assert admin.post(
        "/usuarios/999/editar",
        data={"nome": "Ausente", "email": "ausente@example.test", "role": "operador"},
    ).status_code == 404
    assert admin.post("/usuarios/999/toggle-ativo").status_code == 404


def test_crud_produto_e_validacao_movimentacao(client, db_session):
    admin = admin_client(client)
    criado = admin.post(
        "/produtos/novo",
        data={"nome": "Produto CRUD", "preco": "8.25", "plataforma": "PC",
              "estoque_atual": "4", "categoria_id": "0", "variacoes_json": "[]"},
        follow_redirects=False,
    )
    assert criado.status_code == 302
    produto = db_session.query(Produto).filter_by(nome="Produto CRUD").one()
    editado = admin.post(
        f"/produtos/{produto.id}/editar",
        data={"nome": "Produto CRUD Editado", "preco": "9.50", "plataforma": "PC",
              "estoque_atual": "6", "categoria_id": "0"},
        follow_redirects=False,
    )
    assert editado.status_code == 302
    assert admin.post(f"/produtos/{produto.id}/desativar", follow_redirects=False).status_code == 302
    assert admin.post(f"/produtos/{produto.id}/ativar", follow_redirects=False).status_code == 302
    assert admin.post(f"/produtos/{produto.id}/deletar", follow_redirects=False).status_code == 302

    invalida = admin.post(
        "/movimentacoes/nova",
        data={"produto_id": str(produto.id), "tipo": "invalido", "quantidade": "1",
              "preco_unitario": "9.5"},
        follow_redirects=False,
    )
    assert invalida.status_code == 400
