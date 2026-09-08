def test_homepage(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Uma loja" in res.text or "Ponto de Venda" in res.text


def test_sobre(client):
    res = client.get("/sobre-nos")
    assert res.status_code == 200
    assert "Sobre" in res.text or "sobre-nos" in res.text
