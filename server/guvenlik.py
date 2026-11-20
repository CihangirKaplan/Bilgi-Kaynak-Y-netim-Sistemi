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

# Kısa anahtar tahmin edilerek sahte oturum anahtarı (token) üretilmesine yol açar; belgelerdeki asgari uzunluk uygulanır.
JWT_SECRET_ASGARI_UZUNLUK = 32
if len(JWT_SECRET) < JWT_SECRET_ASGARI_UZUNLUK:
    raise RuntimeError(
        f"JWT_SECRET en az {JWT_SECRET_ASGARI_UZUNLUK} karakter olmalıdır (şu an {len(JWT_SECRET)}). "
        "Yenisini üretmek için: python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
        "ve çıkan değeri .env dosyasındaki JWT_SECRET satırına yazın."
    )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "45"))

# Yönetici ya da kurtarma aracıyla verilen GEÇİCİ parolanın geçerlilik süresi (saat). Süre dolunca kullanıcı giriş yapamaz ve
# yeniden geçici parola ister. Süre bilgisi boş eski kayıtlar süresiz kalır. (SQL'e tam sayı olarak gömülür: kullanıcı girdisi değildir.)
GECICI_PAROLA_GECERLILIK_SAAT = max(1, int(os.getenv("GECICI_PAROLA_GECERLILIK_SAAT", "48")))
GECICI_PAROLA_BITIS_SQL = f"CURRENT_TIMESTAMP + INTERVAL '{GECICI_PAROLA_GECERLILIK_SAAT} hours'"

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
    parola_bytes = parola.encode("utf-8")
    if len(parola_bytes) > 72:
        # bcrypt 72 bayttan uzun girdide ValueError fırlatır (sunucu hatasına yol açardı); parola bu uzunlukta
        # belirlenemediği için hiçbir hesapla eşleşemez: sıradan "yanlış parola" sayılır.
        return False
    return bcrypt.checkpw(
        parola_bytes,
        parola_hash.encode("utf-8")
    )

def access_token_olustur(kullanici_id: int, parola_hash: str | None = None, token_surumu: int | None = None) -> str:
    simdi = datetime.now(timezone.utc)
    bitis_zamani = simdi + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "sub": str(kullanici_id),
        "iat": simdi,
        "exp": bitis_zamani
    }

    if parola_hash is not None:
        payload["phv"] = parola_token_ozeti(parola_hash)

    if token_surumu is not None:
        payload["tsv"] = int(token_surumu)           # çıkışta kullanıcının sürümü artar; eski jetonlar geçersiz olur

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


def token_surumu_gecerli(token: str, mevcut_surum) -> bool:
    """Jetonun taşıdığı oturum sürümü kullanıcının güncel sürümüyle aynı mı? (Sürüm taşımayan eski jetonlar 0 sayılır.)"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        return False
    return int(payload.get("tsv", 0)) == int(mevcut_surum or 0)


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
    