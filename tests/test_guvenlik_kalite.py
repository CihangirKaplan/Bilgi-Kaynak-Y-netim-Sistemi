import string
import jwt

from guvenlik import (
    gecici_parola_uret,
    parola_hashle,
    parola_dogrula,
    access_token_olustur,
    JWT_SECRET,
    JWT_ALGORITHM,
)


def test_gecici_parola_uzunlugu_ve_karakterleri():
    parola = gecici_parola_uret()

    izin_verilen = string.ascii_letters + string.digits + "!@#$%&*"

    assert len(parola) == 16
    assert all(karakter in izin_verilen for karakter in parola)


def test_parola_hashleme_ve_dogrulama():
    parola = "TKYS-Guvenli-Test-123!"
    hash_degeri = parola_hashle(parola)

    assert hash_degeri != parola
    assert parola_dogrula(parola, hash_degeri) is True
    assert parola_dogrula("YanlisParola123!", hash_degeri) is False


def test_jwt_olusturma_ve_payload():
    token = access_token_olustur(kullanici_id=42)

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["sub"] == "42"
    assert payload["exp"] > payload["iat"]
