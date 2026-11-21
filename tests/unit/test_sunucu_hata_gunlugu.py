"""Uçların yakalayıp genel 500/503 yanıtına çevirdiği beklenmeyen hatalar günlüğe asıl nedeniyle yazılır."""
import logging

import psycopg2
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from server.girdi_korumasi import merkezi_hata_yakalayicilari_kur


@pytest.fixture
def istemci():
    uygulama = FastAPI()
    merkezi_hata_yakalayicilari_kur(uygulama)

    @uygulama.get("/hata")
    def hata():
        try:
            return 1 / 0
        except Exception:
            raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")

    @uygulama.get("/kod-alinamadi")
    def kod():
        try:
            raise KeyError("siradaki_kod")
        except Exception:
            raise HTTPException(status_code=503, detail="Sıradaki danışan kodu şu an alınamadı.")

    @uygulama.get("/yinelenen")
    def yinelenen():
        try:
            raise psycopg2.errors.UniqueViolation("duplicate key")
        except Exception:
            raise HTTPException(status_code=500, detail="genel")

    @uygulama.get("/yok")
    def yok():
        raise HTTPException(status_code=404, detail="Bulunamadı.")

    @uygulama.get("/yasak")
    def yasak():
        raise HTTPException(status_code=403, detail="Yetkisiz.")

    return TestClient(uygulama)


def _kayitlar(caplog):
    return [k for k in caplog.records if k.name == "uvicorn.error" and k.levelno >= logging.ERROR]


def test_500_yaniti_degismez_ama_asil_hata_gunluge_yazilir(istemci, caplog):
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        yanit = istemci.get("/hata")
    assert yanit.status_code == 500 and yanit.json() == {"detail": "İşlem sırasında beklenmeyen bir sunucu hatası oluştu."}
    (kayit,) = _kayitlar(caplog)
    assert "GET /hata" in kayit.getMessage()
    metin = logging.Formatter().formatException(kayit.exc_info)
    assert "ZeroDivisionError" in metin and "hata" in metin                  # özgün hata ve hangi fonksiyonda olduğu zincirde


def test_503_de_yazilir(istemci, caplog):
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        yanit = istemci.get("/kod-alinamadi")
    assert yanit.status_code == 503
    (kayit,) = _kayitlar(caplog)
    assert "503" in kayit.getMessage() and "KeyError" in logging.Formatter().formatException(kayit.exc_info)


@pytest.mark.parametrize("yol, durum", [("/yok", 404), ("/yasak", 403)])
def test_beklenen_istemci_hatalari_gunluge_yazilmaz(istemci, caplog, yol, durum):
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        assert istemci.get(yol).status_code == durum
    assert _kayitlar(caplog) == []


def test_kullanici_girdisinden_gelen_veritabani_hatasi_409a_cevrilir_ve_hata_gibi_yazilmaz(istemci, caplog):
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        yanit = istemci.get("/yinelenen")
    assert yanit.status_code == 409
    assert _kayitlar(caplog) == []


def test_gercek_uygulamada_baglanti_hatasi_nedeniyle_yazilir(caplog, monkeypatch):
    import server.sunucu as sunucu

    def bagla(*a, **k):
        raise RuntimeError("veritabani yok (deneme)")

    monkeypatch.setattr(sunucu.psycopg2, "connect", bagla)
    sunucu.app.dependency_overrides[sunucu.mevcut_kullanici_id] = lambda: 1
    try:
        with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
            yanit = TestClient(sunucu.app).get("/api/yetkilerim")
    finally:
        sunucu.app.dependency_overrides.pop(sunucu.mevcut_kullanici_id, None)
    assert yanit.status_code == 500
    (kayit,) = _kayitlar(caplog)
    assert "/api/yetkilerim" in kayit.getMessage()
    assert "RuntimeError: veritabani yok (deneme)" in logging.Formatter().formatException(kayit.exc_info)
