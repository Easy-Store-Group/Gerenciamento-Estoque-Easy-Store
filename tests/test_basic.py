def test_homepage(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Easy Store" in res.text or "PDV" in res.text


def test_sobre(client):
    res = client.get("/sobre-nos")
    assert res.status_code == 200
    assert "Sobre" in res.text or "sobre-nos" in res.text


def test_loading_global_sem_blur_e_com_spinner_maior():
    from pathlib import Path

    css = Path("app/static/css/global-loading.css").read_text(encoding="utf-8")

    assert "backdrop-filter: blur" not in css
    assert "filter: blur" not in css
    assert "backdrop-filter: none" in css
    assert "width: 48px" in css
    assert "height: 48px" in css
