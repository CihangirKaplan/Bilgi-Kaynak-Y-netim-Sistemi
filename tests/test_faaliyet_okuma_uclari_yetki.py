"""Faaliyet okuma uçlarının rol izni testleri (SEC-T02).

Bu uçlar eskiden yalnızca "giriş yapmış olmayı" istiyordu; izni olmayan bir rol
öğrenci adı/numarası ve faaliyet kayıtlarını okuyabiliyordu. Artık
FAALIYET_KAYITLARI_DUZENLE izni zorunludur (yazma uçlarıyla aynı izin).
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

UCLAR = [
    "/api/faaliyet-kayitlari",
    "/api/faaliyetler",
    "/api/faaliyet-birimleri",
    "/api/ogrenciler-liste",
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


@pytest.mark.parametrize("yol", UCLAR)
def test_izni_olmayan_rol_403_alir_ve_veri_sorgulanmaz(yol):
    conn, cursor = sahte_baglanti(izin_var=0)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(yol)
    assert yanit.status_code == 403
    sorgular = [c.args[0] for c in cursor.execute.call_args_list]
    assert all("izin_adi" in s for s in sorgular)


@pytest.mark.parametrize("yol", UCLAR)
def test_izni_olan_rol_listeyi_gorur(yol):
    conn, _ = sahte_baglanti(izin_var=1)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(yol)
    assert yanit.status_code == 200
    assert yanit.json() == []


@pytest.mark.parametrize("yol", UCLAR)
def test_tokensiz_istek_reddedilir(yol):
    app.dependency_overrides.pop(mevcut_kullanici_id, None)
    assert istek_at(yol).status_code in (401, 403)