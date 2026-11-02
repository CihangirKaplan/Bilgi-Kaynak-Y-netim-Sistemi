"""Oda, psikolog listesi ve dashboard uçlarının rol izni testleri (SEC-T02).

Bu uçlar eskiden yalnızca "giriş yapmış olmayı" istiyordu. Artık her biri,
istemcide ilgili ekranı gören rollerin sahip olduğu izne bağlıdır.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

UCLAR = [
    ("/api/odalar", "ODA_DURUMU_GORUNTULE"),
    ("/api/psikologlar", "TAKVIM_GORUNTULE"),
    ("/api/dashboard/bugunku-randevular", "TAKVIM_GORUNTULE"),
    ("/api/dashboard/ozet", "CIHAZ_ENVANTER_YONET"),
    ("/api/dashboard/bugunku-rezervasyonlar", "CIHAZ_ENVANTER_YONET"),
    ("/api/dashboard/yaklasan-islemler", "CIHAZ_ENVANTER_YONET"),
]


def sahte_baglanti(izin_var):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (izin_var,)
    cursor.fetchall.return_value = []
    return conn, cursor


def istek_at(yol):
    with TestClient(app) as istemci:
        return istemci.get(yol)


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


@pytest.mark.parametrize("yol, izin", UCLAR)
def test_izni_olmayan_rol_403_alir_ve_dogru_izin_sorgulanir(yol, izin):
    conn, cursor = sahte_baglanti(izin_var=0)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(yol)
    assert yanit.status_code == 403
    assert len(cursor.execute.call_args_list) == 1
    sorgu, parametreler = cursor.execute.call_args.args
    assert "izin_adi" in sorgu
    assert parametreler == (5, izin)


@pytest.mark.parametrize("yol, izin", UCLAR)
def test_izni_olan_rol_ucu_kullanabilir(yol, izin):
    conn, _ = sahte_baglanti(izin_var=1)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(yol)
    assert yanit.status_code != 403


@pytest.mark.parametrize("yol, izin", UCLAR)
def test_tokensiz_istek_reddedilir(yol, izin):
    app.dependency_overrides.pop(mevcut_kullanici_id, None)
    assert istek_at(yol).status_code in (401, 403)