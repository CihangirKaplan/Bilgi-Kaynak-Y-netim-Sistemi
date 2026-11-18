"""Gerçek PostgreSQL: IP bazlı giriş sınırı (giris_istek_limitleri) ve /api/login üzerinden 429."""
import os
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from server import giris_siniri
from server.sunucu import VT_AYARLARI, app


@pytest.fixture
def veritabani():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    conn.autocommit = True
    c = conn.cursor()
    c.execute("SELECT COALESCE(MAX(denetim_id), 0) FROM denetim_kayitlari")
    onceki_denetim = c.fetchone()[0]
    yield c
    c.execute("DELETE FROM giris_istek_limitleri WHERE anahtar LIKE 'gs\\_%%' OR anahtar = %s",
              (giris_siniri.istemci_anahtari(type("R", (), {"client": type("C", (), {"host": "testclient"})()})()),))
    c.execute("DELETE FROM denetim_kayitlari WHERE denetim_id > %s AND olay_turu::text = 'LOGIN_FAILED' AND kullanici_id IS NULL", (onceki_denetim,))
    conn.close()


def _anahtar():
    return f"gs_{uuid4().hex[:20]}"


def _say(c, anahtar):
    c.execute("SELECT istek_sayisi FROM giris_istek_limitleri WHERE anahtar = %s", (anahtar,))
    satir = c.fetchone()
    return satir[0] if satir else None


def test_sinira_kadar_engel_yok_sinirda_engel_var(veritabani):
    anahtar = _anahtar()
    for _ in range(giris_siniri.EN_FAZLA_BASARISIZ - 1):
        giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, anahtar)
    assert _say(veritabani, anahtar) == giris_siniri.EN_FAZLA_BASARISIZ - 1
    assert giris_siniri.engel_suresi(VT_AYARLARI, anahtar) == 0

    giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, anahtar)
    bekleme = giris_siniri.engel_suresi(VT_AYARLARI, anahtar)
    assert 1 <= bekleme <= giris_siniri.PENCERE_SANIYE


def test_baska_istemci_etkilenmez(veritabani):
    engelli, temiz = _anahtar(), _anahtar()
    for _ in range(giris_siniri.EN_FAZLA_BASARISIZ):
        giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, engelli)
    assert giris_siniri.engel_suresi(VT_AYARLARI, engelli) > 0
    assert giris_siniri.engel_suresi(VT_AYARLARI, temiz) == 0


def test_pencere_bitince_sayac_sifirlanir(veritabani):
    anahtar = _anahtar()
    for _ in range(giris_siniri.EN_FAZLA_BASARISIZ):
        giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, anahtar)
    veritabani.execute("UPDATE giris_istek_limitleri SET pencere_baslangici = NOW() - INTERVAL '10 minutes' WHERE anahtar = %s", (anahtar,))
    assert giris_siniri.engel_suresi(VT_AYARLARI, anahtar) == 0      # pencere dolmuş: engel kalkar
    giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, anahtar)
    assert _say(veritabani, anahtar) == 1                             # yeni pencere 1'den başlar


def test_eski_sayaclar_temizlenir(veritabani):
    eski = _anahtar()
    veritabani.execute("INSERT INTO giris_istek_limitleri (anahtar, pencere_baslangici, istek_sayisi) VALUES (%s, NOW() - INTERVAL '3 hours', 5)", (eski,))
    giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, _anahtar())
    assert _say(veritabani, eski) is None


def test_login_ucunda_sinir_asilinca_429(veritabani):
    istemci = TestClient(app)
    govde = {"kullanici_adi": f"yok_{uuid4().hex[:10]}", "parola": "yanlis"}
    for _ in range(giris_siniri.EN_FAZLA_BASARISIZ):
        assert istemci.post("/api/login", json=govde).status_code == 401
    yanit = istemci.post("/api/login", json=govde)
    assert yanit.status_code == 429
    assert int(yanit.headers["Retry-After"]) >= 1
    assert "çok fazla" in yanit.json()["detail"].lower()
