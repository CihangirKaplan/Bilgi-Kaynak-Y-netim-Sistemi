import bcrypt
import os
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET ortam değişkeni tanımlı değil.")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

def parola_hashle(parola: str) -> str:
    parola_bytes = parola.encode("utf-8")
    hash_bytes = bcrypt.hashpw(parola_bytes, bcrypt.gensalt())
    return hash_bytes.decode("utf-8")

def parola_dogrula(parola: str, parola_hash: str) -> bool:
    return bcrypt.checkpw(
        parola.encode("utf-8"),
        parola_hash.encode("utf-8")
    )

def access_token_olustur(kullanici_id: int) -> str:
    simdi = datetime.now(timezone.utc)
    bitis_zamani = simdi + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(kullanici_id),
        "iat": simdi,
        "exp": bitis_zamani
    }

    token = jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )

    return token

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
    