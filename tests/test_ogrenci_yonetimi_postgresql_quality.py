
"""TKYS Öğrenci Yönetimi - PostgreSQL salt okunur entegrasyon testleri."""

from datetime import date

import psycopg2
import pytest

from sunucu import (
    VT_AYARLARI,
    ogrenciler_yonetim_listesi,
    ogrenci_puan_detayi,
)


@pytest.fixture
def pg_conn():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

        yield conn

    finally:
        conn.rollback()
        conn.close()


def test_ogrenci_listesi_pg_ile_uyumlu(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT ogrenci_id, ogrenci_numarasi, tur::text
            FROM ogrenciler
            ORDER BY ogrenci_id
        """)
        beklenen = cur.fetchall()

    sonuc = ogrenciler_yonetim_listesi(yetkili_id=1)

    gercek = sorted(
        (
            o["ogrenci_id"],
            o["ogrenci_numarasi"],
            o["tur"],
        )
        for o in sonuc
    )

    assert gercek == beklenen


def test_ogrenci_puanlari_pg_ile_uyumlu(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            ORDER BY ogrenci_id
            LIMIT 1
        """)
        kayit = cur.fetchone()

        if kayit is None:
            pytest.skip("Test veritabanında öğrenci bulunmuyor.")

        ogrenci_id = kayit[0]

        cur.execute("""
            SELECT COALESCE(SUM(t.adet * t.kayit_puani), 0)
            FROM ogrenci_faaliyet_takip t
            JOIN faaliyetler f
                ON f.faaliyet_id = t.faaliyet_id
            WHERE t.ogrenci_id = %s
              AND t.faaliyet_tarihi BETWEEN %s AND %s
        """, (
            ogrenci_id,
            date(2000, 1, 1),
            date(2100, 1, 1),
        ))

        beklenen_puan = float(cur.fetchone()[0])

    sonuc = ogrenci_puan_detayi(
        ogrenci_id=ogrenci_id,
        baslangic=date(2000, 1, 1),
        bitis=date(2100, 1, 1),
        yetkili_id=1,
    )

    assert sonuc["toplam_puan"] == beklenen_puan


def test_erteleme_gecmisi_tablosu_mevcut(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("""
            SELECT to_regclass(
                'public.ogrenci_kayit_erteleme_gecmisi'
            )
        """)

        assert cur.fetchone()[0] is not None


# ------------------------------------------------------------
# Öğrenci Yönetimi - transaction entegrasyon testleri
# ------------------------------------------------------------

from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException

import sunucu


@pytest.fixture
def gecici_gonullu():
    """Yalnızca test veritabanında geçici öğrenci oluşturur."""

    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    numara = "QA" + uuid4().hex[:12]
    conn = psycopg2.connect(**VT_AYARLARI)
    ogrenci_id = None

    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO ogrenciler
                    (ad_soyad, ogrenci_numarasi, tur,
                     olusturulma_tarihi)
                VALUES (%s, %s, 'GONULLU', %s)
                RETURNING ogrenci_id
            """, (
                "QA Geçici Öğrenci",
                numara,
                datetime(2015, 1, 1),
            ))

            ogrenci_id = cur.fetchone()[0]

        conn.commit()

        yield ogrenci_id

    finally:
        conn.rollback()

        try:
            if ogrenci_id is not None:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT erteleme_id
                        FROM ogrenci_kayit_erteleme_gecmisi
                        WHERE ogrenci_id = %s
                    """, (ogrenci_id,))

                    erteleme_ids = [
                        row[0] for row in cur.fetchall()
                    ]

                    if erteleme_ids:
                        cur.execute("""
                            DELETE FROM denetim_kayitlari
                            WHERE hedef_tablo =
                                'ogrenci_kayit_erteleme_gecmisi'
                              AND hedef_kayit_id = ANY(%s)
                        """, (erteleme_ids,))

                    cur.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = 'ogrenciler'
                          AND hedef_kayit_id = %s
                    """, (ogrenci_id,))

                    cur.execute("""
                        DELETE FROM ogrenci_kayit_erteleme_gecmisi
                        WHERE ogrenci_id = %s
                    """, (ogrenci_id,))

                    cur.execute("""
                        DELETE FROM ogrenciler
                        WHERE ogrenci_id = %s
                    """, (ogrenci_id,))

                conn.commit()

        finally:
            conn.close()


def test_erteleme_ve_audit_birlikte_kaydedilir(gecici_gonullu):
    ogrenci_id = gecici_gonullu
    yeni_tarih = date.today() + timedelta(days=30)

    sonuc = sunucu.ogrenci_silme_ertele(
        ogrenci_id=ogrenci_id,
        veri=sunucu.OgrenciErteleModeli(
            yeni_uyari_tarihi=yeni_tarih
        ),
        yetkili_id=None,
    )

    assert sonuc["ogrenci_id"] == ogrenci_id

    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT erteleme_id, yeni_uyari_tarihi
                FROM ogrenci_kayit_erteleme_gecmisi
                WHERE ogrenci_id = %s
                ORDER BY erteleme_id DESC
                LIMIT 1
            """, (ogrenci_id,))

            erteleme_id, kayitli_tarih = cur.fetchone()

            assert kayitli_tarih == yeni_tarih

            cur.execute("""
                SELECT COUNT(*)
                FROM denetim_kayitlari
                WHERE hedef_tablo =
                    'ogrenci_kayit_erteleme_gecmisi'
                  AND hedef_kayit_id = %s
                  AND olay_turu = 'CREATE'
            """, (erteleme_id,))

            assert cur.fetchone()[0] == 1

    finally:
        conn.rollback()
        conn.close()


