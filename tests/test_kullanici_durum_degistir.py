from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from sunucu import (
    app,
    kullanici_durum_degistir,
    mevcut_kullanici_id,
)


def sahte_db(islem_rolu="MUDUR", hedef_rol="PSIKOLOG", aktif=True):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.side_effect = [
        (islem_rolu,),
        (hedef_rol, aktif),
    ]
    return conn, cursor


@pytest.mark.parametrize(
    "mevcut,beklenen",
    [(True, False), (False, True)],
)
def test_aktif_pasif_durum_degistirme(mevcut, beklenen):
    conn, cursor = sahte_db(aktif=mevcut)

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = kullanici_durum_degistir(
            kullanici_id=5,
            islem_yapan_id=10,
        )

    assert sonuc["yeni_durum"] is beklenen

    sorgular = [
        c.args for c in cursor.execute.call_args_list
    ]

    for tablo in ("kullanicilar", "personel"):
        assert any(
            f"UPDATE {tablo} SET aktif_mi" in args[0]
            and args[1] == (beklenen, 5)
            for args in sorgular
        )

    assert any(
        "INSERT INTO denetim_kayitlari" in args[0]
        for args in sorgular
    )

    conn.commit.assert_called_once()


def test_mudur_admin_durumunu_degistiremez():
    conn, _ = sahte_db(hedef_rol="ADMIN")

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=5,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    conn.commit.assert_not_called()


def test_kendi_hesabini_degistiremez():
    conn = MagicMock()

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=10,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 403
    conn.commit.assert_not_called()


def test_olmayan_kullanici_reddedilir():
    conn, _ = sahte_db()
    conn.cursor.return_value.fetchone.side_effect = [
        ("MUDUR",),
        None,
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=999,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 404
    conn.commit.assert_not_called()


def test_yetkisiz_http_erisim_reddedilir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/durum-degistir"
                )

        assert yanit.status_code == 403
        conn.commit.assert_not_called()
    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)


def test_veritabani_hatasi_hassas_bilgi_sizdirmaz():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    gizli_hata = (
        "password=GIZLI_TEST_SIFRESI "
        "SELECT * FROM kullanicilar "
        "/Users/test/proje/.env"
    )

    cursor.execute.side_effect = RuntimeError(gizli_hata)

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_durum_degistir(
                kullanici_id=5,
                islem_yapan_id=10,
            )

    assert hata.value.status_code == 500

    mesaj = str(hata.value.detail)

    assert "GIZLI_TEST_SIFRESI" not in mesaj
    assert "SELECT * FROM" not in mesaj
    assert ".env" not in mesaj

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_durum_degistirme_audit_parametreleri_dogru():
    conn, cursor = sahte_db(
        islem_rolu="MUDUR",
        hedef_rol="PSIKOLOG",
        aktif=True,
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        kullanici_durum_degistir(
            kullanici_id=5,
            islem_yapan_id=10,
        )

    audit_cagrilari = [
        c for c in cursor.execute.call_args_list
        if "INSERT INTO denetim_kayitlari" in c.args[0]
    ]

    assert len(audit_cagrilari) == 1
    assert audit_cagrilari[0].args[1] == (
        10,
        "UPDATE",
        "kullanicilar",
        5,
    )

    conn.commit.assert_called_once()


def test_mudur_http_uzerinden_kullanici_durumunu_degistirebilir():
    endpoint = next(
        route for route in app.routes
        if getattr(route, "path", None)
        == "/api/kullanicilar/{kullanici_id}/durum-degistir"
        and "PATCH" in getattr(route, "methods", set())
    )

    yetki_bagimliligi = endpoint.dependant.dependencies[0].call

    conn, cursor = sahte_db(
        islem_rolu="MUDUR",
        hedef_rol="PSIKOLOG",
        aktif=True,
    )

    app.dependency_overrides[yetki_bagimliligi] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                yanit = client.patch(
                    "/api/kullanicilar/5/durum-degistir"
                )

        assert yanit.status_code == 200
        assert yanit.json()["kullanici_id"] == 5
        assert yanit.json()["yeni_durum"] is False

        conn.commit.assert_called_once()

    finally:
        app.dependency_overrides.pop(yetki_bagimliligi, None)
