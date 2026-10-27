from types import SimpleNamespace
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException

from sunucu import token_kullanici_id


def test_gecerli_token_kullanici_id_doner():
    credentials = SimpleNamespace(credentials="test-token")

    with patch("sunucu.token_dogrula", return_value=42):
        sonuc = token_kullanici_id(credentials)

    assert sonuc == 42


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