def test_erteleme_audit_hatasinda_rollback(gecici_gonullu):
    ogrenci_id = gecici_gonullu

    gercek_audit = sunucu.denetim_kaydi_olustur

    def audit_ve_hata(*args, **kwargs):
        assert kwargs.get("mevcut_cursor") is not None
        gercek_audit(*args, **kwargs)
        raise RuntimeError("QA_ERTELEME_ROLLBACK")

    with patch.object(
        sunucu,
        "denetim_kaydi_olustur",
        side_effect=audit_ve_hata,
    ):
        with pytest.raises(HTTPException) as hata:
            sunucu.ogrenci_silme_ertele(
                ogrenci_id=ogrenci_id,
                veri=sunucu.OgrenciErteleModeli(
                    yeni_uyari_tarihi=(
                        date.today() + timedelta(days=30)
                    )
                ),
                yetkili_id=None,
            )

    assert hata.value.status_code == 500

    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM ogrenci_kayit_erteleme_gecmisi
                WHERE ogrenci_id = %s
            """, (ogrenci_id,))

            assert cur.fetchone()[0] == 0

    finally:
        conn.rollback()
        conn.close()


def test_ertelenen_ogrenci_silinemez(gecici_gonullu):
    ogrenci_id = gecici_gonullu

    sunucu.ogrenci_silme_ertele(
        ogrenci_id=ogrenci_id,
        veri=sunucu.OgrenciErteleModeli(
            yeni_uyari_tarihi=(
                date.today() + timedelta(days=30)
            )
        ),
        yetkili_id=None,
    )

    with pytest.raises(HTTPException) as hata:
        sunucu.ogrenci_on_yil_sil(
            ogrenci_id=ogrenci_id,
            veri=sunucu.OgrenciSilOnayModeli(
                onayla=True
            ),
            yetkili_id=None,
        )

    assert hata.value.status_code == 409


def test_on_yili_dolan_gonullu_guvenle_silinir(gecici_gonullu):
    ogrenci_id = gecici_gonullu

    sonuc = sunucu.ogrenci_on_yil_sil(
        ogrenci_id=ogrenci_id,
        veri=sunucu.OgrenciSilOnayModeli(
            onayla=True
        ),
        yetkili_id=None,
    )

    assert sonuc["durum"] == "silindi"

    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM ogrenciler
                WHERE ogrenci_id = %s
            """, (ogrenci_id,))

            assert cur.fetchone()[0] == 0

            cur.execute("""
                SELECT COUNT(*)
                FROM denetim_kayitlari
                WHERE hedef_tablo = 'ogrenciler'
                  AND hedef_kayit_id = %s
                  AND olay_turu = 'DELETE'
            """, (ogrenci_id,))

            assert cur.fetchone()[0] == 1

    finally:
        conn.rollback()
        conn.close()



def faaliyet_kaydi_olustur(ogrenci_id):
    """Geçici öğrenciye yalnızca test DB'sinde faaliyet ekle."""
    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.faaliyet_id, b.birim_id
                FROM faaliyetler f
                CROSS JOIN faaliyet_birimleri b
                ORDER BY f.faaliyet_id, b.birim_id
                LIMIT 1
            """)

            kayit = cur.fetchone()
            if kayit is None:
                pytest.skip("Faaliyet veya birim bulunmuyor.")

            faaliyet_id, birim_id = kayit

            cur.execute("""
                INSERT INTO ogrenci_faaliyet_takip
                    (ogrenci_id, faaliyet_id, birim_id,
                     adet, faaliyet_tarihi, kayit_puani)
                SELECT %s, f.faaliyet_id, %s,
                       3, CURRENT_DATE, f.puan
                FROM faaliyetler AS f
                WHERE f.faaliyet_id = %s
                RETURNING takip_id
            """, (
                ogrenci_id,
                birim_id,
                faaliyet_id
            ))

            takip_id = cur.fetchone()[0]

        conn.commit()
        return takip_id, faaliyet_id

    finally:
        conn.close()


def faaliyet_sayisi(ogrenci_id):
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM ogrenci_faaliyet_takip
                WHERE ogrenci_id = %s
            """, (ogrenci_id,))
            return cur.fetchone()[0]
    finally:
        conn.rollback()
        conn.close()


