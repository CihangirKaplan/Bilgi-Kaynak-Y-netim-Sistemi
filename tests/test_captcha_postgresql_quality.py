"""TKYS CAPTCHA PostgreSQL kalite ve eszamanlilik testleri."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException

from captcha_servisi import (
    _kod_ozeti,
    captcha_dogrula,
    captcha_olustur,
)
from sunucu import VT_AYARLARI


pytestmark = pytest.mark.skipif(
    os.getenv("TKYS_PG_TEST_ONAY") != "EVET",
    reason="Gercek PostgreSQL testleri icin acik onay gerekli.",
)


@pytest.fixture(autouse=True)
def sadece_test_veritabani():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == "crkys_alembic_test"


@pytest.fixture
def kod_kaydi():
    kayitlar = []

    def ekle(kod="73942", sure=120):
        captcha_id = uuid4().hex
        kayitlar.append(captcha_id)

        bitis = datetime.now(timezone.utc) + timedelta(
            seconds=sure
        )

        with psycopg2.connect(**VT_AYARLARI) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO giris_captcha_kodlari
                        (captcha_id, kod_ozeti, gecerlilik_sonu)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        captcha_id,
                        _kod_ozeti(captcha_id, kod),
                        bitis,
                    ),
                )

        return captcha_id

    yield ekle

    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM giris_captcha_kodlari
                WHERE captcha_id = ANY(%s)
                """,
                (kayitlar,),
            )


def test_dogru_kod_kabul_edilir(kod_kaydi):
    captcha_id = kod_kaydi()

    assert captcha_dogrula(
        VT_AYARLARI,
        captcha_id,
        "73942",
    )


def test_kullanilmis_kod_reddedilir(kod_kaydi):
    captcha_id = kod_kaydi()

    assert captcha_dogrula(
        VT_AYARLARI, captcha_id, "73942"
    )

    with pytest.raises(HTTPException) as hata:
        captcha_dogrula(
            VT_AYARLARI, captcha_id, "73942"
        )

    assert hata.value.status_code == 400


def test_yanlis_kod_tuketilir(kod_kaydi):
    captcha_id = kod_kaydi()

    with pytest.raises(HTTPException):
        captcha_dogrula(
            VT_AYARLARI, captcha_id, "11111"
        )

    with pytest.raises(HTTPException) as hata:
        captcha_dogrula(
            VT_AYARLARI, captcha_id, "73942"
        )

    assert hata.value.status_code == 400


def test_eksik_uzunlukta_kod_tuketilir(kod_kaydi):
    captcha_id = kod_kaydi()

    with pytest.raises(HTTPException):
        captcha_dogrula(
            VT_AYARLARI, captcha_id, "12"
        )

    with pytest.raises(HTTPException) as hata:
        captcha_dogrula(
            VT_AYARLARI, captcha_id, "73942"
        )

    assert hata.value.status_code == 400


def test_suresi_dolmus_kod_reddedilir(kod_kaydi):
    captcha_id = kod_kaydi(sure=-10)

    with pytest.raises(HTTPException) as hata:
        captcha_dogrula(
            VT_AYARLARI, captcha_id, "73942"
        )

    assert hata.value.status_code == 400


def test_olmayan_captcha_reddedilir():
    with pytest.raises(HTTPException) as hata:
        captcha_dogrula(
            VT_AYARLARI,
            uuid4().hex,
            "73942",
        )

    assert hata.value.status_code == 400


def test_es_zamanli_kullanimda_tek_basarili(kod_kaydi):
    captcha_id = kod_kaydi()
    baslangic = Barrier(2)

    def dogrulama(_):
        baslangic.wait(timeout=10)

        try:
            captcha_dogrula(
                VT_AYARLARI,
                captcha_id,
                "73942",
            )
            return True

        except HTTPException as hata:
            assert hata.status_code == 400
            return False

    with ThreadPoolExecutor(max_workers=2) as havuz:
        sonuclar = list(
            havuz.map(dogrulama, range(2))
        )

    assert sonuclar.count(True) == 1
    assert sonuclar.count(False) == 1


def test_captcha_olusturma_veritabanina_kaydeder():
    captcha_id = None

    try:
        sonuc = captcha_olustur(VT_AYARLARI)
        captcha_id = sonuc["captcha_id"]

        assert len(captcha_id) == 32
        assert sonuc["gecerlilik_saniye"] == 120
        assert sonuc["gorsel_base64"]

        with psycopg2.connect(**VT_AYARLARI) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT kod_ozeti, gecerlilik_sonu
                    FROM giris_captcha_kodlari
                    WHERE captcha_id = %s
                    """,
                    (captcha_id,),
                )

                kayit = cursor.fetchone()

        assert kayit is not None
        assert len(kayit[0]) == 64
        assert kayit[1] > datetime.now(timezone.utc)

    finally:
        if captcha_id:
            with psycopg2.connect(**VT_AYARLARI) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM giris_captcha_kodlari
                        WHERE captcha_id = %s
                        """,
                        (captcha_id,),
                    )
