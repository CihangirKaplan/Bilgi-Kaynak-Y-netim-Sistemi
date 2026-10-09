from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import RandevuGuncelleModeli, RandevuOlusturModeli
from sunucu import (
    randevu_guncelle,
    randevu_iptal_et,
    randevu_olustur,
    randevulari_listele,
)


def test_psikolog_baskasinin_randevusunu_guncelleyemez():
    # Sahte veritabanı bağlantısı
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Sorguların döndüreceği sahte sonuçlar:
    # 1. Randevu bilgisi (psikolog_id = 2)
    # 2. Giriş yapan kullanıcının rolü
    # 3. Giriş yapan psikoloğun personel_id değeri
    mock_cursor.fetchone.side_effect = [
        (
            "TEST-D-001",
            2,
            1,
            "2026-10-15T10:00:00",
            "2026-10-15T11:00:00",
            "PLANLANDI",
        ),
        ("PSIKOLOG",),
        (1,),
    ]

    # Gerçek veritabanına bağlanılmasını engelle
    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=5,
                guncelleme=RandevuGuncelleModeli(oda_id=1),
                kullanici_id=10,
            )

    assert hata.value.status_code == 403
    assert hata.value.detail == (
        "Yalnızca kendi randevunuzu düzenleyebilirsiniz."
    )

    # Güncelleme yapılmadığını da doğrula
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]
    assert not any(
        sorgu.startswith("UPDATE") for sorgu in sorgular
    )
 

def test_psikolog_baskasinin_randevusunu_iptal_edemez():
    # Sahte veritabanı bağlantısı
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Randevu psikolog 2'ye ait, giriş yapan psikolog 1
    mock_cursor.fetchone.side_effect = [
        (2, "PLANLANDI"),
        ("PSIKOLOG",),
        (1,),
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            randevu_iptal_et(
                randevu_id=5,
                kullanici_id=10,
            )

    assert hata.value.status_code == 403
    assert hata.value.detail == (
        "Yalnızca kendi randevunuzu iptal edebilirsiniz."
    )

    # Randevu değiştirilmemiş olmalı
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]
    assert not any(
        sorgu.startswith("UPDATE") for sorgu in sorgular
    )
   

def test_psikolog_baskasi_adina_randevu_olusturamaz():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Giriş yapan psikolog: personel_id = 1
    # Randevu oluşturulmak istenen psikolog: personel_id = 2
    mock_cursor.fetchone.side_effect = [
        ("PSIKOLOG",),
        (1,),
    ]

    randevu = RandevuOlusturModeli(
        danisan_kod_id="TEST-D-001",
        psikolog_id=2,
        oda_id=1,
        baslangic_zamani="2026-10-15T15:00:00",
        bitis_zamani="2026-10-15T16:00:00",
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(
                randevu=randevu,
                kullanici_id=10,
            )

    assert hata.value.status_code == 403
    assert hata.value.detail == (
        "Yalnızca kendi adınıza randevu oluşturabilirsiniz."
    )

    # Yetkisiz randevu veritabanına eklenmemeli
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]
    assert not any(
        sorgu.startswith("INSERT") for sorgu in sorgular
    )



def test_psikolog_kendi_randevusunu_guncelleyebilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # SQL sorgularının sırasına göre sahte cevaplar
    mock_cursor.fetchone.side_effect = [
        (
            "TEST-D-001",
            1,
            1,
            "2026-10-15T10:00:00",
            "2026-10-15T11:00:00",
            "PLANLANDI",
        ),
        ("PSIKOLOG",),  # Kullanıcının rolü
        (1,),           # Kullanıcının personel_id değeri
        (1,),           # Danışan kodu aktif
        (1,),           # Psikolog aktif
        (1,),           # Oda aktif
        None,           # Randevu çakışması yok
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = randevu_guncelle(
            randevu_id=2,
            guncelleme=RandevuGuncelleModeli(oda_id=1),
            kullanici_id=10,
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["randevu_id"] == 2

    # Güncelleme sorgusu çalıştırılmış olmalı
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]
    assert any(
        sorgu.startswith("UPDATE RANDEVULAR")
        for sorgu in sorgular
    )

    # İşlem veritabanına kaydedilmiş olmalı
    mock_conn.commit.assert_called_once()



def test_psikolog_tum_randevulari_goruntuleyebilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Giriş yapan kullanıcı psikolog rolünde
    mock_cursor.fetchone.return_value = ("PSIKOLOG",)

    # İki farklı psikoloğa ait sahte randevular
    mock_cursor.fetchall.return_value = [
        (
            2, "TEST-D-001", 1, 1,
            "2026-10-15T10:00:00",
            "2026-10-15T11:00:00",
            "PLANLANDI",
        ),
        (
            5, "TEST-D-002", 2, 1,
            "2026-10-15T15:00:00",
            "2026-10-15T16:00:00",
            "PLANLANDI",
        ),
    ]

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        sonuc = randevulari_listele(kullanici_id=10)

    assert len(sonuc) == 2
    assert sonuc[0]["psikolog_id"] == 1
    assert sonuc[1]["psikolog_id"] == 2

    # Listeleme sorgusu psikolog_id ile filtrelenmemeli
    sorgular = [
        call.args[0].upper()
        for call in mock_cursor.execute.call_args_list
    ]

    listeleme_sorgusu = next(
        sorgu for sorgu in sorgular
        if "FROM RANDEVULAR" in sorgu
    )

    assert "WHERE PSIKOLOG_ID" not in listeleme_sorgusu
    mock_conn.commit.assert_not_called()

