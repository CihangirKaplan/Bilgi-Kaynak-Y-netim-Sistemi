"""API dokümantasyon sayfaları (/docs, /redoc, /openapi.json) varsayılan kapalıdır; yalnızca TKYS_API_DOCS=1 ile açılır.

Kapalı ofis ağında bile, ağdaki herkesin tüm uç noktaların listesini giriş yapmadan görmesi gerekmez.
Sunucunun ayakta olduğunu anlamak için kimlik doğrulaması istemeyen /api/saglik ucu kullanılır.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import sunucu

KOK = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("deger", [None, "", "0", "false", "evet", "2", " "])
def test_varsayilan_ve_gecersiz_degerlerde_belgeler_kapali(monkeypatch, deger):
    if deger is None:
        monkeypatch.delenv("TKYS_API_DOCS", raising=False)
    else:
        monkeypatch.setenv("TKYS_API_DOCS", deger)
    assert sunucu.api_belgeleri_acik_mi() is False


@pytest.mark.parametrize("deger", ["1", " 1 ", "1\n"])
def test_yalnizca_1_belgeleri_acar(monkeypatch, deger):
    monkeypatch.setenv("TKYS_API_DOCS", deger)
    assert sunucu.api_belgeleri_acik_mi() is True


def test_kapaliyken_uc_belge_adresi_de_404_doner():
    istemci = TestClient(sunucu.fastapi_olustur(False))
    for yol in ("/docs", "/redoc", "/openapi.json"):
        assert istemci.get(yol).status_code == 404, yol


def test_acikken_belge_adresleri_calisir():
    istemci = TestClient(sunucu.fastapi_olustur(True))
    assert istemci.get("/docs").status_code == 200
    assert istemci.get("/redoc").status_code == 200
    assert istemci.get("/openapi.json").status_code == 200


def test_gercek_uygulama_ortam_degiskenine_gore_kurulur():
    # .env dosyasında TKYS_API_DOCS=1 olan geliştirme bilgisayarında da geçer.
    acik = sunucu.api_belgeleri_acik_mi()
    assert (sunucu.app.openapi_url is not None) == acik
    assert (sunucu.app.docs_url is not None) == acik
    assert (sunucu.app.redoc_url is not None) == acik


def test_belgeler_kapaliyken_sema_koddan_yine_alinabilir():
    # Fuzz testi gibi araçlar HTTP adresine ihtiyaç duymadan şemayı app.openapi() ile okur.
    assert "/api/login" in sunucu.app.openapi()["paths"]


def test_saglik_ucu_kimlik_istemeden_calisir():
    yanit = TestClient(sunucu.app).get("/api/saglik")
    assert yanit.status_code == 200
    assert yanit.json() == {"durum": "calisiyor"}


def test_saglik_ucu_veritabanina_baglanmaz(monkeypatch):
    def baglanma(*args, **kwargs):
        raise AssertionError("Sağlık ucu veritabanına bağlanmamalı.")

    monkeypatch.setattr(sunucu.psycopg2, "connect", baglanma)
    assert TestClient(sunucu.app).get("/api/saglik").status_code == 200


def test_kilavuz_readme_ve_env_ornegi_guncel():
    kilavuz = (KOK / "docs" / "Sunucu_Kurulum_Kilavuzu.md").read_text(encoding="utf-8")
    assert ":8000/api/saglik" in kilavuz
    assert ":8000/docs" not in kilavuz
    assert "TKYS_API_DOCS=1" in (KOK / "README.md").read_text(encoding="utf-8")
    assert "TKYS_API_DOCS" in (KOK / ".env.example").read_text(encoding="utf-8")
