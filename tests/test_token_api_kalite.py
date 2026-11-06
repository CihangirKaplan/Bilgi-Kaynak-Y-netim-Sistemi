from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from sunucu import token_kullanici_id


def test_gecerli_token_kullanici_id_doner():
    from unittest.mock import MagicMock
    from guvenlik import access_token_olustur

    parola_hash = "TEST_PAROLA_HASH"

    # Gerçek JWT oluştur.
    token = access_token_olustur(42, parola_hash)
    credentials = SimpleNamespace(credentials=token)

    # Veritabanı bağlantısını taklit et.
    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value

    # Kullanıcı mevcut ve aktif.
    mock_cursor.fetchone.return_value = (
        parola_hash,
        True,
    )

    with patch(
        "sunucu.psycopg2.connect",
        return_value=mock_conn,
    ):
        sonuc = token_kullanici_id(credentials)

    assert sonuc == 42

    # Kullanıcı veritabanından doğrulanmış olmalı.
    mock_cursor.execute.assert_called_once()

    sorgu, parametreler = mock_cursor.execute.call_args.args

    assert "SELECT parola_hash, aktif_mi" in sorgu
    assert parametreler == (42,)

    mock_conn.close.assert_called_once()



def test_suresi_dolmus_token_401_doner():
    credentials = SimpleNamespace(credentials="expired-token")

    with patch(
        "sunucu.token_dogrula",
        side_effect=jwt.ExpiredSignatureError()
    ):
        with pytest.raises(HTTPException) as hata:
            token_kullanici_id(credentials)

    assert hata.value.status_code == 401
    assert hata.value.detail == "Token süresi dolmuş."


def test_gecersiz_token_401_doner():
    credentials = SimpleNamespace(credentials="invalid-token")

    with patch(
        "sunucu.token_dogrula",
        side_effect=jwt.InvalidTokenError()
    ):
        with pytest.raises(HTTPException) as hata:
            token_kullanici_id(credentials)

    assert hata.value.status_code == 401
    assert hata.value.detail == "Geçersiz token."
