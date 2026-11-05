"""TKYS giris ve CAPTCHA istek hizi sinirlama servisi."""

import hashlib
import hmac
import secrets

from contextlib import closing

import psycopg2

from fastapi import HTTPException
from guvenlik import JWT_SECRET


PENCERE_SANIYE = 300

SINIRLER = {
    "captcha": 120,
    "login": 60,
}


def _anahtar_uret(istemci_ip, islem):
    """IP adresini duz metin saklamak yerine HMAC ile ozetle."""
    anahtar = JWT_SECRET

    if isinstance(anahtar, str):
        anahtar = anahtar.encode("utf-8")

    mesaj = (
        f"tkys-rate-limit-v1:{islem}:{istemci_ip}"
    ).encode("utf-8")

    return hmac.new(
        anahtar,
        mesaj,
        hashlib.sha256,
    ).hexdigest()


def hiz_siniri_kontrol(vt_ayarlari, istemci_ip, islem):
    """PostgreSQL uzerinden atomik istek hizi kontrolu."""
    if islem not in SINIRLER:
        raise ValueError("Bilinmeyen istek turu.")

    if not istemci_ip:
        istemci_ip = "unknown"

    limit = SINIRLER[islem]
    anahtar = _anahtar_uret(istemci_ip, islem)

    with closing(psycopg2.connect(**vt_ayarlari)) as conn:
        try:
            with conn.cursor() as cursor:

                # Eski kayitlari ara sira temizle.
                if secrets.randbelow(64) == 0:
                    cursor.execute(
                        """
                        DELETE FROM giris_istek_limitleri
                        WHERE pencere_baslangici
                            < CURRENT_TIMESTAMP - INTERVAL '1 day'
                        """
                    )

                # ON CONFLICT: eszamanli isteklerde
                # sayaci atomik olarak gunceller.
                cursor.execute(
                    """
                    INSERT INTO giris_istek_limitleri (
                        anahtar,
                        pencere_baslangici,
                        istek_sayisi
                    )
                    VALUES (
                        %s,
                        to_timestamp(
                            (
                                floor(
                                    EXTRACT(
                                        EPOCH FROM CURRENT_TIMESTAMP
                                    ) / 300
                                ) * 300
                            )::double precision
                        ),
                        1
                    )
                    ON CONFLICT (anahtar)
                    DO UPDATE SET
                        istek_sayisi = CASE
                            WHEN
                                giris_istek_limitleri.pencere_baslangici
                                = EXCLUDED.pencere_baslangici
                            THEN LEAST(
                                giris_istek_limitleri.istek_sayisi + 1,
                                %s
                            )
                            ELSE 1
                        END,
                        pencere_baslangici =
                            EXCLUDED.pencere_baslangici
                    RETURNING
                        istek_sayisi,
                        GREATEST(
                            1,
                            CEIL(
                                EXTRACT(
                                    EPOCH FROM (
                                        pencere_baslangici
                                        + INTERVAL '5 minutes'
                                        - CURRENT_TIMESTAMP
                                    )
                                )
                            )
                        )::integer;
                    """,
                    (anahtar, limit + 1),
                )

                sayi, bekleme = cursor.fetchone()

            # Limit asildiginda bile sayac kaydedilir.
            conn.commit()

        except Exception:
            conn.rollback()
            raise

    if sayi > limit:
        raise HTTPException(
            status_code=429,
            detail=(
                "Çok fazla istek gönderildi. "
                "Lütfen biraz sonra tekrar deneyin."
            ),
            headers={
                "Retry-After": str(bekleme),
                "X-TKYS-RateLimit": "1",
            },
        )

    return True
