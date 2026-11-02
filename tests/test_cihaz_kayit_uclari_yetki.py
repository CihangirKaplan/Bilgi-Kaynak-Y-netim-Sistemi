"""Bakım, kalibrasyon ve arıza uçlarının rol izni testleri (SEC-T02 / SEC-T03).

Bu uçlar eskiden yalnızca "giriş yapmış olmayı" istiyordu; yetkisi olmayan bir rol
(örn. Psikolog, Danışma Öğrencisi) kayıtları okuyabiliyor, arıza kaydı ekleyip
değiştirebiliyordu. Artık ilgili izin zorunludur.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

ARIZA_BODY = {
    "cihaz_id": 1,
    "ariza_baslik": "Ekran sorunu",
    "ariza_aciklama": "Cihaz açılmıyor",
    "aciliyet": "Orta",
}
ARIZA_GUNCELLEME_BODY = {
    "ariza_baslik": "Ekran sorunu",
    "ariza_aciklama": "Cihaz açılmıyor",
    "aciliyet": "Orta",
    "cozuldu_mu": True,
}

UCLAR = [
    ("get", "/api/bakimlar", None),
    ("get", "/api/kalibrasyonlar", None),
    ("get", "/api/arizalar", None),
    ("post", "/api/arizalar", ARIZA_BODY),
    ("put", "/api/arizalar/1", ARIZA_GUNCELLEME_BODY),
]


def sahte_baglanti(izin_var):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (izin_var,)
    cursor.fetchall.return_value = []
    return conn, cursor


def istek_at(metot, yol, govde):
    with TestClient(app) as istemci:
        return getattr(istemci, metot)(yol, **({"json": govde} if govde is not None else {}))


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


@pytest.mark.parametrize("metot, yol, govde", UCLAR)
def test_izni_olmayan_rol_403_alir_ve_veri_degismez(metot, yol, govde):
    conn, cursor = sahte_baglanti(izin_var=0)

    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at(metot, yol, govde)

    assert yanit.status_code == 403
    conn.commit.assert_not_called()
    sorgular = [c.args[0].strip().upper() for c in cursor.execute.call_args_list]
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in sorgular)


@pytest.mark.parametrize("yol", ["/api/bakimlar", "/api/kalibrasyonlar", "/api/arizalar"])
def test_izni_olan_rol_listeleri_gorur(yol):
    conn, _ = sahte_baglanti(izin_var=1)

    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istek_at("get", yol, None)

    assert yanit.status_code == 200
    assert yanit.json() == []


@pytest.mark.parametrize("metot, yol, govde", UCLAR)
def test_tokensiz_istek_reddedilir(metot, yol, govde):
    app.dependency_overrides.pop(mevcut_kullanici_id, None)
    yanit = istek_at(metot, yol, govde)
    assert yanit.status_code in (401, 403)