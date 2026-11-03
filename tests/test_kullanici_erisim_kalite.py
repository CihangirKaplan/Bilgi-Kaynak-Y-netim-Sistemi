from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException

from sunucu import mevcut_kullanici_id


def test_suresi_dolmus_token_erisim_401():
    credentials = SimpleNamespace(credentials="expired-token")

    with patch(
        "sunucu.token_dogrula",
        side_effect=jwt.ExpiredSignatureError()
    ), patch("sunucu.psycopg2.connect") as mock_connect:

        with pytest.raises(HTTPException) as hata:
            mevcut_kullanici_id(credentials)

    assert hata.value.status_code == 401
    assert hata.value.detail == "Token süresi dolmuş."
    mock_connect.assert_not_called()


def test_veritabaninda_olmayan_kullanici_401():
    credentials = SimpleNamespace(credentials="valid-token")

    mock_conn = MagicMock()
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.fetchone.return_value = None

    with patch("sunucu.token_dogrula", return_value=42):
        with patch("sunucu.psycopg2.connect", return_value=mock_conn):

            with pytest.raises(HTTPException) as hata:
                mevcut_kullanici_id(credentials)

    assert hata.value.status_code == 401
    assert hata.value.detail == "Kullanıcı bulunamadı."

    sorgu, parametreler = mock_cursor.execute.call_args.args
    assert "WHERE kullanici_id = %s" in sorgu
    assert parametreler == (42,)

    mock_cursor.close.assert_called_once()
    mock_conn.close.assert_called_once()
