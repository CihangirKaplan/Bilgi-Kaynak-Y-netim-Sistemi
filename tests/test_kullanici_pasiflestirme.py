from unittest.mock import MagicMock, patch

def test_yetkisiz_kullanici_pasiflestiremez():
    import pytest
    from fastapi import HTTPException
    from sunucu import izin_kontrol

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcının KULLANICI_PASIFLESTIR izni yok
    mock_cursor.fetchone.return_value = (0,)

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with pytest.raises(HTTPException) as hata:
            izin_kontrol("KULLANICI_PASIFLESTIR")(
                kullanici_id=10
            )

    assert hata.value.status_code == 403

    mock_conn.close.assert_called_once()


def test_pasif_kullanici_mevcut_token_ile_erisim_saglayamaz():
    import pytest
    from fastapi import HTTPException
    from sunucu import mevcut_kullanici_id

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı pasif durumda
    mock_cursor.fetchone.return_value = (False, False)

    # Token doğrulaması başarılı olsa bile erişim engellenmeli
    mock_credentials = MagicMock()
    mock_credentials.credentials = "gecerli-test-token"

    with patch("sunucu.token_dogrula", return_value=5):
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):
            with pytest.raises(HTTPException) as hata:
                mevcut_kullanici_id(credentials=mock_credentials)

    assert hata.value.status_code == 403
    assert hata.value.detail == "Kullanıcı hesabı aktif değil."

    mock_conn.close.assert_called_once()


def test_pasif_kullanici_giris_yapamaz():
    import pytest
    from fastapi import HTTPException
    from modeller import GirisModeli
    from sunucu import giris_yap

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Veritabanından dönen kullanıcı bilgileri
    mock_cursor.fetchone.return_value = (
        5,              # kullanici_id
        "test_psikolog", # kullanici_adi
        "hash",         # parola_hash
        2,              # rol_id
        False,          # aktif_mi
        0,              # basarisiz_giris_sayisi
        None,           # kilit_bitis_zamani
        False           # ilk_giris_mi
    )

    with patch("sunucu.psycopg2.connect", return_value=mock_conn):
        with patch("sunucu.denetim_kaydi_olustur") as mock_audit:
            with patch("sunucu.access_token_olustur") as mock_token:
                with pytest.raises(HTTPException) as hata:
                    giris_yap(
                        GirisModeli(
                            kullanici_adi="test_psikolog",
                            parola="test_parola"
                        )
                    )

    assert hata.value.status_code == 403
    assert hata.value.detail == "Kullanıcı hesabı aktif değil."

    # Pasif kullanıcıya token verilmemeli
    mock_token.assert_not_called()

    # Başarısız giriş denetim kaydına alınmalı
    assert mock_audit.call_args.kwargs["olay_turu"] == "LOGIN_FAILED"
