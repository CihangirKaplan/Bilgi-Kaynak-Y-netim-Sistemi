"""Bağımsız gün/saatli etkinlik oluşturma ve düzenleme testi."""

import os
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import VT_AYARLARI
from server.oda_etkinlikleri_api import router_olustur
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_bagimsiz_oturumlar_olustur_ve_guncelle():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)
    etkinlik_id = None

    ilk_oturumlar = [
        ("2047-11-25T13:00:00", "2047-11-25T14:00:00"),
        ("2047-11-23T13:00:00", "2047-11-23T14:00:00"),
        ("2047-11-27T15:00:00", "2047-11-27T16:00:00"),
    ]

    yeni_oturumlar = [
        ("2047-11-23T13:00:00", "2047-11-23T14:00:00"),
        ("2047-11-27T15:00:00", "2047-11-27T16:00:00"),
    ]

    def gunler_json(araliklar):
        return [
            {
                "baslangic_zamani": bas,
                "bitis_zamani": bit,
            }
            for bas, bit in araliklar
        ]

    def db_araliklari(cur):
        cur.execute(
            """
            SELECT baslangic_zamani, bitis_zamani
            FROM oda_etkinlik_gunleri
            WHERE etkinlik_id = %s
            ORDER BY baslangic_zamani
            """,
            (etkinlik_id,),
        )
        return cur.fetchall()

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
                WHERE p.aktif_mi IS TRUE AND k.aktif_mi IS TRUE
                AND UPPER(TRIM(r.rol_adi)) <> 'ADMIN'
                ORDER BY p.personel_id
                LIMIT 1
            """)
            personel = cur.fetchone()
            assert personel, "Aktif test personeli bulunamadı."
            personel_id, kullanici_id = personel

            cur.execute("""
                SELECT oda_id
                FROM odalar
                WHERE aktif_mi IS TRUE AND kapasite >= 1
                ORDER BY oda_id
            """)

            oda_id = None
            for (aday,) in cur.fetchall():
                if all(
                    oda_cakismasi_bul(
                        cur, aday,
                        datetime.fromisoformat(bas),
                        datetime.fromisoformat(bit),
                    ) is None
                    for bas, bit in ilk_oturumlar
                ):
                    oda_id = aday
                    break

            assert oda_id is not None, "Uygun test odası bulunamadı."

        conn.rollback()

        app = FastAPI()
        app.include_router(
            router_olustur(
                lambda izin: lambda: kullanici_id,
                VT_AYARLARI,
            )
        )

        with TestClient(app) as client:
            cevap = client.post(
                "/api/oda-etkinlikleri",
                json={
                    "oda_id": oda_id,
                    "organize_eden_personel_id": personel_id,
                    "etkinlik_adi": (
                        "TKYS_BAGIMSIZ_" + uuid4().hex[:10]
                    ),
                    "katilimci_sayisi": 1,
                    "gunler": gunler_json(ilk_oturumlar),
                },
            )

            assert cevap.status_code == 201, cevap.text
            etkinlik_id = cevap.json()["etkinlik_id"]

            with conn.cursor() as cur:
                araliklar = db_araliklari(cur)

                beklenen = sorted(
                    (
                        datetime.fromisoformat(bas),
                        datetime.fromisoformat(bit),
                    )
                    for bas, bit in ilk_oturumlar
                )
                assert araliklar == beklenen

                # Pazartesi ve çarşamba 13.00-14.00;
                # cuma 15.00-16.00 dolu olmalı.
                for bas, bit in beklenen:
                    assert oda_cakismasi_bul(
                        cur, oda_id, bas, bit
                    ) == "etkinlik"

                # Salı ve perşembe boş kalmalı.
                for gun in (24, 26):
                    bas = datetime(2047, 11, gun, 13)
                    assert oda_cakismasi_bul(
                        cur, oda_id,
                        bas, bas + timedelta(hours=1),
                    ) is None

            conn.rollback()
            # Yalnızca gerçekten oturum bulunan günlerde listelenmeli.
            for gun, gorunmeli in (
                (23, True),
                (24, False),
                (25, True),
                (26, False),
                (27, True),
            ):
                tarih = f"2047-11-{gun:02d}"
                cevap = client.get(
                    "/api/oda-etkinlikleri",
                    params={"baslangic": tarih, "bitis": tarih},
                )
                assert cevap.status_code == 200, cevap.text

                bulunanlar = [
                    e for e in cevap.json()["etkinlikler"]
                    if e["etkinlik_id"] == etkinlik_id
                ]
                assert len(bulunanlar) == int(gorunmeli), tarih

                if gorunmeli:
                    assert len(bulunanlar[0]["gunler"]) == 3

            print("PASS | Oturum olmayan günler filtrede görünmüyor.")
            print("PASS | Etkinlik tek kayıt ve üç oturumla listeleniyor.")
            print("PASS | Üç bağımsız oturum kaydedildi.")
            print("PASS | Aradaki günler boş kaldı.")

            cevap = client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}",
                json={
                    "gunler": gunler_json(yeni_oturumlar),
                },
            )
            assert cevap.status_code == 200, cevap.text

            with conn.cursor() as cur:
                araliklar = db_araliklari(cur)
                beklenen = [
                    (
                        datetime.fromisoformat(bas),
                        datetime.fromisoformat(bit),
                    )
                    for bas, bit in yeni_oturumlar
                ]
                assert araliklar == beklenen

                # Çarşamba oturumu kaldırıldı.
                assert oda_cakismasi_bul(
                    cur, oda_id,
                    datetime(2047, 11, 25, 13),
                    datetime(2047, 11, 25, 14),
                ) is None

            conn.rollback()
            print("PASS | Oturum listesi güncellendi.")
            print("PASS | Kaldırılan oturum odayı serbest bıraktı.")

    finally:
        conn.rollback()
        try:
            if etkinlik_id is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = 'oda_etkinlikleri'
                          AND hedef_kayit_id = %s
                        """,
                        (etkinlik_id,),
                    )
                    cur.execute(
                        """
                        DELETE FROM oda_etkinlikleri
                        WHERE etkinlik_id = %s
                        """,
                        (etkinlik_id,),
                    )
                conn.commit()
        finally:
            conn.close()
