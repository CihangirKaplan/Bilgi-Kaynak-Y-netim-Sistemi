from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import KullaniciOlusturModeli
from sunucu import kullanici_olustur


def test_mudur_admin_kullanicisi_olusturamaz():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # 1. İşlemi yapan kullanıcının rolü: MUDUR
    # 2. Rol atama yetkisi: VAR
    # 3. Oluşturulmak istenen rol: ADMIN
    mock_cursor.fetchone.side_effect = [
        ("MUDUR",),
        (1,),
        ("ADMIN",),
    ]

    yeni_kullanici = KullaniciOlusturModeli(
        kullanici_adi="test_admin",
        rol_id=6,
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            kullanici_olustur(
                yeni_kullanici=yeni_kullanici,
                kullanici_id=10,
            )

    assert hata.value.status_code == 403
    assert hata.value.detail == (
        "ADMIN rolünü atama yetkiniz bulunmuyor."
    )

    # Reddedilen işlem veritabanına kullanıcı eklememeli
    sorgular = [
        call.args[0].strip().upper()
        for call in mock_cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("INSERT INTO KULLANICILAR")
        for sorgu in sorgular
    )
def test_admin_gecici_sifreyle_kullanici_olusturur():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    mock_cursor.fetchone.side_effect = [
        ("ADMIN",),       # İşlemi yapan kullanıcının rolü
        (1,),             # Rol atama yetkisi var
        ("PSIKOLOG",),    # Yeni kullanıcının rolü
        (25,),            # Oluşturulan kullanıcının ID'si
    ]

    yeni_kullanici = KullaniciOlusturModeli(
        kullanici_adi="test_psikolog",
        rol_id=1,
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=mock_conn),
        patch("sunucu.gecici_parola_uret", return_value="TestGecici123!"),
        patch("sunucu.parola_hashle", return_value="ornek_hash") as mock_hash,
    ):
        sonuc = kullanici_olustur(
            yeni_kullanici=yeni_kullanici,
            kullanici_id=10,
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["kullanici_id"] == 25
    assert sonuc["gecici_parola"] == "TestGecici123!"
    assert sonuc["ilk_giris_mi"] is True

    # Geçici şifre hash fonksiyonuna gönderilmeli
    mock_hash.assert_called_once_with("TestGecici123!")

    # Veritabanına açık şifre değil, hash kaydedilmeli
    insert_cagrilari = [
        call
        for call in mock_cursor.execute.call_args_list
        if "INSERT INTO kullanicilar" in call.args[0]
    ]

    assert len(insert_cagrilari) == 1

    sorgu, parametreler = insert_cagrilari[0].args

    assert "ilk_giris_mi" in sorgu
    assert "TRUE, TRUE" in sorgu
    assert parametreler == ("test_psikolog", "ornek_hash", 1)

    mock_conn.commit.assert_called_once()