from unittest.mock import  MagicMock, patch

import pytest
from fastapi import HTTPException

from modeller import SifreDegistirModeli
from sunucu import sifre_degistir


def test_yeni_sifreler_eslesmezse_reddedilir():
    veri = SifreDegistirModeli(
        eski_parola="EskiSifre123!",
        yeni_parola="YeniSifre123!",
        yeni_parola_tekrar="FarkliSifre123!"
    )

    with patch("sunucu.psycopg2.connect") as mock_connect:
        with pytest.raises(HTTPException) as hata:
            sifre_degistir(
                veri=veri,
                kullanici_id=10
            )

    assert hata.value.status_code == 422
    assert hata.value.detail == "Yeni şifreler birbiriyle eşleşmiyor."

    # Hatalı şifreler için veritabanına bağlantı açılmamalı
    mock_connect.assert_not_called()

def test_eski_sifre_yanlissa_reddedilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı mevcut ve hesabı aktif
    mock_cursor.fetchone.return_value = ("kayitli_hash", True)

    veri = SifreDegistirModeli(
        eski_parola="YanlisSifre123!",
        yeni_parola="YeniSifre123!",
        yeni_parola_tekrar="YeniSifre123!"
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=mock_conn),
        patch("sunucu.parola_dogrula", return_value=False)
    ):
        with pytest.raises(HTTPException) as hata:
            sifre_degistir(
                veri=veri,
                kullanici_id=10
            )

    assert hata.value.status_code == 401
    assert hata.value.detail == "Eski şifre hatalı."

    # Yanlış eski şifreyle değişiklik kaydedilmemeli
    mock_conn.commit.assert_not_called()

def test_sifre_basarili_degistirilir():
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı mevcut ve aktif
    mock_cursor.fetchone.return_value = ("eski_hash", True)

    veri = SifreDegistirModeli(
        eski_parola="EskiSifre123!",
        yeni_parola="YeniSifre456!",
        yeni_parola_tekrar="YeniSifre456!"
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=mock_conn),
        patch("sunucu.parola_dogrula", return_value=True) as mock_dogrula,
        patch("sunucu.parola_hashle", return_value="yeni_hash") as mock_hash,
    ):
        sonuc = sifre_degistir(
            veri=veri,
            kullanici_id=10
        )

    assert sonuc["durum"] == "basarili"

    # Eski şifre doğrulanmalı
    mock_dogrula.assert_called_once_with(
        "EskiSifre123!", "eski_hash"
    )

    # Yeni şifre hash fonksiyonuna gönderilmeli
    mock_hash.assert_called_once_with("YeniSifre456!")

    # Veritabanındaki şifre güncellenmeli
    guncelleme_cagrilari = [
        call
        for call in mock_cursor.execute.call_args_list
        if "UPDATE kullanicilar" in call.args[0]
    ]

    assert len(guncelleme_cagrilari) == 1

    sorgu, parametreler = guncelleme_cagrilari[0].args

    assert "ilk_giris_mi = FALSE" in sorgu
    assert parametreler == ("yeni_hash", 10)

    # İşlem kaydedilmeli
    mock_conn.commit.assert_called_once()
    
def test_ilk_giriste_diger_api_erisimleri_engellenir():
    from fastapi.security import HTTPAuthorizationCredentials
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı aktif ancak ilk giriş şifresini değiştirmemiş
    mock_cursor.fetchone.return_value = (True, True)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test_token"
    )

    with (
        patch("sunucu.token_dogrula", return_value=10),
        patch("sunucu.psycopg2.connect", return_value=mock_conn),
    ):
        with pytest.raises(HTTPException) as hata:
            mevcut_kullanici_id(credentials=credentials)

    assert hata.value.status_code == 403
    assert hata.value.detail == (
        "İlk girişte şifrenizi değiştirmeniz gerekiyor."
    )

def test_sifre_degistirildikten_sonra_erisim_acilir():
    from fastapi.security import HTTPAuthorizationCredentials
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı aktif ve şifre değiştirme işlemini tamamlamış
    mock_cursor.fetchone.return_value = (True, False)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test_token"
    )

    with (
        patch("sunucu.token_dogrula", return_value=10),
        patch("sunucu.psycopg2.connect", return_value=mock_conn),
    ):
        sonuc = mevcut_kullanici_id(credentials=credentials)

    # Kullanıcı artık kimlik doğrulama kontrolünden geçebilmeli
    assert sonuc == 10