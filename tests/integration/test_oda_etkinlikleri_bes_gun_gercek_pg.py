"""Beş günlük etkinlik: gerçek PostgreSQL ve FastAPI testi."""

import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_bes_gunluk_etkinlik_olusturma_cakisma_iptal():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    etkinlik_id = None

    ilk_gun = datetime(2047, 11, 23)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            cur.execute("""
                SELECT p.personel_id, p.kullanici_id
                FROM personel p
                JOIN kullanicilar k
                  ON k.kullanici_id = p.kullanici_id
                WHERE p.aktif_mi = TRUE
                  AND k.aktif_mi = TRUE
                ORDER BY p.personel_id
                LIMIT 1
            """)
            personel = cur.fetchone()
            assert personel, "Aktif personel bulunamadı."
            personel_id, kullanici_id = personel

            cur.execute("""
                SELECT oda_id
                FROM odalar
                WHERE aktif_mi = TRUE
                ORDER BY oda_id
            """)
            odalar = [r[0] for r in cur.fetchall()]

            oda_id = None

            for aday in odalar:
                if all(
                    oda_cakismasi_bul(
                        cur,
                        aday,
                        ilk_gun + timedelta(days=i, hours=13),
                        ilk_gun + timedelta(days=i, hours=17),
                    ) is None
                    for i in range(5)
                ):
                    oda_id = aday
                    break

            assert oda_id is not None, (
                "Beş gün boyunca 13.00-17.00 arası "
                "uygun oda bulunamadı."
            )

        conn.commit()

        uygulama = FastAPI()
        uygulama.include_router(
            router_olustur(
                lambda izin: lambda: kullanici_id,
                VT_AYARLARI,
            )
        )

        with TestClient(uygulama) as client:
            yanit = client.post(
                "/api/oda-etkinlikleri",
                json={
                    "oda_id": oda_id,
                    "organize_eden_personel_id": personel_id,
                    "etkinlik_adi": (
                        "TKYS_BES_GUN_TEST_" + uuid4().hex[:10]
                    ),
                    "katilimci_sayisi": 1,
                    "baslangic_zamani": "2047-11-23T14:00:00",
                    "bitis_zamani": "2047-11-27T16:00:00",
                },
            )

            assert yanit.status_code == 201, yanit.text
            etkinlik_id = yanit.json()["etkinlik_id"]

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT baslangic_zamani, bitis_zamani
                    FROM oda_etkinlik_gunleri
                    WHERE etkinlik_id = %s
                    ORDER BY baslangic_zamani
                """, (etkinlik_id,))
                gunler = cur.fetchall()

                assert len(gunler) == 5

                for i, (bas, bit) in enumerate(gunler):
                    gun = ilk_gun + timedelta(days=i)

                    assert bas == gun.replace(hour=14)
                    assert bit == gun.replace(hour=16)

                    assert oda_cakismasi_bul(
                        cur, oda_id,
                        gun.replace(hour=13),
                        gun.replace(hour=14),
                    ) is None

                    assert oda_cakismasi_bul(
                        cur, oda_id,
                        gun.replace(hour=14),
                        gun.replace(hour=16),
                    ) == "etkinlik"

                    assert oda_cakismasi_bul(
                        cur, oda_id,
                        gun.replace(hour=16),
                        gun.replace(hour=17),
                    ) is None

            conn.rollback()

            iptal = client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}/iptal"
            )
            assert iptal.status_code == 200, iptal.text

            with conn.cursor() as cur:
                for i in range(5):
                    gun = ilk_gun + timedelta(days=i)

                    assert oda_cakismasi_bul(
                        cur, oda_id,
                        gun.replace(hour=14),
                        gun.replace(hour=16),
                    ) is None

            conn.rollback()

        print("PASS | Beş günlük etkinlik oluşturuldu.")
        print("PASS | Günlük kayıt sayısı: 5")
        print("PASS | 14.00-16.00 dolu.")
        print("PASS | 13.00-14.00 ve 16.00-17.00 uygun.")
        print("PASS | İptal sonrası bütün günler serbest.")

    finally:
        conn.rollback()

        try:
            if etkinlik_id is not None:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = 'oda_etkinlikleri'
                          AND hedef_kayit_id = %s
                    """, (etkinlik_id,))

                    cur.execute("""
                        DELETE FROM oda_etkinlikleri
                        WHERE etkinlik_id = %s
                    """, (etkinlik_id,))

                conn.commit()
        finally:
            conn.close()
