"""CAPTCHA hiz sinirinin PostgreSQL kalite testleri."""

import os

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import psycopg2
import pytest

from fastapi import HTTPException

from captcha_hiz_siniri import (
    SINIRLER,
    _anahtar_uret,
    hiz_siniri_kontrol,
)
from sunucu import VT_AYARLARI


pytestmark = pytest.mark.skipif(
    os.getenv("TKYS_PG_TEST_ONAY") != "EVET",
    reason="PostgreSQL kalite testi için açık onay gerekiyor.",
)


@pytest.fixture
def istemci():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == "crkys_alembic_test"

    ip = "test-" + uuid4().hex

    yield ip

    anahtarlar = [
        _anahtar_uret(ip, "captcha"),
        _anahtar_uret(ip, "login"),
    ]

    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM giris_istek_limitleri
                WHERE anahtar = ANY(%s)
                """,
                (anahtarlar,),
            )


def test_hiz_siniri_429_ve_bekleme_suresi(istemci):
    with patch.dict(SINIRLER, {"captcha": 1}):
        assert hiz_siniri_kontrol(
            VT_AYARLARI, istemci, "captcha"
        )

        with pytest.raises(HTTPException) as hata:
            hiz_siniri_kontrol(
                VT_AYARLARI, istemci, "captcha"
            )

    assert hata.value.status_code == 429
    assert int(hata.value.headers["Retry-After"]) > 0
    assert hata.value.headers["X-TKYS-RateLimit"] == "1"


def test_es_zamanli_isteklerde_limit_asilamaz(istemci):
    baslangic = Barrier(4)

    def istek(_):
        baslangic.wait(timeout=10)

        try:
            hiz_siniri_kontrol(
                VT_AYARLARI,
                istemci,
                "captcha",
            )
            return 200

        except HTTPException as hata:
            assert hata.status_code == 429
            return hata.status_code

    with patch.dict(SINIRLER, {"captcha": 2}):
        with ThreadPoolExecutor(max_workers=4) as havuz:
            sonuclar = list(
                havuz.map(istek, range(4))
            )

    assert sonuclar.count(200) == 2
    assert sonuclar.count(429) == 2


def test_captcha_limiti_login_limitini_etkilemez(istemci):
    with patch.dict(SINIRLER, {"captcha": 1}):
        assert hiz_siniri_kontrol(
            VT_AYARLARI, istemci, "captcha"
        )

        with pytest.raises(HTTPException):
            hiz_siniri_kontrol(
                VT_AYARLARI, istemci, "captcha"
            )

    assert hiz_siniri_kontrol(
        VT_AYARLARI, istemci, "login"
    )
