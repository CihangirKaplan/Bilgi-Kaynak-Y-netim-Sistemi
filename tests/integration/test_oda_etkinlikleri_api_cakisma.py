"""Gerçek PostgreSQL ile Oda Etkinlikleri API çakışma testi."""

import os
from datetime import datetime
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur


def test_randevu_ve_cihaz_varken_etkinlik_reddedilir():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    randevu_id = None
    rezervasyon_id = None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            cur.execute("""
                SELECT oda_id FROM odalar
                WHERE aktif_mi = TRUE AND kapasite >= 1
                ORDER BY oda_id LIMIT 1
            """)
            oda = cur.fetchone()

            cur.execute("""
                SELECT personel_id, kullanici_id FROM personel
                WHERE aktif_mi = TRUE AND kullanici_id IS NOT NULL
                ORDER BY personel_id LIMIT 1
            """)
            personel = cur.fetchone()

            cur.execute("""
                SELECT danisan_kod_id FROM danisan_kodlari
                ORDER BY danisan_kod_id LIMIT 1
            """)
            danisan = cur.fetchone()

            cur.execute("""
                SELECT cihaz_id FROM cihazlar
                WHERE durum IN ('Kullanima_Hazir', 'Rezerve')
                ORDER BY cihaz_id LIMIT 1
            """)
            cihaz = cur.fetchone()

            assert all((oda, personel, danisan, cihaz))

            oda_id = oda[0]
            personel_id, kullanici_id = personel
            isaret = uuid4().hex[:12]

            # Gelecekte, birbiriyle çakışmayan iki test aralığı.
            araliklar = [
                (datetime(2048, 6, 15, 10), datetime(2048, 6, 15, 11)),
                (datetime(2048, 6, 15, 12), datetime(2048, 6, 15, 13)),
            ]

            from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul

            for bas, bit in araliklar:
                assert oda_cakismasi_bul(
                    cur, oda_id, bas, bit
                ) is None, "Test aralığında önceden bir kayıt var."

            cur.execute("""
                INSERT INTO randevular
                    (danisan_kod_id, psikolog_id, oda_id,
                     baslangic_zamani, bitis_zamani, durum)
                VALUES (%s, %s, %s, %s, %s, 'PLANLANDI')
                RETURNING randevu_id
            """, (
                danisan[0], personel_id, oda_id, *araliklar[0]
            ))
            randevu_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO cihaz_rezervasyonlari
                    (cihaz_id, kullanilacak_oda_id,
                     baslangic_zamani, bitis_zamani)
                VALUES (%s, %s, %s, %s)
                RETURNING rezervasyon_id
            """, (
                cihaz[0], oda_id, *araliklar[1]
            ))
            rezervasyon_id = cur.fetchone()[0]

        conn.commit()

        # Sadece test router'ında kimlik/yetki bağımlılığı değiştirilir.
        # Gerçek PostgreSQL ve etkinlik endpoint'i kullanılır.
        def test_izin_kontrol(_izin):
            return lambda: kullanici_id

        test_app = FastAPI()
        test_app.include_router(
            router_olustur(test_izin_kontrol, VT_AYARLARI)
        )

        with TestClient(test_app) as client:
            for tur, (bas, bit) in zip(
                ("randevu", "cihaz"), araliklar
            ):
                veri = {
                    "oda_id": oda_id,
                    "organize_eden_personel_id": personel_id,
                    "etkinlik_adi": f"TKYS_API_TEST_{isaret}",
                    "katilimci_sayisi": 1,
                    "baslangic_zamani": bas.isoformat(),
                    "bitis_zamani": bit.isoformat(),
                }

                cevap = client.post(
                    "/api/oda-etkinlikleri", json=veri
                )

                print(f"{tur}: HTTP {cevap.status_code}")
                assert cevap.status_code == 409, cevap.text

        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM oda_etkinlikleri
                WHERE etkinlik_adi = %s
            """, (f"TKYS_API_TEST_{isaret}",))
            assert cur.fetchone()[0] == 0

        conn.rollback()
        print("PASS | Her iki çakışma reddedildi; etkinlik oluşturulmadı.")

    finally:
        conn.rollback()
        try:
            with conn.cursor() as cur:
                if rezervasyon_id is not None:
                    cur.execute("""
                        DELETE FROM cihaz_rezervasyonlari
                        WHERE rezervasyon_id = %s
                    """, (rezervasyon_id,))
                if randevu_id is not None:
                    cur.execute("""
                        DELETE FROM randevular
                        WHERE randevu_id = %s
                    """, (randevu_id,))
            conn.commit()
            print("PASS | Geçici test kayıtları temizlendi.")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
