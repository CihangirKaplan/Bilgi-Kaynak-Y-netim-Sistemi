"""Oda Etkinlikleri gerçek PostgreSQL eşzamanlılık testi."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur

TEST_DB = "crkys_alembic_test"


def test_ayni_oda_iki_es_zamanli_etkinlik():
    assert VT_AYARLARI["dbname"] == TEST_DB

    baglanti = psycopg2.connect(**VT_AYARLARI)
    isaret = f"TKYS_QA_{uuid4().hex}"
    baslangic = "2040-06-15T10:30:00"
    bitis = "2040-06-15T11:30:00"

    try:
        with baglanti.cursor() as cursor:
            cursor.execute("SELECT current_database()")
            assert cursor.fetchone()[0] == TEST_DB

            cursor.execute("""
                SELECT oda_id
                FROM odalar
                WHERE aktif_mi = TRUE AND kapasite >= 1
                ORDER BY oda_id
                LIMIT 1
            """)
            oda = cursor.fetchone()
            assert oda, "Aktif test odası bulunamadı."

            cursor.execute("""
                SELECT p.personel_id, p.kullanici_id
                FROM personel p
                JOIN kullanicilar k
                  ON k.kullanici_id = p.kullanici_id
                JOIN roller r ON r.rol_id = k.rol_id
                WHERE p.aktif_mi = TRUE
                  AND k.aktif_mi = TRUE
                AND UPPER(TRIM(r.rol_adi)) <> 'ADMIN'
                ORDER BY p.personel_id
                LIMIT 1
            """)
            personel = cursor.fetchone()
            assert personel, "Aktif test personeli bulunamadı."

        baglanti.rollback()

        oda_id = oda[0]
        personel_id, kullanici_id = personel

        def test_izin_kontrol(_izin):
            return lambda: kullanici_id

        test_app = FastAPI()
        test_app.include_router(
            router_olustur(test_izin_kontrol, VT_AYARLARI)
        )

        baslama_engeli = Barrier(2)

        def etkinlik_olustur(sira):
            veri = {
                "oda_id": oda_id,
                "organize_eden_personel_id": personel_id,
                "etkinlik_adi": f"{isaret}_{sira}",
                "katilimci_sayisi": 1,
                "baslangic_zamani": baslangic,
                "bitis_zamani": bitis,
            }
            baslama_engeli.wait(timeout=10)
            with TestClient(test_app) as client:
                yanit = client.post(
                    "/api/oda-etkinlikleri",
                    json=veri,
                )
            return yanit.status_code, yanit.text

        print("\n=== EŞZAMANLI ETKİNLİK TESTİ ===")

        with ThreadPoolExecutor(max_workers=2) as havuz:
            gelecekler = [
                havuz.submit(etkinlik_olustur, sira)
                for sira in (1, 2)
            ]
            sonuclar = [
                gelecek.result(timeout=30)
                for gelecek in gelecekler
            ]

        for sira, (durum, metin) in enumerate(sonuclar, 1):
            print(f"İstek {sira}: HTTP {durum} | {metin[:160]}")

        durumlar = sorted(durum for durum, _ in sonuclar)
        assert durumlar == [201, 409], (
            f"Beklenen [201, 409], gelen {durumlar}"
        )

        print("PASS | Çakışan iki istekten yalnızca biri kaydedildi.")

        with baglanti.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*)
                FROM oda_etkinlikleri
                WHERE etkinlik_adi LIKE %s
            """, (isaret + "%",))
            adet = cursor.fetchone()[0]

        assert adet == 1, f"Beklenen 1 kayıt, bulunan {adet}"
        print("PASS | Veritabanında yalnızca bir etkinlik var.")

    finally:
        try:
            baglanti.rollback()
            with baglanti.cursor() as cursor:
                cursor.execute("""
                    SELECT etkinlik_id
                    FROM oda_etkinlikleri
                    WHERE etkinlik_adi LIKE %s
                """, (isaret + "%",))
                etkinlik_ids = [
                    kayit[0] for kayit in cursor.fetchall()
                ]

                if etkinlik_ids:
                    cursor.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = 'oda_etkinlikleri'
                          AND hedef_kayit_id = ANY(%s)
                    """, (etkinlik_ids,))
                    cursor.execute("""
                        DELETE FROM oda_etkinlikleri
                        WHERE etkinlik_id = ANY(%s)
                    """, (etkinlik_ids,))

            baglanti.commit()
            print("PASS | Test etkinlikleri ve audit kayıtları temizlendi.")
        except Exception:
            baglanti.rollback()
            raise
        finally:
            baglanti.close()
