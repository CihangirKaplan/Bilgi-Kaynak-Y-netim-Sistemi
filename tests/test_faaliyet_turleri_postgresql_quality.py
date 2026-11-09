"""Faaliyet puanları: gerçek PostgreSQL entegrasyon testleri."""

import uuid
from unittest.mock import patch

import psycopg2
import pytest
from fastapi import HTTPException

from sunucu import (
    VT_AYARLARI,
    FaaliyetTuruDuzenleModeli,
    faaliyet_turu_duzenle,
)


class SahteBaglanti:
    """API commit işlemini test boyunca engeller."""

    def __init__(self, gercek):
        self.gercek = gercek

    def cursor(self, *args, **kwargs):
        return self.gercek.cursor(*args, **kwargs)

    def commit(self):
        pass

    def rollback(self):
        self.gercek.rollback()

    def close(self):
        pass


@pytest.fixture
def ortam():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    baglanti = psycopg2.connect(**VT_AYARLARI)
    baglanti.autocommit = False

    try:
        with baglanti.cursor() as cur:
            cur.execute("""
                SELECT ogrenci_id
                FROM ogrenciler
                ORDER BY ogrenci_id
                LIMIT 1
            """)
            ogrenci = cur.fetchone()

            cur.execute("""
                SELECT birim_id
                FROM faaliyet_birimleri
                ORDER BY birim_id
                LIMIT 1
            """)
            birim = cur.fetchone()

            cur.execute("""
                SELECT kullanici_id
                FROM kullanicilar
                ORDER BY kullanici_id
                LIMIT 1
            """)
            kullanici = cur.fetchone()

            if not all((ogrenci, birim, kullanici)):
                pytest.skip(
                    "Test DB'de öğrenci, birim veya kullanıcı yok."
                )

            ad = "QA_PUAN_" + uuid.uuid4().hex[:12]

            cur.execute("""
                INSERT INTO faaliyetler
                    (faaliyet_adi, puan, aktif_mi)
                VALUES (%s, 8, TRUE)
                RETURNING faaliyet_id
            """, (ad,))
            faaliyet_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO ogrenci_faaliyet_takip
                    (ogrenci_id, faaliyet_id, birim_id,
                     adet, faaliyet_tarihi, kayit_puani)
                VALUES (%s, %s, %s, 10, CURRENT_DATE, 8)
                RETURNING takip_id
            """, (
                ogrenci[0],
                faaliyet_id,
                birim[0],
            ))
            takip_id = cur.fetchone()[0]

        yield {
            "conn": baglanti,
            "ad": ad,
            "faaliyet_id": faaliyet_id,
            "takip_id": takip_id,
            "kullanici_id": kullanici[0],
        }

    finally:
        baglanti.rollback()
        baglanti.close()


def puanlari_oku(ortam):
    with ortam["conn"].cursor() as cur:
        cur.execute("""
            SELECT f.puan, t.kayit_puani,
                   t.adet * t.kayit_puani
            FROM faaliyetler f
            JOIN ogrenci_faaliyet_takip t
              ON t.faaliyet_id = f.faaliyet_id
            WHERE t.takip_id = %s
        """, (ortam["takip_id"],))
        return cur.fetchone()


def guncelle(ortam, puan, gecmis):
    model = FaaliyetTuruDuzenleModeli(
        faaliyet_adi=ortam["ad"],
        puan=puan,
        gecmis_puanlari_guncelle=gecmis,
    )

    return faaliyet_turu_duzenle(
        ortam["faaliyet_id"],
        model,
        ortam["kullanici_id"],
    )


def test_pg_gecmis_puanlari_koru(ortam):
    gercek_connect = psycopg2.connect

    with patch(
        "sunucu.psycopg2.connect",
        return_value=SahteBaglanti(ortam["conn"]),
    ):
        sonuc = guncelle(ortam, 10, False)

    assert sonuc["durum"] == "basarili"
    assert puanlari_oku(ortam) == (10, 8, 80)


def test_pg_gecmis_puanlari_guncelle(ortam):
    with patch(
        "sunucu.psycopg2.connect",
        return_value=SahteBaglanti(ortam["conn"]),
    ):
        sonuc = guncelle(ortam, 12, True)

    assert sonuc["durum"] == "basarili"
    assert sonuc["guncellenen_gecmis_kayit"] == 1
    assert puanlari_oku(ortam) == (12, 12, 120)


def test_pg_audit_hatasinda_rollback(ortam):
    with (
        patch(
            "sunucu.psycopg2.connect",
            return_value=SahteBaglanti(ortam["conn"]),
        ),
        patch(
            "denetim.denetim_kaydi_olustur",
            side_effect=RuntimeError("QA_AUDIT_HATASI"),
        ),
    ):
        with pytest.raises(HTTPException) as hata:
            guncelle(ortam, 15, True)

    assert hata.value.status_code == 500

    # Rollback yeni oluşturulan test kayıtlarını da
    # geri aldığı için bunların silindiğini doğrula.
    with ortam["conn"].cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM faaliyetler
            WHERE faaliyet_id = %s
        """, (ortam["faaliyet_id"],))
        assert cur.fetchone()[0] == 0
