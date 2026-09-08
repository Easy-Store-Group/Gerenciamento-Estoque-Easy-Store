import json


def test_register_and_login(client):
    # Register
    payload = {"nome": "Test User", "email": "test@example.com", "senha": "secret123", "plano_premium": False}
    res = client.post("/auth/api/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "usuario_id" in data

    # Login (JSON)
    login_payload = {"email": "test@example.com", "senha": "secret123"}
    res2 = client.post("/auth/login-json", json=login_payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2.get("email") == "test@example.com"
    assert "token" in data2 and data2["token"]


def test_produtos_publicos_empty(client):
    # Should respond with page even when no products exist
    res = client.get("/auth/produtos")
    assert res.status_code == 200
    assert "produtos" in res.text or "Nenhum produto" in res.text
