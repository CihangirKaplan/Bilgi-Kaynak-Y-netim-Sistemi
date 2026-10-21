from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import danisma_oturumu_baslat


def test_danisma_oturumu_baslat_basarili():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),  # Aktif öğrenci
        None,  # Açık oturum yok
        (10, datetime(2026, 10, 21, 10, 0)),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = danisma_oturumu_baslat(kullanici_id=1)

    assert sonuc["durum"] == "AKTIF"
    assert sonuc["oturum_id"] == 10
    conn.commit.assert_called_once()


def test_ikinci_oturum_engellenir():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),   # Aktif öğrenci
        (10,),  # Zaten açık oturum var
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            danisma_oturumu_baslat(kullanici_id=1)

    assert hata.value.status_code == 409
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_aktif_ogrenci_bulunamadi():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = None

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            danisma_oturumu_baslat(kullanici_id=1)

    assert hata.value.status_code == 403
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_danisma_oturumu_bitir_basarili():
    from sunucu import danisma_oturumu_bitir

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),   # Aktif öğrenci
        (10,),  # Açık oturum
        (
            datetime(2026, 10, 21, 9, 0),
            datetime(2026, 10, 21, 12, 25),
        ),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = danisma_oturumu_bitir(kullanici_id=1)

    assert sonuc["durum"] == "TAMAMLANDI"
    assert sonuc["oturum_id"] == 10
    assert sonuc["toplam_dakika"] == 205
    assert sonuc["calisilan_sure"] == "3 saat 25 dakika"

    conn.commit.assert_called_once()


def test_acik_oturum_yoksa_bitirilemez():
    from sunucu import danisma_oturumu_bitir

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),  # Aktif öğrenci
        None,  # Açık oturum yok
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            danisma_oturumu_bitir(kullanici_id=1)

    assert hata.value.status_code == 409
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()


def test_aktif_danisma_oturumu_suresi():
    from sunucu import danisma_aktif_oturum

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),
        (
            10,
            datetime(2026, 10, 21, 9, 0),
            datetime(2026, 10, 21, 12, 25),
        ),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = danisma_aktif_oturum(kullanici_id=1)

    assert sonuc["durum"] == "AKTIF"
    assert sonuc["toplam_dakika"] == 205
    assert sonuc["calisilan_sure"] == "3 saat 25 dakika"


def test_aktif_danisma_oturumu_yok():
    from sunucu import danisma_aktif_oturum

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),
        None,
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = danisma_aktif_oturum(kullanici_id=1)

    assert sonuc["durum"] == "PASIF"
    assert sonuc["oturum_id"] is None


def test_danisma_oturum_gecmisi():
    from sunucu import danisma_oturum_gecmisi

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.return_value = (1,)
    cursor.fetchall.return_value = [
        (
            10,
            datetime(2026, 10, 21, 9, 0),
            datetime(2026, 10, 21, 12, 25),
            False,
        )
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = danisma_oturum_gecmisi(kullanici_id=1)

    assert sonuc["toplam_kayit"] == 1
    assert sonuc["oturumlar"][0]["toplam_dakika"] == 205
    assert sonuc["oturumlar"][0]["calisilan_sure"] == "3 saat 25 dakika"
    assert sonuc["oturumlar"][0]["onaylandi_mi"] is False


def test_danisma_oturum_gecmisi_bos():
    from sunucu import danisma_oturum_gecmisi

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.return_value = (1,)
    cursor.fetchall.return_value = []

    with patch("sunucu.psycopg2.connect", return_value=conn):
        sonuc = danisma_oturum_gecmisi(kullanici_id=1)

    assert sonuc["toplam_kayit"] == 0
    assert sonuc["oturumlar"] == []


def test_veritabani_cakismasi_http_409():
    from psycopg2.errors import UniqueViolation

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),  # Aktif öğrenci bulundu
        None,  # Başlangıçta açık oturum bulunamadı
    ]

    # INSERT sırasında PostgreSQL benzersizlik hatası versin.
    cursor.execute.side_effect = [
        None,  # Öğrenci SELECT
        None,  # Açık oturum SELECT
        UniqueViolation("uq_danisma_tek_acik_oturum"),
    ]

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            danisma_oturumu_baslat(kullanici_id=1)

    assert hata.value.status_code == 409
    assert hata.value.detail == (
        "Zaten devam eden bir göreviniz bulunuyor."
    )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()
