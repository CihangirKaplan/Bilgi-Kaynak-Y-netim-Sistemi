"""
GET /api/randevular/doluluk: seçilen gün için oda ve/veya psikologun dolu saat aralıkları.

Yalnızca zaman aralığı ve dolu olanın türü döner; kimlik bilgisi (danışan kodu, psikolog adı) dönmez.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

YOL = "/api/randevular/doluluk"


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def baglanti(izin=1, satirlar=()):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (izin,)
    cursor.fetchall.return_value = list(satirlar)
    return conn, cursor


def istek_at(conn, **params):
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            return istemci.get(YOL, params=params)


def doluluk_sorgusu(cursor):
    """İzin sorgusundan sonra çalışan doluluk sorgusu (sql, parametreler)."""
    return cursor.execute.call_args_list[-1].args


def test_izni_olmayan_rol_403_alir_ve_doluluk_sorgulanmaz():
    conn, cursor = baglanti(izin=0)
    yanit = istek_at(conn, tarih="2026-12-01", oda_id=1)
    assert yanit.status_code == 403
    assert len(cursor.execute.call_args_list) == 1  # yalnızca izin sorgusu


def test_oda_ve_psikolog_ikisi_de_yoksa_422():
    conn, cursor = baglanti()
    yanit = istek_at(conn, tarih="2026-12-01")
    assert yanit.status_code == 422
    assert not any("FROM randevular" in c.args[0] for c in cursor.execute.call_args_list)


@pytest.mark.parametrize("params", [
    {"tarih": "gecersiz", "oda_id": 1},
    {"tarih": "2026-12-01", "oda_id": 0},
    {"tarih": "2026-12-01", "psikolog_id": -3},
])
def test_gecersiz_parametreler_422(params):
    conn, _ = baglanti()
    assert istek_at(conn, **params).status_code == 422


def test_tarih_zorunlu():
    conn, _ = baglanti()
    assert istek_at(conn, oda_id=1).status_code == 422


def test_yalnizca_aralik_ve_sebep_doner_kimlik_bilgisi_yok():
    gun = datetime(2026, 12, 1)
    satirlar = [
        (gun.replace(hour=10), gun.replace(hour=11), True, False),
        (gun.replace(hour=13), gun.replace(hour=15), False, True),
        (gun.replace(hour=15), gun.replace(hour=16), True, True),
    ]
    conn, _ = baglanti(satirlar=satirlar)
    yanit = istek_at(conn, tarih="2026-12-01", oda_id=1, psikolog_id=3)

    assert yanit.status_code == 200
    veri = yanit.json()
    assert veri["tarih"] == "2026-12-01"
    assert veri["dolu_araliklar"] == [
        {"baslangic": "2026-12-01T10:00:00", "bitis": "2026-12-01T11:00:00", "sebep": "oda"},
        {"baslangic": "2026-12-01T13:00:00", "bitis": "2026-12-01T15:00:00", "sebep": "psikolog"},
        {"baslangic": "2026-12-01T15:00:00", "bitis": "2026-12-01T16:00:00", "sebep": "oda_ve_psikolog"},
    ]
    for aralik in veri["dolu_araliklar"]:
        assert set(aralik) == {"baslangic", "bitis", "sebep"}


def test_bos_gun_bos_liste_doner():
    conn, _ = baglanti(satirlar=[])
    yanit = istek_at(conn, tarih="2026-12-01", oda_id=1)
    assert yanit.status_code == 200
    assert yanit.json()["dolu_araliklar"] == []


def test_sorgu_yalnizca_planlanan_randevulari_ve_secilen_gunu_kapsar():
    conn, cursor = baglanti()
    istek_at(conn, tarih="2026-12-01", oda_id=2, psikolog_id=3)

    sorgu, parametreler = doluluk_sorgusu(cursor)
    assert "durum = 'PLANLANDI'" in sorgu
    assert "randevu_id <>" not in sorgu
    gun_basi = datetime(2026, 12, 1)
    assert parametreler == [2, 3, 2, 3, gun_basi + timedelta(days=1), gun_basi]


def test_haric_randevu_sorguya_eklenir():
    conn, cursor = baglanti()
    istek_at(conn, tarih="2026-12-01", oda_id=2, haric_randevu_id=9)

    sorgu, parametreler = doluluk_sorgusu(cursor)
    assert "randevu_id <> %s" in sorgu
    assert parametreler[-1] == 9
    assert parametreler[:2] == [2, None]  # psikolog verilmedi


def test_baglanti_her_durumda_kapatilir():
    conn, cursor = baglanti()
    istek_at(conn, tarih="2026-12-01", oda_id=1)
    cursor.close.assert_called()
    conn.close.assert_called()
