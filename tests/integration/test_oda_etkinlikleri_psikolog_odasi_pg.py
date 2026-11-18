"""Psikoloğa atanmış odada etkinlik POST/PATCH engelleme testi."""

import os
from datetime import datetime
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_psikolog_odasi_post_patch_409():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    etkinlik_id = None

    bas = datetime(2049, 6, 15, 13)
    bit = datetime(2049, 6, 15, 14)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            cur.execute("""
                SELECT p.personel_id, p.kullanici_id
                FROM personel p
                JOIN kullanicilar k
                  ON k.kullanici_id = p.kullanici_id
                WHERE p.aktif_mi IS TRUE
                  AND k.aktif_mi IS TRUE
                ORDER BY p.personel_id LIMIT 1
            """)
            personel = cur.fetchone()
            assert personel, "Aktif personel bulunamadı."
            personel_id, kullanici_id = personel

            cur.execute("""
                SELECT DISTINCT o.oda_id
                FROM odalar o
                JOIN psikolog_odalar po ON po.oda_id = o.oda_id
                JOIN kullanicilar k
                  ON k.kullanici_id = po.kullanici_id
                WHERE o.aktif_mi IS TRUE
                  AND k.aktif_mi IS TRUE
                  AND o.kapasite >= 1
                ORDER BY o.oda_id
            """)
            atanmis_odalar = [r[0] for r in cur.fetchall()]
            assert atanmis_odalar, "Aktif psikoloğa atanmış oda yok."

            cur.execute("""
                SELECT o.oda_id
                FROM odalar o
                WHERE o.aktif_mi IS TRUE
                  AND o.kapasite >= 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM psikolog_odalar po
                      JOIN kullanicilar k
                        ON k.kullanici_id = po.kullanici_id
                      WHERE po.oda_id = o.oda_id
                        AND k.aktif_mi IS TRUE
                  )
                ORDER BY o.oda_id
            """)

            bos_oda = None
            for (aday,) in cur.fetchall():
                if oda_cakismasi_bul(cur, aday, bas, bit) is None:
                    bos_oda = aday
                    break

            assert bos_oda is not None, "Uygun boş oda yok."

        conn.rollback()

        app = FastAPI()
        app.include_router(
            router_olustur(
                lambda izin: lambda: kullanici_id,
                VT_AYARLARI,
            )
        )

        payload = {
            "organize_eden_personel_id": personel_id,
            "etkinlik_adi": "TKYS_PSI_TEST_" + uuid4().hex[:10],
            "katilimci_sayisi": 1,
            "gunler": [{
                "baslangic_zamani": bas.isoformat(),
                "bitis_zamani": bit.isoformat(),
            }],
        }

        with TestClient(app) as client:
            # Atanmış oda: POST reddedilmeli.
            cevap = client.post(
                "/api/oda-etkinlikleri",
                json={**payload, "oda_id": atanmis_odalar[0]},
            )
            assert cevap.status_code == 409, cevap.text
            print("PASS | Psikolog odasında POST: 409")

            # Atanmamış oda: POST başarılı olmalı.
            cevap = client.post(
                "/api/oda-etkinlikleri",
                json={**payload, "oda_id": bos_oda},
            )
            assert cevap.status_code == 201, cevap.text
            etkinlik_id = cevap.json()["etkinlik_id"]
            print("PASS | Atanmamış odada POST: 201")

            # Psikolog odasına taşıma: PATCH reddedilmeli.
            cevap = client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}",
                json={"oda_id": atanmis_odalar[0]},
            )
            assert cevap.status_code == 409, cevap.text
            print("PASS | Psikolog odasına PATCH: 409")

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT oda_id
                    FROM oda_etkinlikleri
                    WHERE etkinlik_id = %s
                    """,
                    (etkinlik_id,),
                )
                assert cur.fetchone()[0] == bos_oda

            conn.rollback()
            print("PASS | Reddedilen PATCH mevcut odayı değiştirmedi.")

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
