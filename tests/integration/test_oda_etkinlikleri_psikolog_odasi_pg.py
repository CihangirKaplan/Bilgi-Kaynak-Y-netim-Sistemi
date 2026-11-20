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
                JOIN roller r ON r.rol_id = k.rol_id
                WHERE p.aktif_mi IS TRUE
                  AND k.aktif_mi IS TRUE
                AND UPPER(TRIM(r.rol_adi)) <> 'ADMIN'
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


def test_admin_duzenleyen_patch_kurali():
    """Admin'e yeni atama yasak; eski Admin kaydı düzenlenebilir."""
    import os
    from uuid import uuid4

    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    etkinlik_id = None

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            cur.execute("""
                SELECT p.personel_id, UPPER(TRIM(r.rol_adi))
                FROM personel p
                JOIN kullanicilar k
                  ON k.kullanici_id = p.kullanici_id
                JOIN roller r ON r.rol_id = k.rol_id
                WHERE p.aktif_mi IS TRUE
                  AND k.aktif_mi IS TRUE
                ORDER BY p.personel_id
            """)

            personeller = cur.fetchall()
            adminler = [
                p for p, rol in personeller if rol == "ADMIN"
            ]
            normal = [
                p for p, rol in personeller if rol != "ADMIN"
            ]

            assert adminler, "Aktif Admin bulunamadi."
            assert normal, "Aktif normal personel bulunamadi."

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

            bas = datetime(2049, 7, 15, 10)
            bit = datetime(2049, 7, 15, 11)

            oda_id = next(
                (
                    oda
                    for (oda,) in cur.fetchall()
                    if oda_cakismasi_bul(cur, oda, bas, bit) is None
                ),
                None,
            )

            assert oda_id is not None, "Uygun oda bulunamadi."

        conn.rollback()

        app = FastAPI()
        app.include_router(
            router_olustur(
                lambda izin: lambda: 1,
                VT_AYARLARI,
            )
        )

        with TestClient(app) as client:
            cevap = client.post(
                "/api/oda-etkinlikleri",
                json={
                    "oda_id": oda_id,
                    "organize_eden_personel_id": normal[0],
                    "etkinlik_adi": "TKYS_ADMIN_PATCH_" + uuid4().hex[:8],
                    "katilimci_sayisi": 1,
                    "baslangic_zamani": bas.isoformat(),
                    "bitis_zamani": bit.isoformat(),
                },
            )
            assert cevap.status_code == 201, cevap.text
            etkinlik_id = cevap.json()["etkinlik_id"]

            cevap = client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}",
                json={
                    "organize_eden_personel_id": adminler[0]
                },
            )
            assert cevap.status_code == 422, cevap.text
            print("PASS | Normal personelden Admin'e PATCH: 422")

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT organize_eden_personel_id
                    FROM oda_etkinlikleri
                    WHERE etkinlik_id = %s
                """, (etkinlik_id,))
                assert cur.fetchone()[0] == normal[0]

            conn.rollback()
            print("PASS | Reddedilen PATCH kaydi degistirmedi.")

            # Eski Admin kaydını taklit etmek için yalnızca
            # bu testin oluşturduğu geçici etkinliği değiştir.
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE oda_etkinlikleri
                    SET organize_eden_personel_id = %s
                    WHERE etkinlik_id = %s
                """, (adminler[0], etkinlik_id))
            conn.commit()

            cevap = client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}",
                json={"etkinlik_adi": "TKYS_ADMIN_ESKI_KAYIT_TEST"},
            )
            assert cevap.status_code == 200, cevap.text
            print("PASS | Eski Admin etkinliginde ad duzenleme: 200")

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
