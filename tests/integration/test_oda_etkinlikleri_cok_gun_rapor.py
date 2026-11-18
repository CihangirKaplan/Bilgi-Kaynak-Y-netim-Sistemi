"""Çok günlük etkinliğin günlük yönetim raporuna yansıması."""

import os
from uuid import uuid4
from datetime import datetime, date, timedelta

import psycopg2
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.sunucu import app, VT_AYARLARI, mevcut_kullanici_id
from server.oda_etkinlikleri_api import router_olustur
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_cok_gunluk_etkinlik_gunluk_rapor():
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
                WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE
                ORDER BY p.personel_id LIMIT 1
            """)
            personel = cur.fetchone()
            assert personel, "Aktif personel bulunamadı."
            personel_id, olusturan_id = personel

            cur.execute("""
                SELECT k.kullanici_id
                FROM kullanicilar k
                JOIN rol_izinleri ri ON ri.rol_id = k.rol_id
                JOIN izinler i ON i.izin_id = ri.izin_id
                WHERE k.aktif_mi = TRUE
                  AND ri.izin_var = 1
                  AND i.izin_adi = 'YONETIM_RAPORLARI_GORUNTULE'
                ORDER BY k.kullanici_id
                LIMIT 1
            """)
            yetkili = cur.fetchone()
            assert yetkili, "Rapor yetkili kullanıcı bulunamadı."
            rapor_kullanici_id = yetkili[0]

            cur.execute("""
                SELECT oda_id
                FROM odalar
                WHERE aktif_mi = TRUE AND kapasite >= 1
                ORDER BY oda_id
            """)
            oda_id = None
            for (aday,) in cur.fetchall():
                if all(
                    oda_cakismasi_bul(
                        cur, aday,
                        ilk_gun + timedelta(days=i, hours=14),
                        ilk_gun + timedelta(days=i, hours=16),
                    ) is None
                    for i in range(5)
                ):
                    oda_id = aday
                    break

            assert oda_id is not None, "Uygun test odası bulunamadı."

        conn.rollback()

        etkinlik_app = FastAPI()
        etkinlik_app.include_router(
            router_olustur(
                lambda izin: lambda: olusturan_id,
                VT_AYARLARI,
            )
        )

        app.dependency_overrides[mevcut_kullanici_id] = (
            lambda: rapor_kullanici_id
        )

        with (
            TestClient(etkinlik_app) as etkinlik_client,
            TestClient(app) as rapor_client,
        ):
            def rapor_sayisi(gun):
                yanit = rapor_client.get(
                    "/api/yonetim-raporlari/bugun-merkezde",
                    params={"gun": gun.isoformat()},
                )
                assert yanit.status_code == 200, yanit.text
                return yanit.json()["ozet"]["planlanan_oda_etkinligi"]

            gunler = [
                date(2047, 11, 23) + timedelta(days=i)
                for i in range(5)
            ]

            once = {gun: rapor_sayisi(gun) for gun in gunler}

            def donem_ozeti(ilk, son):
                yanit = rapor_client.get(
                    "/api/yonetim-raporlari/proje-etkinlik-ozet",
                    params={
                        "baslangic": ilk,
                        "bitis": son,
                    },
                )
                assert yanit.status_code == 200, yanit.text
                return yanit.json()["ozet"]

            tek_gun_once = donem_ozeti("2047-11-25", "2047-11-25")
            bes_gun_once = donem_ozeti("2047-11-23", "2047-11-27")

            def donem_ozeti(ilk, son):
                yanit = rapor_client.get(
                    "/api/yonetim-raporlari/proje-etkinlik-ozet",
                    params={
                        "baslangic": ilk,
                        "bitis": son,
                    },
                )
                assert yanit.status_code == 200, yanit.text
                return yanit.json()["ozet"]

            tek_gun_once = donem_ozeti("2047-11-25", "2047-11-25")
            bes_gun_once = donem_ozeti("2047-11-23", "2047-11-27")

            yanit = etkinlik_client.post(
                "/api/oda-etkinlikleri",
                json={
                    "oda_id": oda_id,
                    "organize_eden_personel_id": personel_id,
                    "etkinlik_adi": (
                        "TKYS_RAPOR_TEST_" + uuid4().hex[:10]
                    ),
                    "katilimci_sayisi": 1,
                    "baslangic_zamani": "2047-11-23T14:00:00",
                    "bitis_zamani": "2047-11-27T16:00:00",
                },
            )
            assert yanit.status_code == 201, yanit.text
            etkinlik_id = yanit.json()["etkinlik_id"]

            tek_gun_sonra = donem_ozeti("2047-11-25", "2047-11-25")
            bes_gun_sonra = donem_ozeti("2047-11-23", "2047-11-27")

            for onceki, sonraki in (
                (tek_gun_once, tek_gun_sonra),
                (bes_gun_once, bes_gun_sonra),
            ):
                assert sonraki["etkinlik_toplam"] == (
                    onceki["etkinlik_toplam"] + 1
                )
                assert sonraki["etkinlik_iptal_edilmemis"] == (
                    onceki["etkinlik_iptal_edilmemis"] + 1
                )
                assert sonraki["kayitli_katilimci_toplami"] == (
                    onceki["kayitli_katilimci_toplami"] + 1
                )

            print("PASS | Tek günlük dönemde 1 etkinlik")
            print("PASS | Beş günlük dönemde 1 etkinlik")

            tek_gun_sonra = donem_ozeti("2047-11-25", "2047-11-25")
            bes_gun_sonra = donem_ozeti("2047-11-23", "2047-11-27")

            for onceki, sonraki in (
                (tek_gun_once, tek_gun_sonra),
                (bes_gun_once, bes_gun_sonra),
            ):
                assert sonraki["etkinlik_toplam"] == (
                    onceki["etkinlik_toplam"] + 1
                )
                assert sonraki["etkinlik_iptal_edilmemis"] == (
                    onceki["etkinlik_iptal_edilmemis"] + 1
                )
                assert sonraki["kayitli_katilimci_toplami"] == (
                    onceki["kayitli_katilimci_toplami"] + 1
                )

            print("PASS | Tek günlük dönemde 1 etkinlik")
            print("PASS | Beş günlük dönemde 1 etkinlik")

            for gun in gunler:
                assert rapor_sayisi(gun) == once[gun] + 1, gun

            print("PASS | Etkinlik beş günün raporunda görünüyor.")

            iptal = etkinlik_client.patch(
                f"/api/oda-etkinlikleri/{etkinlik_id}/iptal"
            )
            assert iptal.status_code == 200, iptal.text

            for ilk, son, onceki in (
                ("2047-11-25", "2047-11-25", tek_gun_once),
                ("2047-11-23", "2047-11-27", bes_gun_once),
            ):
                ozet = donem_ozeti(ilk, son)
                assert ozet["etkinlik_toplam"] == (
                    onceki["etkinlik_toplam"] + 1
                )
                assert ozet["etkinlik_iptal_edilmemis"] == (
                    onceki["etkinlik_iptal_edilmemis"]
                )
                assert ozet["kayitli_katilimci_toplami"] == (
                    onceki["kayitli_katilimci_toplami"]
                )

            print("PASS | İptal dönemsel aktif toplamdan çıkarıldı")

            for ilk, son, onceki in (
                ("2047-11-25", "2047-11-25", tek_gun_once),
                ("2047-11-23", "2047-11-27", bes_gun_once),
            ):
                ozet = donem_ozeti(ilk, son)
                assert ozet["etkinlik_toplam"] == (
                    onceki["etkinlik_toplam"] + 1
                )
                assert ozet["etkinlik_iptal_edilmemis"] == (
                    onceki["etkinlik_iptal_edilmemis"]
                )
                assert ozet["kayitli_katilimci_toplami"] == (
                    onceki["kayitli_katilimci_toplami"]
                )

            print("PASS | İptal dönemsel aktif toplamdan çıkarıldı")

            for gun in gunler:
                assert rapor_sayisi(gun) == once[gun], gun

            print("PASS | İptal edilen etkinlik günlük sayılardan çıkarıldı.")

    finally:
        app.dependency_overrides.pop(mevcut_kullanici_id, None)
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
