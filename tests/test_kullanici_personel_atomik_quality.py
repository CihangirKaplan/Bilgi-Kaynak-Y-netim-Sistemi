
"""
TKYS QA-001
Kullanici, personel ve ogrenci kayitlarinin
tek transaction icinde olusturulmasi.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import KullaniciOlusturModeli
from sunucu import kullanici_olustur


def sahte_veritabani(rol="PSIKOLOG", hatali_tablo=None):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    durum = {"son_sorgu": "", "parametreler": None}

    def execute(sorgu, parametreler=None):
        durum["son_sorgu"] = sorgu.upper()
        durum["parametreler"] = parametreler

        if hatali_tablo:
            if f"INSERT INTO {hatali_tablo.upper()}" in sorgu.upper():
                raise RuntimeError("QA001_TEST_VERITABANI_HATASI")

    def fetchone():
        sorgu = durum["son_sorgu"]

        if "FROM KULLANICILAR K JOIN ROLLER R" in sorgu:
            return ("ADMIN",)

        if "ROL_IZINLERI" in sorgu:
            return (1,)

        if "SELECT ROL_ADI FROM ROLLER" in sorgu:
            return (rol,)

        if "INSERT INTO KULLANICILAR" in sorgu:
            return (25,)

        if "INSERT INTO PERSONEL" in sorgu:
            return (15,)

        if "INSERT INTO OGRENCILER" in sorgu:
            return (17,)

        return None

    cursor.execute.side_effect = execute
    cursor.fetchone.side_effect = fetchone
    def fetchall():
        # Oda doğrulama sorgusu: istenen odaların hepsi aktif sayılır.
        if "FROM ODALAR" in durum["son_sorgu"]:
            return [(oda_id,) for oda_id in durum["parametreler"][0]]
        return []

    cursor.fetchall.side_effect = fetchall

    return conn, cursor


def sorgular(cursor):
    return [
        c.args[0].upper()
        for c in cursor.execute.call_args_list
    ]


def test_kullanici_ve_personel_birlikte_olusturulur():
    conn, cursor = sahte_veritabani()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.gecici_parola_uret", return_value="Test123!"),
        patch("sunucu.parola_hashle", return_value="hash"),
    ):
        sonuc = kullanici_olustur(
            KullaniciOlusturModeli(
                kullanici_adi="yeni_psikolog",
                rol_id=1,
                oda_idleri=[2],
            ),
            kullanici_id=10,
        )

    assert sonuc["durum"] == "basarili"

    sql = sorgular(cursor)

    assert any("INSERT INTO KULLANICILAR" in s for s in sql)
    assert any("INSERT INTO PERSONEL" in s for s in sql)

    audit_sayisi = sum(
        "INSERT INTO DENETIM_KAYITLARI" in s
        for s in sql
    )

    assert audit_sayisi >= 2

    conn.commit.assert_called_once()
    conn.close.assert_called_once()


def test_personel_hatasinda_kullanici_geri_alinir():
    conn, cursor = sahte_veritabani(
        hatali_tablo="personel",
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.gecici_parola_uret", return_value="Test123!"),
        patch("sunucu.parola_hashle", return_value="hash"),
    ):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(
                KullaniciOlusturModeli(
                    kullanici_adi="yeni_psikolog",
                    rol_id=1,
                    oda_idleri=[2],
                ),
                kullanici_id=10,
            )

    assert hata.value.status_code == 500

    assert "QA001_TEST_VERITABANI_HATASI" not in str(
        hata.value.detail
    )

    sql = sorgular(cursor)

    assert any("INSERT INTO KULLANICILAR" in s for s in sql)
    assert any("INSERT INTO PERSONEL" in s for s in sql)

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_danisma_ogrencisi_kayitlari_birlikte_olusturulur():
    conn, cursor = sahte_veritabani(
        rol="DANISMA_OGRENCISI",
    )

    yeni = KullaniciOlusturModeli(
        kullanici_adi="ornek_ogrenci",
        rol_id=4,
        ad_soyad="Ornek Ogrenci",
        ogrenci_numarasi="20260001",
        telefon="5551234567",
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.gecici_parola_uret", return_value="Test123!"),
        patch("sunucu.parola_hashle", return_value="hash"),
    ):
        kullanici_olustur(
            yeni,
            kullanici_id=10,
        )

    sql = sorgular(cursor)

    assert any("INSERT INTO KULLANICILAR" in s for s in sql)
    assert any("INSERT INTO PERSONEL" in s for s in sql)
    assert any("INSERT INTO OGRENCILER" in s for s in sql)

    conn.commit.assert_called_once()
    conn.close.assert_called_once()



def test_ogrenci_hatasinda_tum_islem_geri_alinir():
    conn, cursor = sahte_veritabani(
        rol="DANISMA_OGRENCISI",
        hatali_tablo="ogrenciler",
    )

    yeni = KullaniciOlusturModeli(
        kullanici_adi="ornek_ogrenci",
        rol_id=4,
        ad_soyad="Ornek Ogrenci",
        ogrenci_numarasi="20260001",
        telefon="5551234567",
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.gecici_parola_uret", return_value="Test123!"),
        patch("sunucu.parola_hashle", return_value="hash"),
    ):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(yeni, kullanici_id=10)

    assert hata.value.status_code == 500

    sql = sorgular(cursor)

    assert any("INSERT INTO KULLANICILAR" in s for s in sql)
    assert any("INSERT INTO PERSONEL" in s for s in sql)
    assert any("INSERT INTO OGRENCILER" in s for s in sql)

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_audit_hatasinda_tum_islem_geri_alinir():
    conn, cursor = sahte_veritabani(
        hatali_tablo="denetim_kayitlari",
    )

    yeni = KullaniciOlusturModeli(
        kullanici_adi="yeni_psikolog",
        rol_id=1,
        oda_idleri=[2],
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.gecici_parola_uret", return_value="Test123!"),
        patch("sunucu.parola_hashle", return_value="hash"),
    ):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(yeni, kullanici_id=10)

    assert hata.value.status_code == 500
    assert "QA001_TEST_VERITABANI_HATASI" not in str(
        hata.value.detail
    )

    sql = sorgular(cursor)

    assert any("INSERT INTO KULLANICILAR" in s for s in sql)
    assert any("INSERT INTO PERSONEL" in s for s in sql)
    assert any("INSERT INTO DENETIM_KAYITLARI" in s for s in sql)

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
