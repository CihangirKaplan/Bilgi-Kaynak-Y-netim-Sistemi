"""Gerçek PostgreSQL ile eşzamanlı oda değiştirme ve iptal testleri."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Barrier
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_es_zamanli_oda_degistirme_ve_iptal():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    etkinlik_ids = []

    def izin_kontrol(_izin):
        return lambda: kullanici_id

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            cur.execute("""
                SELECT p.personel_id, p.kullanici_id
                FROM personel p
                JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
                WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE
                ORDER BY p.personel_id LIMIT 1
            """)
            personel_id, kullanici_id = cur.fetchone()

            cur.execute("""
                SELECT oda_id
                FROM odalar
                WHERE aktif_mi = TRUE AND kapasite >= 1
                ORDER BY oda_id LIMIT 3
            """)
            odalar = [r[0] for r in cur.fetchall()]
            assert len(odalar) == 3, "Üç aktif oda gerekli."

            bas = datetime(2049, 6, 15, 10)
            bit = datetime(2049, 6, 15, 11)

            for oda_id in odalar:
                assert oda_cakismasi_bul(
                    cur, oda_id, bas, bit
                ) is None, f"Oda {oda_id} test saatinde dolu."

            isaret = uuid4().hex[:10]

            for sira, oda_id in enumerate(odalar[:2], 1):
                cur.execute("""
                    INSERT INTO oda_etkinlikleri (
                        oda_id, organize_eden_personel_id,
                        etkinlik_adi, katilimci_sayisi,
                        baslangic_zamani, bitis_zamani
                    )
                    VALUES (%s, %s, %s, 1, %s, %s)
                    RETURNING etkinlik_id
                """, (
                    oda_id, personel_id,
                    f"TKYS_CONC_{isaret}_{sira}", bas, bit
                ))
                etkinlik_id = cur.fetchone()[0]
                etkinlik_ids.append(etkinlik_id)

                # Yeni veri modelinde her etkinliğin en az
                # bir günlük kullanım kaydı bulunmalıdır.
                cur.execute(
                    '''
                    INSERT INTO oda_etkinlik_gunleri (
                        etkinlik_id,
                        baslangic_zamani,
                        bitis_zamani
                    )
                    VALUES (%s, %s, %s)
                    ''',
                    (etkinlik_id, bas, bit),
                )

        conn.commit()

        test_app = FastAPI()
        test_app.include_router(
            router_olustur(izin_kontrol, VT_AYARLARI)
        )

        def paralel_istekler(istekler):
            bariyer = Barrier(len(istekler))

            def calistir(yol, veri):
                bariyer.wait(timeout=10)
                with TestClient(test_app) as client:
                    return client.patch(yol, json=veri)

            with ThreadPoolExecutor(max_workers=len(istekler)) as havuz:
                futures = [
                    havuz.submit(calistir, yol, veri)
                    for yol, veri in istekler
                ]
                return [f.result(timeout=20) for f in futures]

        print("\n=== EŞZAMANLI ODA DEĞİŞTİRME ===")

        yanitlar = paralel_istekler([
            (
                f"/api/oda-etkinlikleri/{etkinlik_id}",
                {"oda_id": odalar[2]},
            )
            for etkinlik_id in etkinlik_ids
        ])

        kodlar = sorted(y.status_code for y in yanitlar)
        print("HTTP durumları:", kodlar)
        for y in yanitlar:
            print(y.text[:200])

        assert kodlar == [200, 409], kodlar

        with conn.cursor() as cur:
            cur.execute("""
                SELECT etkinlik_id, oda_id
                FROM oda_etkinlikleri
                WHERE etkinlik_id = ANY(%s)
                ORDER BY etkinlik_id
            """, (etkinlik_ids,))
            kayitlar = cur.fetchall()
            assert len(kayitlar) == 2
            assert sum(
                oda_id == odalar[2]
                for _, oda_id in kayitlar
            ) == 1

        conn.rollback()
        print("PASS | Aynı hedef odaya yalnızca bir etkinlik taşındı.")

        print("\n=== EŞZAMANLI İPTAL ===")

        # İki isteğin de aynı etkinliği iptal etmesini dene.
        iptal_id = etkinlik_ids[0]
        yanitlar = paralel_istekler([
            (f"/api/oda-etkinlikleri/{iptal_id}/iptal", None),
            (f"/api/oda-etkinlikleri/{iptal_id}/iptal", None),
        ])

        kodlar = sorted(y.status_code for y in yanitlar)
        print("HTTP durumları:", kodlar)

        assert kodlar == [200, 409], kodlar

        with conn.cursor() as cur:
            cur.execute("""
                SELECT iptal_edildi_mi
                FROM oda_etkinlikleri
                WHERE etkinlik_id = %s
            """, (iptal_id,))
            assert cur.fetchone()[0] is True

            cur.execute("""
                SELECT COUNT(*)
                FROM denetim_kayitlari
                WHERE hedef_tablo = 'oda_etkinlikleri'
                  AND hedef_kayit_id = %s
                  AND olay_turu = 'CANCEL'
            """, (iptal_id,))
            assert cur.fetchone()[0] == 1

        conn.rollback()
        print("PASS | Etkinlik bir kez iptal edildi; tek audit kaydı oluştu.")

    finally:
        conn.rollback()
        try:
            with conn.cursor() as cur:
                if etkinlik_ids:
                    cur.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = 'oda_etkinlikleri'
                          AND hedef_kayit_id = ANY(%s)
                    """, (etkinlik_ids,))
                    cur.execute("""
                        DELETE FROM oda_etkinlikleri
                        WHERE etkinlik_id = ANY(%s)
                    """, (etkinlik_ids,))
            conn.commit()
            print("PASS | Geçici etkinlikler ve audit kayıtları temizlendi.")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