def test_faaliyetli_gonullu_faaliyetleriyle_silinir(gecici_gonullu):
    ogrenci_id = gecici_gonullu
    _, faaliyet_id = faaliyet_kaydi_olustur(ogrenci_id)

    try:
        assert faaliyet_sayisi(ogrenci_id) == 1

        sonuc = sunucu.ogrenci_on_yil_sil(
            ogrenci_id=ogrenci_id,
            veri=sunucu.OgrenciSilOnayModeli(onayla=True),
            yetkili_id=None,
        )

        assert sonuc["durum"] == "silindi"
        assert faaliyet_sayisi(ogrenci_id) == 0

        conn = psycopg2.connect(**VT_AYARLARI)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM ogrenciler WHERE ogrenci_id = %s",
                    (ogrenci_id,)
                )
                assert cur.fetchone()[0] == 0

                # Ortak faaliyet tanımı silinmemeli
                cur.execute(
                    "SELECT COUNT(*) FROM faaliyetler WHERE faaliyet_id = %s",
                    (faaliyet_id,)
                )
                assert cur.fetchone()[0] == 1

                cur.execute("""
                    SELECT COUNT(*)
                    FROM denetim_kayitlari
                    WHERE hedef_tablo = 'ogrenciler'
                      AND hedef_kayit_id = %s
                      AND olay_turu = 'DELETE'
                """, (ogrenci_id,))
                assert cur.fetchone()[0] == 1
        finally:
            conn.rollback()
            conn.close()

    finally:
        # Test bir noktada başarısız olursa fixture temizleyebilsin
        conn = psycopg2.connect(**VT_AYARLARI)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM ogrenci_faaliyet_takip
                    WHERE ogrenci_id = %s
                """, (ogrenci_id,))
            conn.commit()
        finally:
            conn.close()


def test_faaliyet_silme_audit_hatasinda_rollback(gecici_gonullu):
    ogrenci_id = gecici_gonullu
    faaliyet_kaydi_olustur(ogrenci_id)

    try:
        gercek_audit = sunucu.denetim_kaydi_olustur

        def audit_ve_hata(*args, **kwargs):
            gercek_audit(*args, **kwargs)
            raise RuntimeError("QA_FAALIYET_ROLLBACK")

        with patch.object(
            sunucu,
            "denetim_kaydi_olustur",
            side_effect=audit_ve_hata,
        ):
            with pytest.raises(HTTPException) as hata:
                sunucu.ogrenci_on_yil_sil(
                    ogrenci_id=ogrenci_id,
                    veri=sunucu.OgrenciSilOnayModeli(onayla=True),
                    yetkili_id=None,
                )

        assert hata.value.status_code == 500

        # Öğrenci de faaliyeti de geri gelmiş olmalı
        assert faaliyet_sayisi(ogrenci_id) == 1

        conn = psycopg2.connect(**VT_AYARLARI)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM ogrenciler WHERE ogrenci_id = %s",
                    (ogrenci_id,)
                )
                assert cur.fetchone()[0] == 1
        finally:
            conn.rollback()
            conn.close()

    finally:
        conn = psycopg2.connect(**VT_AYARLARI)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM ogrenci_faaliyet_takip
                    WHERE ogrenci_id = %s
                """, (ogrenci_id,))
            conn.commit()
        finally:
            conn.close()


def test_silme_audit_hatasinda_rollback(gecici_gonullu):
    ogrenci_id = gecici_gonullu
    gercek_audit = sunucu.denetim_kaydi_olustur

    def audit_ve_hata(*args, **kwargs):
        assert kwargs.get("mevcut_cursor") is not None

        gercek_audit(*args, **kwargs)

        raise RuntimeError("QA_SILME_ROLLBACK")

    with patch.object(
        sunucu,
        "denetim_kaydi_olustur",
        side_effect=audit_ve_hata,
    ):
        with pytest.raises(HTTPException) as hata:
            sunucu.ogrenci_on_yil_sil(
                ogrenci_id=ogrenci_id,
                veri=sunucu.OgrenciSilOnayModeli(
                    onayla=True
                ),
                yetkili_id=None,
            )

    assert hata.value.status_code == 500

    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM ogrenciler
                WHERE ogrenci_id = %s
            """, (ogrenci_id,))

            assert cur.fetchone()[0] == 1

            cur.execute("""
                SELECT COUNT(*)
                FROM denetim_kayitlari
                WHERE hedef_tablo = 'ogrenciler'
                  AND hedef_kayit_id = %s
                  AND olay_turu = 'DELETE'
            """, (ogrenci_id,))

            assert cur.fetchone()[0] == 0

    finally:
        conn.rollback()
        conn.close()
