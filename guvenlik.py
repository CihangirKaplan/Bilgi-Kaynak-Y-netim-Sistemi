import bcrypt
import hashlib
import hmac
import os
import jwt
import secrets
import string
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET ortam değişkeni tanımlı değil.")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "45"))

def gecici_parola_uret() -> str:
    karakterler = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(
        secrets.choice(karakterler)
        for _ in range(16)
    )

def parola_hashle(parola: str) -> str:
    parola_bytes = parola.encode("utf-8")
    hash_bytes = bcrypt.hashpw(parola_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")

def parola_dogrula(parola: str, parola_hash: str) -> bool:
    return bcrypt.checkpw(
        parola.encode("utf-8"),
        parola_hash.encode("utf-8")
    )

def access_token_olustur(kullanici_id: int, parola_hash: str | None = None) -> str:
    simdi = datetime.now(timezone.utc)
    bitis_zamani = simdi + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(kullanici_id),
        "iat": simdi,
        "exp": bitis_zamani
    }

    if parola_hash is not None:
        payload["phv"] = parola_token_ozeti(parola_hash)

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )

    return token

def parola_token_ozeti(parola_hash: str) -> str:
    """Parola hash'ini JWT içinde açığa çıkarmadan sürüm imzası üret."""
    return hmac.new(
        JWT_SECRET.encode("utf-8"),
        parola_hash.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def token_parola_gecerli(token: str, parola_hash: str) -> bool:
    """JWT'nin mevcut parola hash'iyle eşleştiğini kontrol et."""
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        return False

    gelen_ozet = payload.get("phv")
    if not isinstance(gelen_ozet, str):
        return False

    return hmac.compare_digest(
        gelen_ozet,
        parola_token_ozeti(parola_hash)
    )


def token_dogrula(token: str) -> int:
    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM]
    )

    kullanici_id = payload.get("sub")

    if kullanici_id is None:
        raise jwt.InvalidTokenError(
            "Token içerisinde kullanıcı bilgisi bulunamadı."
        )

    try:
        return int(kullanici_id)
    except (TypeError, ValueError):
        raise jwt.InvalidTokenError(
            "Token içerisindeki kullanıcı bilgisi geçersiz."
        )
    