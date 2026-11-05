"""TKYS giris CAPTCHA servisi."""

import base64
import hashlib
import hmac
import re
import secrets

from contextlib import closing
from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4

import psycopg2

from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from guvenlik import JWT_SECRET


CAPTCHA_SURE_SANIYE = 120
CAPTCHA_UZUNLUK = 5

HATA_MESAJI = (
    "Güvenlik kodu hatalı veya süresi dolmuş. "
    "Lütfen yeni kod alın."
)


def _kod_ozeti(captcha_id, kod):
    """Dogrulama kodunu sunucu anahtariyla HMAC kullanarak ozetle."""
    anahtar = JWT_SECRET
    if isinstance(anahtar, str):
        anahtar = anahtar.encode("utf-8")

    mesaj = f"tkys-captcha-v1:{captcha_id}:{kod}".encode("utf-8")

    return hmac.new(
        anahtar,
        mesaj,
        hashlib.sha256,
    ).hexdigest()


def _gorsel_uret(kod):
    """Sayilari PNG gorseline ciz; cevap metnini istemciye gonderme."""
    resim = Image.new("RGB", (200, 60), "#EDF4FF")
    cizim = ImageDraw.Draw(resim)
    yazi_tipi = ImageFont.load_default(size=30)

    # Hafif arka plan paraziti.
    for _ in range(80):
        x = secrets.randbelow(200)
        y = secrets.randbelow(60)
        cizim.point((x, y), fill="#A9C2E3")

    for _ in range(3):
        cizim.line(
            (
                secrets.randbelow(200),
                secrets.randbelow(60),
                secrets.randbelow(200),
                secrets.randbelow(60),
            ),
            fill="#A6BFDF",
            width=1,
        )

    for sira, rakam in enumerate(kod):
        x = 12 + sira * 36 + secrets.randbelow(4)
        y = 6 + secrets.randbelow(6)

        cizim.text(
            (x, y),
            rakam,
            font=yazi_tipi,
            fill="#173D75",
        )

    cikti = BytesIO()
    resim.save(cikti, format="PNG")

    return base64.b64encode(cikti.getvalue()).decode("ascii")


def captcha_olustur(vt_ayarlari):
    """Rastgele bir guvenlik kodu olustur ve suresini kaydet."""
    captcha_id = uuid4().hex

    kod = "".join(
        str(secrets.randbelow(10))
        for _ in range(CAPTCHA_UZUNLUK)
    )

    ozet = _kod_ozeti(captcha_id, kod)
    gorsel = _gorsel_uret(kod)

    son = datetime.now(timezone.utc) + timedelta(
        seconds=CAPTCHA_SURE_SANIYE
    )

    with closing(psycopg2.connect(**vt_ayarlari)) as conn:
        try:
            with conn.cursor() as cursor:
                # Suresi dolmus eski kodlari temizle.
                cursor.execute(
                    """
                    DELETE FROM giris_captcha_kodlari
                    WHERE gecerlilik_sonu <= CURRENT_TIMESTAMP;
                    """
                )

                cursor.execute(
                    """
                    INSERT INTO giris_captcha_kodlari
                        (captcha_id, kod_ozeti, gecerlilik_sonu)
                    VALUES (%s, %s, %s);
                    """,
                    (captcha_id, ozet, son),
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "captcha_id": captcha_id,
        "gorsel_base64": gorsel,
        "gecerlilik_saniye": CAPTCHA_SURE_SANIYE,
    }


def captcha_dogrula(vt_ayarlari, captcha_id, girilen_kod):
    """Kodu tek kullanimlik olarak dogrula; yanlista da tuket."""
    if not (
        isinstance(captcha_id, str)
        and re.fullmatch(r"[0-9a-f]{32}", captcha_id)
    ):
        raise HTTPException(
            status_code=400,
            detail=HATA_MESAJI,
        )

    with closing(psycopg2.connect(**vt_ayarlari)) as conn:
        try:
            with conn.cursor() as cursor:
                # DELETE RETURNING tek kullanimliligi atomik saglar.
                cursor.execute(
                    """
                    DELETE FROM giris_captcha_kodlari
                    WHERE captcha_id = %s
                    RETURNING kod_ozeti, gecerlilik_sonu;
                    """,
                    (captcha_id,),
                )
                kayit = cursor.fetchone()

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    if kayit is None:
        raise HTTPException(
            status_code=400,
            detail=HATA_MESAJI,
        )

    beklenen_ozet, gecerlilik_sonu = kayit

    if not (
        isinstance(girilen_kod, str)
        and re.fullmatch(r"[0-9]{5}", girilen_kod)
    ):
        raise HTTPException(
            status_code=400,
            detail=HATA_MESAJI,
        )

    dogru_ozet = _kod_ozeti(captcha_id, girilen_kod)

    if (
        datetime.now(timezone.utc) >= gecerlilik_sonu
        or not hmac.compare_digest(beklenen_ozet, dogru_ozet)
    ):
        raise HTTPException(
            status_code=400,
            detail=HATA_MESAJI,
        )

    return True
