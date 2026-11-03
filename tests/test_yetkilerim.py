"""Giriş yapan kullanıcının kendi izinlerini döndüren uç (istemci menüsü bu yanıttan çizilir)."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id

YOL = "/api/yetkilerim"


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 7
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def istek(satirlar):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchall.return_value = satirlar
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            return istemci.get(YOL), cursor, conn


def test_rolun_acik_izinleri_listelenir():
    yanit, cursor, _ = istek([("PSIKOLOG", "RANDEVU_DUZENLE"), ("PSIKOLOG", "RANDEVU_OLUSTUR")])
    assert yanit.status_code == 200
    assert yanit.json() == {"rol_adi": "PSIKOLOG", "izinler": ["RANDEVU_DUZENLE", "RANDEVU_OLUSTUR"]}
    sorgu, parametreler = cursor.execute.call_args.args
    assert "izin_var = 1" in sorgu          # yalnızca açık olan izinler
    assert parametreler == (7,)             # yalnızca kendi kullanıcısı


def test_hic_izni_olmayan_rol_bos_liste_alir():
    yanit, _, _ = istek([("YENI_ROL", None)])
    assert yanit.status_code == 200
    assert yanit.json() == {"rol_adi": "YENI_ROL", "izinler": []}


def test_kullanici_bulunamazsa_404():
    yanit, _, _ = istek([])
    assert yanit.status_code == 404


def test_veritabani_hatasinda_ayrinti_sizdirilmaz():
    conn = MagicMock()
    conn.cursor.return_value.execute.side_effect = RuntimeError("gizli ayrıntı: tablo adı")
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            yanit = istemci.get(YOL)
    assert yanit.status_code == 500
    assert "gizli" not in yanit.text


def test_baglanti_her_durumda_kapatilir():
    _, cursor, conn = istek([("ADMIN", "ROL_OLUSTUR")])
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_tokensiz_istek_reddedilir():
    app.dependency_overrides.pop(mevcut_kullanici_id, None)
    with TestClient(app) as istemci:
        assert istemci.get(YOL).status_code in (401, 403)
