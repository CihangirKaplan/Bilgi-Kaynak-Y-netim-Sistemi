"""Veritabanı şeması eski/uyumsuzsa (eksik tablo ya da sütun) kullanıcı "beklenmeyen hata" yerine ne yapılacağını görür.

Sunucu: UndefinedColumn / UndefinedTable -> 503 + kod=SEMA_UYUMSUZ + anlaşılır mesaj; teknik ayrıntı yalnızca günlüğe yazılır.
İstemci: merkezi sarmalayıcı bu yanıtı tanır; ekranların gösterdiği hata metni anlaşılır mesaj olur.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import psycopg2
import pytests
import requests
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import client.api_yoneticisi as api
import server.girdi_korumasi as gk
from server.sunucu import app, mevcut_kullanici_id

SUTUN_HATASI = 'column "iptal_nedeni" does not exist\nLINE 1: SELECT iptal_nedeni FROM randevular'
TABLO_HATASI = 'relation "yeni_tablo" does not exist'


# ---------------------------------------------------------------- sunucu: çevirici
@pytest.mark.parametrize("hata", [
    psycopg2.errors.UndefinedColumn(SUTUN_HATASI),
    psycopg2.errors.UndefinedTable(TABLO_HATASI),
])
def test_eksik_sutun_ve_tablo_503_ve_anlasilir_mesaja_cevrilir(hata):
    durum, mesaj = gk.veritabani_hatasini_cevir(hata)
    assert durum == 503
    assert mesaj == gk.SEMA_UYUMSUZ_MESAJI
    assert "alembic upgrade head" in mesaj
    assert "iptal_nedeni" not in mesaj and "yeni_tablo" not in mesaj           # teknik ayrıntı istemciye gitmez


@pytest.mark.parametrize("hata", [
    psycopg2.errors.SyntaxError("syntax error at or near"),
    psycopg2.errors.UndefinedFunction("function foo() does not exist"),
    psycopg2.OperationalError("connection refused"),
    psycopg2.errors.InsufficientPrivilege("permission denied"),
])
def test_diger_programlama_hatalari_sema_uyumsuzlugu_sayilmaz(hata):
    assert gk.sema_uyumsuz_mu(hata) is False
    assert gk.veritabani_hatasini_cevir(hata) is None


def test_veri_hatalari_eskisi_gibi_cevrilir():
    assert gk.veritabani_hatasini_cevir(psycopg2.errors.UniqueViolation("x"))[0] == 409
    assert gk.veritabani_hatasini_cevir(psycopg2.errors.CheckViolation("x"))[0] == 422


# ---------------------------------------------------------------- sunucu: yakalayıcılar (küçük uygulama)
def kucuk_uygulama():
    kucuk = FastAPI()
    gk.merkezi_hata_yakalayicilari_kur(kucuk)

    @kucuk.get("/ham")
    def ham():
        raise psycopg2.errors.UndefinedColumn(SUTUN_HATASI)

    @kucuk.get("/sarilmis")
    def sarilmis():
        try:
            raise psycopg2.errors.UndefinedTable(TABLO_HATASI)
        except psycopg2.Error:
            raise HTTPException(status_code=500, detail="Veritabanı hatası.")

    @kucuk.get("/bilinmeyen")
    def bilinmeyen():
        raise psycopg2.errors.SyntaxError("syntax error")

    return TestClient(kucuk, raise_server_exceptions=False)


@pytest.mark.parametrize("yol", ["/ham", "/sarilmis"])
def test_ham_ve_sarilmis_hata_503_kodla_doner(yol):
    yanit = kucuk_uygulama().get(yol)
    assert yanit.status_code == 503
    assert yanit.json() == {"detail": gk.SEMA_UYUMSUZ_MESAJI, "kod": gk.SEMA_UYUMSUZ_KODU}
    assert "iptal_nedeni" not in yanit.text and "yeni_tablo" not in yanit.text


def test_teknik_ayrinti_sunucu_gunlugune_yazilir(caplog):
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        kucuk_uygulama().get("/ham")
        kucuk_uygulama().get("/sarilmis")
    metin = "\n".join(kayit.getMessage() for kayit in caplog.records)
    assert "şeması uyumsuz" in metin
    assert "/ham" in metin and "iptal_nedeni" in metin                  # hangi uç, hangi sütun
    assert "/sarilmis" in metin and "yeni_tablo" in metin


def test_bilinmeyen_veritabani_hatasi_eskisi_gibi_500_ve_kodsuz():
    yanit = kucuk_uygulama().get("/bilinmeyen")
    assert yanit.status_code == 500
    assert yanit.json() == {"detail": gk.GENEL_HATA_MESAJI}


# ---------------------------------------------------------------- sunucu: gerçek uygulama
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def sutunu_olmayan_baglanti():
    """İzin kontrolünü geçer; veri sorgusunda 'sütun yok' hatası verir (eski şemayı taklit eder)."""
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.return_value = (1,)

    def calistir(sorgu, *a, **k):
        if "FROM odalar" in str(sorgu):
            raise psycopg2.errors.UndefinedColumn(SUTUN_HATASI)

    imlec.execute.side_effect = calistir
    return conn


def test_gercek_uygulamada_eski_sema_503_verir_500_degil(istemci):
    with patch("server.sunucu.psycopg2.connect", return_value=sutunu_olmayan_baglanti()):
        yanit = istemci.get("/api/odalar")
    assert yanit.status_code == 503
    assert yanit.json()["kod"] == gk.SEMA_UYUMSUZ_KODU
    assert "alembic upgrade head" in yanit.json()["detail"]


def test_sunucu_ve_istemci_ayni_kodu_kullanir():
    assert api.SEMA_UYUMSUZ_KODU == gk.SEMA_UYUMSUZ_KODU


# ---------------------------------------------------------------- istemci
def yanit_yap(durum, veri, reason="Service Unavailable"):
    yanit = requests.Response()
    yanit.status_code = durum
    yanit._content = json.dumps(veri).encode("utf-8")
    yanit.reason = reason
    yanit.url = "http://127.0.0.1:8000/api/randevu-raporu"
    yanit.headers["Content-Type"] = "application/json"
    return yanit


SEMA_YANITI = {"detail": gk.SEMA_UYUMSUZ_MESAJI, "kod": gk.SEMA_UYUMSUZ_KODU}


def test_istemci_sema_yanitini_tanir_ve_ekranlarin_gosterdigi_hata_metnini_anlasilir_yapar():
    yanit = yanit_yap(503, SEMA_YANITI)
    with patch("client.api_yoneticisi.requests.request", return_value=yanit):
        donen = api.oturum_kontrollu_istek("GET", "http://127.0.0.1:8000/api/randevu-raporu")
    assert donen is yanit
    with pytest.raises(requests.HTTPError) as hata:
        donen.raise_for_status()
    assert "alembic upgrade head" in str(hata.value)               # ekranlardaki "Randevu raporu alınamadı: {hata}" metni
    assert "Internal Server Error" not in str(hata.value)


def test_istemci_api_hata_mesaji_sunucunun_anlasilir_mesajini_gosterir():
    assert api.api_hata_mesaji(yanit_yap(503, SEMA_YANITI)) == gk.SEMA_UYUMSUZ_MESAJI


@pytest.mark.parametrize("durum,veri", [
    (503, {"detail": "Servis geçici olarak kullanılamıyor."}),                      # kodsuz 503
    (503, {"detail": "x", "kod": "BASKA_KOD"}),                                      # başka kod
    (500, {"detail": gk.SEMA_UYUMSUZ_MESAJI, "kod": gk.SEMA_UYUMSUZ_KODU}),          # yalnızca 503'te geçerli
    (503, ["liste"]),                                                                # JSON ama sözlük değil
    (503, {"detail": 5, "kod": gk.SEMA_UYUMSUZ_KODU}),                               # detay metin değil
])
def test_istemci_baska_yanitlari_degistirmez(durum, veri):
    yanit = yanit_yap(durum, veri, reason="Original Reason")
    with patch("client.api_yoneticisi.requests.request", return_value=yanit):
        donen = api.oturum_kontrollu_istek("GET", "http://x/api/y")
    assert donen.reason == "Original Reason"
    assert api.sema_uyumsuz_detayi(yanit) is None


def test_istemci_gecersiz_govdeli_503u_bozmaz():
    yanit = requests.Response()
    yanit.status_code = 503
    yanit._content = b"<html>bad gateway</html>"
    yanit.reason = "Service Unavailable"
    assert api.sema_uyumsuz_detayi(yanit) is None
    assert api.api_hata_mesaji(yanit) == "Sunucuda bir hata oluştu. Lütfen daha sonra tekrar deneyin."


def test_istemci_mock_yanitlarla_cakismaz():
    # Mevcut testler MagicMock yanıt kullanabilir; 503 olmadığı için dokunulmamalı.
    sahte = MagicMock()
    sahte.status_code = 200
    assert api.sema_uyumsuz_detayi(sahte) is None
