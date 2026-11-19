"""Yalnızca geçici TKYS PostgreSQL test veritabanı için CI verileri."""

import os
from uuid import uuid4

import psycopg2
from server.sunucu import VT_AYARLARI


def main():
    assert os.environ.get("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    assert VT_AYARLARI["host"] in ("127.0.0.1", "localhost")

    etiket = uuid4().hex[:10]

    with psycopg2.connect(**VT_AYARLARI) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "crkys_alembic_test"

            kullanicilar = {}

            for rol in ("ADMIN", "PSIKOLOG"):
                cur.execute(
                    """
                    INSERT INTO kullanicilar
                        (kullanici_adi, parola_hash, rol_id)
                    VALUES (
                        %s, 'x',
                        (SELECT rol_id FROM roller WHERE rol_adi = %s)
                    )
                    RETURNING kullanici_id
                    """,
                    (f"oe_ci_{rol.lower()}_{etiket}", rol),
                )
                kullanicilar[rol] = cur.fetchone()[0]

            personeller = {}

            for rol, kullanici_id in kullanicilar.items():
                cur.execute(
                    """
                    INSERT INTO personel
                        (kullanici_id, personel_kodu)
                    VALUES (%s, %s)
                    RETURNING personel_id
                    """,
                    (kullanici_id, f"OE-{rol[:2]}-{etiket}"),
                )
                personeller[rol] = cur.fetchone()[0]

            odalar = []

            for sira in range(4):
                cur.execute(
                    """
                    INSERT INTO odalar (oda_adi, kapasite)
                    VALUES (%s, 10)
                    RETURNING oda_id
                    """,
                    (f"oe_ci_oda_{sira}_{etiket}",),
                )
                odalar.append(cur.fetchone()[0])

            cur.execute(
                """
                INSERT INTO psikolog_odalar (kullanici_id, oda_id)
                VALUES (%s, %s)
                """,
                (kullanicilar["PSIKOLOG"], odalar[3]),
            )

            cur.execute(
                """
                INSERT INTO danisan_kodlari
                    (danisan_kod_id, olusturan_psikolog_id, yas_grubu)
                VALUES (%s, %s, 'YETISKIN')
                """,
                (f"OE-{etiket}", personeller["PSIKOLOG"]),
            )

            cur.execute(
                """
                INSERT INTO cihazlar
                    (envanter_kodu, cihaz_adi, durum)
                VALUES (%s, %s, 'Kullanima_Hazir')
                """,
                (f"OE-CI-{etiket}", f"CI test cihazi {etiket}"),
            )

    print("PASS | CI test verileri oluşturuldu.")
    print("PASS | 2 kullanıcı, 2 personel, 4 oda hazır.")
    print("PASS | Psikolog-oda ataması, danışan ve cihaz hazır.")


if __name__ == "__main__":
    main()
