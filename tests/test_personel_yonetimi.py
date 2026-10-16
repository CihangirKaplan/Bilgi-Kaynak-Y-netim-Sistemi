from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import PersonelOlusturModeli
from sunucu import personel_olustur


def test_aktif_kullanici_icin_personel_olusturulur():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        (True, "PSIKOLOG"),  # Kullanıcı aktif
        (15,),              # Yeni personel ID
    ]

    yeni_personel = PersonelOlusturModeli(
        kullanici_id=25,
        personel_kodu="PSK-025"
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = personel_olustur(
            yeni_personel=yeni_personel,
            islem_yapan_id=10
        )

    assert sonuc["personel_id"] == 15
    assert sonuc["kullanici_id"] == 25
    assert sonuc["personel_kodu"] == "PSK-025"
    assert sonuc["aktif_mi"] is True

    mock_conn.commit.assert_called_once()

    # Audit kaydı oluşturulmuş mu?
    sorgular = [
        cagri.args[0]
        for cagri in mock_cursor.execute.call_args_list
    ]

    assert any(
        "INSERT INTO denetim_kayitlari" in sorgu
        for sorgu in sorgular
    )


def test_pasif_kullanici_icin_personel_olusturulamaz():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.return_value = (False, "PSIKOLOG")

    yeni_personel = PersonelOlusturModeli(
        kullanici_id=25,
        personel_kodu="PSK-025"
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            personel_olustur(
                yeni_personel=yeni_personel,
                islem_yapan_id=10
            )

    assert hata.value.status_code == 422
    mock_conn.commit.assert_not_called()
from psycopg2.errors import UniqueViolation
from pydantic import ValidationError


def test_olmayan_kullanici_icin_personel_olusturulamaz():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = None

    yeni_personel = PersonelOlusturModeli(
        kullanici_id=999,
        personel_kodu="PSK-999"
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            personel_olustur(yeni_personel, islem_yapan_id=10)

    assert hata.value.status_code == 404
    mock_conn.commit.assert_not_called()


def test_mukerrer_personel_kaydi_reddedilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.return_value = (True, "PSIKOLOG")
    mock_cursor.execute.side_effect = [
        None,
        UniqueViolation()
    ]

    yeni_personel = PersonelOlusturModeli(
        kullanici_id=25,
        personel_kodu="PSK-025"
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            personel_olustur(yeni_personel, islem_yapan_id=10)

    assert hata.value.status_code == 409
    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()


def test_bos_personel_kodu_reddedilir():
    with pytest.raises(ValidationError):
        PersonelOlusturModeli(
            kullanici_id=25,
            personel_kodu="   "
        )
def test_yetkisiz_kullanici_http_uzerinden_personel_olusturamaz():
    from fastapi.testclient import TestClient
    from sunucu import app, mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcının PERSONEL_TANIMLA izni yok
    mock_cursor.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                yanit = client.post(
                    "/api/personel",
                    json={
                        "kullanici_id": 25,
                        "personel_kodu": "PSK-025"
                    }
                )

        assert yanit.status_code == 403
        mock_conn.commit.assert_not_called()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
def test_personel_http_uzerinden_basariyla_olusturulur():
    from fastapi.testclient import TestClient
    from sunucu import app, mevcut_kullanici_id, izin_kontrol

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        (1,),                 # PERSONEL_TANIMLA izni var
        (True, "PSIKOLOG"),  # Kullanıcı aktif
        (15,),                # Oluşturulan personel ID
    ]

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                yanit = client.post(
                    "/api/personel",
                    json={
                        "kullanici_id": 25,
                        "personel_kodu": "PSK-025"
                    }
                )

        assert yanit.status_code == 201
        assert yanit.json()["personel_id"] == 15
        assert yanit.json()["personel_kodu"] == "PSK-025"
        mock_conn.commit.assert_called_once()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
from datetime import datetime
from sunucu import personel_listele


def test_personel_listesi_basariyla_getirilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    tarih = datetime(2026, 10, 16, 10, 0)

    mock_cursor.fetchall.return_value = [
        (1, 25, "psikolog1", "PSK-025", "PSIKOLOG", True, tarih),
        (2, 30, "memur1", "MEM-030", "MEMUR", True, tarih),
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = personel_listele(islem_yapan_id=10)

    assert len(sonuc) == 2
    assert sonuc[0]["personel_id"] == 1
    assert sonuc[0]["kullanici_adi"] == "psikolog1"
    assert sonuc[1]["personel_kodu"] == "MEM-030"

    mock_cursor.fetchall.assert_called_once()
    mock_conn.commit.assert_not_called()


def test_personel_listesi_bossa_bos_liste_doner():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchall.return_value = []

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = personel_listele(islem_yapan_id=10)

    assert sonuc == []
    mock_conn.commit.assert_not_called()
from sunucu import personel_detay


def test_personel_detay_basariyla_getirilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    tarih = datetime(2026, 10, 16, 10, 0)

    mock_cursor.fetchone.return_value = (
        15, 25, "psikolog1", "PSK-025",
        "PSIKOLOG", True, tarih
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = personel_detay(
            personel_id=15,
            islem_yapan_id=10
        )

    assert sonuc["personel_id"] == 15
    assert sonuc["kullanici_id"] == 25
    assert sonuc["personel_kodu"] == "PSK-025"
    assert sonuc["rol_adi"] == "PSIKOLOG"

    mock_conn.commit.assert_not_called()


def test_olmayan_personel_detayi_404_doner():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = None

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            personel_detay(
                personel_id=999,
                islem_yapan_id=10
            )

    assert hata.value.status_code == 404
    mock_conn.commit.assert_not_called()


def test_gecersiz_personel_id_reddedilir():
    with pytest.raises(HTTPException) as hata:
        personel_detay(
            personel_id=0,
            islem_yapan_id=10
        )

    assert hata.value.status_code == 422
from modeller import PersonelGuncelleModeli
from sunucu import personel_guncelle


def test_personel_basariyla_guncellenir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = (15, "PSK-025", True)

    guncelleme = PersonelGuncelleModeli(
        personel_kodu="PSK-NEW",
        aktif_mi=False
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = personel_guncelle(
            personel_id=15,
            guncelleme=guncelleme,
            islem_yapan_id=10
        )

    assert sonuc["personel_kodu"] == "PSK-NEW"
    assert sonuc["aktif_mi"] is False
    mock_conn.commit.assert_called_once()

    sorgular = [
        cagri.args[0]
        for cagri in mock_cursor.execute.call_args_list
    ]

    assert any("UPDATE personel" in sorgu for sorgu in sorgular)
    assert any("INSERT INTO denetim_kayitlari" in sorgu for sorgu in sorgular)


def test_olmayan_personel_guncellenemez():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = None

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            personel_guncelle(
                personel_id=999,
                guncelleme=PersonelGuncelleModeli(aktif_mi=False),
                islem_yapan_id=10
            )

    assert hata.value.status_code == 404
    mock_conn.commit.assert_not_called()


def test_bos_guncelleme_reddedilir():
    with pytest.raises(HTTPException) as hata:
        personel_guncelle(
            personel_id=15,
            guncelleme=PersonelGuncelleModeli(),
            islem_yapan_id=10
        )

    assert hata.value.status_code == 422


def test_personel_kodu_baska_kayitta_kullaniliyorsa_reddedilir():
    from psycopg2.errors import UniqueViolation

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.return_value = (15, "PSK-025", True)
    mock_cursor.execute.side_effect = [
        None,
        UniqueViolation()
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            personel_guncelle(
                personel_id=15,
                guncelleme=PersonelGuncelleModeli(
                    personel_kodu="PSK-030"
                ),
                islem_yapan_id=10
            )

    assert hata.value.status_code == 409
    mock_conn.rollback.assert_called_once()
    mock_conn.commit.assert_not_called()
@pytest.mark.parametrize(
    "method, url, payload",
    [
        ("get", "/api/personel", None),
        ("get", "/api/personel/15", None),
        ("patch", "/api/personel/15", {"aktif_mi": False}),
    ]
)
def test_yetkisiz_personel_islemleri_reddedilir(method, url, payload):
    from fastapi.testclient import TestClient
    from sunucu import app, mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # PERSONEL_TANIMLA izni bulunmuyor
    mock_cursor.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 10

    try:
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with TestClient(app) as client:
                yanit = client.request(
                    method.upper(),
                    url,
                    json=payload
                )

        assert yanit.status_code == 403
        mock_conn.commit.assert_not_called()

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)