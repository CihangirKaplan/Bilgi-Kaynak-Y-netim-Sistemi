from datetime import datetime, timedelta, timezone

import jwt
import pytest

from guvenlik import (
    JWT_SECRET,
    JWT_ALGORITHM,
    access_token_olustur,
    token_dogrula,
)


def test_gecerli_token_kullanici_id_doner():
    token = access_token_olustur(42)

    assert token_dogrula(token) == 42


def test_suresi_dolmus_token_reddedilir():
    simdi = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": "42",
            "iat": simdi - timedelta(hours=2),
            "exp": simdi - timedelta(minutes=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        token_dogrula(token)


def test_yanlis_imzali_token_reddedilir():
    token = jwt.encode(
        {
            "sub": "42",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        "qa-001-farkli-imza-test-anahtari-2026-uzun",
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidSignatureError):
        token_dogrula(token)


def test_kullanici_id_olmayan_token_reddedilir():
    token = jwt.encode(
        {"test": "QA-001"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        token_dogrula(token)


def test_gecersiz_kullanici_id_reddedilir():
    token = jwt.encode(
        {"sub": "gecersiz-id"},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        token_dogrula(token)
