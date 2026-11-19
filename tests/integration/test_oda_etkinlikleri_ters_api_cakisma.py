"""Etkinlik varken randevu ve cihaz rezervasyonu API çakışmaları."""

import os
from datetime import datetime
from uuid import uuid4

import psycopg2
from fastapi.testclient import TestClient

from server.sunucu import (
    app,
    mevcut_kullanici_id,
    VT_AYARLARI,
    CIHAZ_ODALARI_SORGUSU,
)
from server.oda_etkinlikleri_kurallari import oda_cakismasi_bul


def test_etkinlik_varken_randevu_ve_cihaz_reddedilir():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    conn = psycopg2.connect(**VT_AYARLARI)

    etkinlik_ids = []
    randevu_ids = []
    rezervasyon_ids = []
    cihaz_id = None

    def yetkili_kullanici(cur, izin):
        cur.execute("""
            SELECT k.kullanici_id
            FROM kullanicilar k
            JOIN rol_izinleri ri ON ri.rol_id = k.rol_id
            JOIN izinler i ON i.izin_id = ri.izin_id
            WHERE k.aktif_mi = TRUE
              AND ri.izin_var = 1
              AND i.izin_adi = %s
            ORDER BY k.kullanici_id
            LIMIT 1
        """, (izin,))
        kayit = cur.fetchone()
        assert kayit, f"Testte {izin} izinli aktif kullanıcı bulunamadı."
        return kayit[0]

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            # Gerçek psikolog-oda atamasını kullan.
            cur.execute("""
                SELECT p.personel_id, o.oda_id
                FROM psikolog_odalar po
                JOIN personel p ON p.kullanici_id = po.kullanici_id
                JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
                JOIN roller r ON r.rol_id = k.rol_id
                JOIN odalar o ON o.oda_id = po.oda_id
                WHERE p.aktif_mi = TRUE
                  AND k.aktif_mi = TRUE
                  AND o.aktif_mi = TRUE
                  AND r.rol_adi ILIKE 'Psikolog'
                ORDER BY p.personel_id, o.oda_id
                LIMIT 1
            """)
            psikolog = cur.fetchone()
            assert psikolog, "Uygun psikolog-oda ataması bulunamadı."
            psikolog_id, randevu_oda_id = psikolog

            # Cihaz rezervasyonuna izin verilen gerçek bir oda.
            cur.execute("""
                SELECT d.oda_id
                FROM (
            """ + CIHAZ_ODALARI_SORGUSU + """
                ) d
                ORDER BY d.oda_id
                LIMIT 1
            """)
            cihaz_odasi = cur.fetchone()
            assert cihaz_odasi, "Cihaz kullanımına uygun oda yok."
            cihaz_oda_id = cihaz_odasi[0]

            cur.execute(
                """
                INSERT INTO cihazlar
                    (envanter_kodu, cihaz_adi, durum)
                VALUES (%s, %s, 'Kullanima_Hazir')
                RETURNING cihaz_id
                """,
                (
                    f"OE-TERS-{uuid4().hex[:12]}",
                    "Oda etkinligi cakisma test cihazi",
                ),
            )
            cihaz_id = cur.fetchone()[0]

            cur.execute("""
                SELECT danisan_kod_id FROM danisan_kodlari
                WHERE aktif_mi = TRUE AND yas_grubu = 'YETISKIN'
                ORDER BY danisan_kod_id LIMIT 1
            """)
            danisan = cur.fetchone()
            assert danisan, "Aktif yetişkin danışan kodu yok."

            cur.execute("""
                SELECT personel_id FROM personel
                WHERE aktif_mi = TRUE
                ORDER BY personel_id LIMIT 1
            """)
            personel = cur.fetchone()
            assert personel, "Aktif personel yok."

            randevu_kullanici = yetkili_kullanici(
                cur, "RANDEVU_OLUSTUR"
            )
            cihaz_kullanici = yetkili_kullanici(
                cur, "CIHAZ_REZERVASYON"
            )

            randevu_bas = datetime(2048, 6, 15, 10)
            randevu_bit = datetime(2048, 6, 15, 11)

            cihaz_bas = datetime(2048, 6, 15, 12)
            cihaz_bit = datetime(2048, 6, 15, 13)

            for oda_id, bas, bit in (
                (randevu_oda_id, randevu_bas, randevu_bit),
                (cihaz_oda_id, cihaz_bas, cihaz_bit),
            ):
                assert oda_cakismasi_bul(
                    cur, oda_id, bas, bit
                ) is None, "Test aralığı zaten dolu."

            isaret = uuid4().hex[:12]

            for sira, (oda_id, bas, bit) in enumerate((
                (randevu_oda_id, randevu_bas, randevu_bit),
                (cihaz_oda_id, cihaz_bas, cihaz_bit),
            ), 1):
                cur.execute("""
                    INSERT INTO oda_etkinlikleri
                        (oda_id, organize_eden_personel_id,
                         etkinlik_adi, katilimci_sayisi,
                         baslangic_zamani, bitis_zamani)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING etkinlik_id
                """, (
                    oda_id, personel[0],
                    f"TKYS_TERS_API_{isaret}_{sira}",
                    None, bas, bit,
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

        def api_istegi(kullanici_id, yol, veri):
            app.dependency_overrides[mevcut_kullanici_id] = (
                lambda: kullanici_id
            )
            try:
                with TestClient(app) as client:
                    return client.post(yol, json=veri)
            finally:
                app.dependency_overrides.pop(
                    mevcut_kullanici_id, None
                )

        print("\n=== ETKİNLİK → RANDEVU ===")

        randevu_yanit = api_istegi(
            randevu_kullanici,
            "/api/randevular",
            {
                "danisan_kod_id": danisan[0],
                "psikolog_id": psikolog_id,
                "oda_id": randevu_oda_id,
                "baslangic_zamani": randevu_bas.isoformat(),
                "bitis_zamani": randevu_bit.isoformat(),
                "gorusme_tipi": "YUZ_YUZE",
                "terapi_turu": "BIREYSEL_TERAPI",
            },
        )

        if randevu_yanit.status_code == 201:
            randevu_ids.append(
                randevu_yanit.json()["randevu_id"]
            )

        print(
            "HTTP:", randevu_yanit.status_code,
            randevu_yanit.text[:250],
        )

        assert randevu_yanit.status_code == 409, (
            randevu_yanit.text
        )
        assert "etkinlik" in randevu_yanit.text.lower()
        print("PASS | Etkinlik üzerine randevu oluşturulamadı.")

        print("\n=== ETKİNLİK → CİHAZ REZERVASYONU ===")

        cihaz_yanit = api_istegi(
            cihaz_kullanici,
            "/api/rezervasyonlar",
            {
                "cihaz_id": cihaz_id,
                "kullanilacak_oda_id": cihaz_oda_id,
                "baslangic_zamani": cihaz_bas.isoformat(),
                "bitis_zamani": cihaz_bit.isoformat(),
            },
        )

        if cihaz_yanit.status_code == 201:
            veri = cihaz_yanit.json()
            if "rezervasyon_id" in veri:
                rezervasyon_ids.append(veri["rezervasyon_id"])

        print(
            "HTTP:", cihaz_yanit.status_code,
            cihaz_yanit.text[:250],
        )

        assert cihaz_yanit.status_code == 409, (
            cihaz_yanit.text
        )
        assert "etkinlik" in cihaz_yanit.text.lower()
        print("PASS | Etkinlik üzerine cihaz rezervasyonu oluşturulamadı.")

    finally:
        app.dependency_overrides.pop(
            mevcut_kullanici_id, None
        )
        conn.rollback()

        try:
            with conn.cursor() as cur:
                for tablo, ids, pk in (
                    ("randevular", randevu_ids, "randevu_id"),
                    ("cihaz_rezervasyonlari", rezervasyon_ids, "rezervasyon_id"),
                    ("oda_etkinlikleri", etkinlik_ids, "etkinlik_id"),
                ):
                    if not ids:
                        continue

                    cur.execute("""
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = %s
                          AND hedef_kayit_id = ANY(%s)
                    """, (tablo, ids))

                    # Tablo ve sütun isimleri sabit kod listesinden gelir.
                    cur.execute(
                        f"DELETE FROM {tablo} WHERE {pk} = ANY(%s)",
                        (ids,),
                    )

            if cihaz_id is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM denetim_kayitlari "
                        "WHERE hedef_tablo = 'cihazlar' "
                        "AND hedef_kayit_id = %s",
                        (cihaz_id,),
                    )
                    cur.execute(
                        "DELETE FROM cihazlar WHERE cihaz_id = %s",
                        (cihaz_id,),
                    )

            conn.commit()
            print("\nPASS | Geçici test kayıtları temizlendi.")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
