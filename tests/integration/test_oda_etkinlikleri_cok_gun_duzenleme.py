"""Çok günlük etkinliğin kısaltılması ve günlük kayıtların yenilenmesi."""

import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_bes_gunden_uc_gune_duzenleme():
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
                JOIN roller r ON r.rol_id = k.rol_id
                WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE
                AND UPPER(TRIM(r.rol_adi)) <> 'ADMIN'
                ORDER BY p.personel_id LIMIT 1
            """)
            personel_id, kullanici_id = cur.fetchone()

            cur.execute("""
                SELECT oda_id FROM odalar
                WHERE aktif_mi = TRUE AND kapasite >= 1
                ORDER BY oda_id
            """)

            oda_id = None

            for (aday,) in cur.fetchall():
                if all(
                    oda_cakismasi_bul(
                        cur,
                        aday,
                        ilk_gun + timedelta(days=i, hours=14),
                        ilk_gun + timedelta(days=i, hours=16),
                    ) is None
                    for i in range(5)
                ):
                    oda_id = aday
                    break

            assert oda_id is not None, "Uygun test odası yok."

        conn.commit()

        app = FastAPI()
        app.include_router(
            router_olustur(
                lambda izin: lambda: kullanici_id,
                VT_AYARLARI,
            )
        )

        with TestClient(app) as client:
            yanit = client.post(
                "/api/oda-etkinlikleri",
                json={
                    "oda_id": oda_id,
                    "organize_eden_personel_id": personel_id,
                    "etkinlik_adi": (
                        "TKYS_DUZENLEME_" + uuid4().hex[:10]
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
                    SELECT COUNT(*)
                    FROM oda_etkinlik_gunleri
                    WHERE etkinlik_id = %s
                """, (etkinlik_id,))
                assert cur.fetchone()[0] == 5

            conn.rollback()
            # Beş günlük etkinlik, orta gündeki filtrede görünmeli.
            liste = client.get(
                "/api/oda-etkinlikleri",
                params={
                    "baslangic": "2047-11-25",
                    "bitis": "2047-11-25",
                },
            )
            assert liste.status_code == 200, liste.text
            bulunanlar = [
                e for e in liste.json()["etkinlikler"]
                if e["etkinlik_id"] == etkinlik_id
            ]
            assert len(bulunanlar) == 1
            print("PASS | 25 Kasım filtresinde tek etkinlik")

            print("PASS | İlk kayıt: 5 gün")

            yanit = client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}",
                json={
                    "bitis_zamani": "2047-11-25T16:00:00"
                },
            )
            assert yanit.status_code == 200, yanit.text

            with conn.cursor() as cur:
                cur.execute("""
                    SELECT baslangic_zamani, bitis_zamani
                    FROM oda_etkinlik_gunleri
                    WHERE etkinlik_id = %s
                    ORDER BY baslangic_zamani
                """, (etkinlik_id,))
                araliklar = cur.fetchall()

                assert len(araliklar) == 3

                for i, (bas, bit) in enumerate(araliklar):
                    gun = ilk_gun + timedelta(days=i)
                    assert bas == gun.replace(hour=14)
                    assert bit == gun.replace(hour=16)

                for i in range(3):
                    gun = ilk_gun + timedelta(days=i)
                    assert oda_cakismasi_bul(
                        cur,
                        oda_id,
                        gun.replace(hour=14),
                        gun.replace(hour=16),
                    ) == "etkinlik"

                for i in (3, 4):
                    gun = ilk_gun + timedelta(days=i)
                    assert oda_cakismasi_bul(
                        cur,
                        oda_id,
                        gun.replace(hour=14),
                        gun.replace(hour=16),
                    ) is None

            conn.rollback()

            # Kısaltılan etkinlik 27 Kasım'da görünmemeli.
            liste = client.get(
                "/api/oda-etkinlikleri",
                params={
                    "baslangic": "2047-11-27",
                    "bitis": "2047-11-27",
                },
            )
            assert liste.status_code == 200, liste.text
            assert not any(
                e["etkinlik_id"] == etkinlik_id
                for e in liste.json()["etkinlikler"]
            )
            print("PASS | 27 Kasım filtresinde görünmüyor")

            print("PASS | Düzenleme sonrası: 3 gün")
            print("PASS | İlk 3 gün dolu")
            print("PASS | Son 2 gün serbest")

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
