"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Gercek PostgreSQL Randevu Eszamanliligi
"""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta
from threading import Barrier
from uuid import uuid4

import psycopg2
from psycopg2.errors import ExclusionViolation

from sunucu import VT_AYARLARI


def test_quality_ayni_oda_eszamanli_randevu_engellenir():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    etiket = uuid4().hex[:10]
    danisan_kodu = f"QA001-{etiket}"

    rol_id = None
    oda_id = None
    kullanici_ids = []
    psikolog_ids = []
    hazirlik_kaydedildi = False

    baslangic = datetime.now().replace(
        microsecond=0
    ) + timedelta(days=90)
    bitis = baslangic + timedelta(hours=1)

    try:
        # Yalnizca teste ait gecici kayitlar olustur.
        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT current_database();")
                    assert cur.fetchone()[0] == "crkys_alembic_test"

                    cur.execute(
                        "INSERT INTO roller (rol_adi) VALUES (%s) RETURNING rol_id;",
                        (f"QA001_{etiket}",),
                    )
                    rol_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO odalar (oda_adi)
                        VALUES (%s) RETURNING oda_id;
                        """,
                        (f"QA001-{etiket}-ODA",),
                    )
                    oda_id = cur.fetchone()[0]

                    cur.execute(
                        """
                        INSERT INTO danisan_kodlari (danisan_kod_id)
                        VALUES (%s);
                        """,
                        (danisan_kodu,),
                    )

                    for i in (1, 2):
                        cur.execute(
                            """
                            INSERT INTO kullanicilar
                                (kullanici_adi, parola_hash, rol_id)
                            VALUES (%s, %s, %s)
                            RETURNING kullanici_id;
                            """,
                            (
                                f"qa001_{etiket}_{i}",
                                "qa001-gecici-test-hash",
                                rol_id,
                            ),
                        )
                        kullanici_id = cur.fetchone()[0]
                        kullanici_ids.append(kullanici_id)

                        cur.execute(
                            """
                            INSERT INTO personel
                                (kullanici_id, personel_kodu)
                            VALUES (%s, %s)
                            RETURNING personel_id;
                            """,
                            (
                                kullanici_id,
                                f"QA{etiket}{i}",
                            ),
                        )
                        psikolog_ids.append(cur.fetchone()[0])

                conn.commit()
                hazirlik_kaydedildi = True
            except Exception:
                conn.rollback()
                raise

        barrier = Barrier(2)

        def randevu_dene(psikolog_id):
            with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT current_database();")
                        assert cur.fetchone()[0] == "crkys_alembic_test"

                        cur.execute("SET LOCAL statement_timeout = '10s';")

                        # Iki baglanti ayni anda eklemeyi denesin.
                        barrier.wait(timeout=10)

                        cur.execute(
                            """
                            INSERT INTO randevular
                                (
                                    danisan_kod_id,
                                    psikolog_id,
                                    oda_id,
                                    baslangic_zamani,
                                    bitis_zamani,
                                    durum
                                )
                            VALUES (%s, %s, %s, %s, %s, 'PLANLANDI');
                            """,
                            (
                                danisan_kodu,
                                psikolog_id,
                                oda_id,
                                baslangic,
                                bitis,
                            ),
                        )

                    conn.commit()
                    return ("BASARILI", None)

                except ExclusionViolation as hata:
                    conn.rollback()
                    return ("CAKISMA", hata.diag.constraint_name)

                except psycopg2.errors.DeadlockDetected:
                    conn.rollback()
                    return ("DEADLOCK", None)

                except Exception:
                    conn.rollback()
                    raise

        with ThreadPoolExecutor(max_workers=2) as havuz:
            sonuclar = list(havuz.map(randevu_dene, psikolog_ids))

        assert sum(
            durum == "BASARILI" for durum, _ in sonuclar
        ) == 1

        assert sum(
            durum in ("CAKISMA", "DEADLOCK")
            for durum, _ in sonuclar
        ) == 1

        assert all(
            kisit == "oda_randevu_cakisma"
            for durum, kisit in sonuclar
            if durum == "CAKISMA"
        )

        with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM randevular
                    WHERE danisan_kod_id = %s;
                    """,
                    (danisan_kodu,),
                )
                assert cur.fetchone()[0] == 1

    finally:
        # Hazirlik kaydedildiyse sadece bu teste ait
        # kayitlari, FK iliskilerine uygun sirayla sil.
        if hazirlik_kaydedildi:
            with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT current_database();")
                        assert cur.fetchone()[0] == "crkys_alembic_test"

                        cur.execute(
                            "DELETE FROM randevular WHERE danisan_kod_id = %s;",
                            (danisan_kodu,),
                        )
                        cur.execute(
                            "DELETE FROM danisan_kodlari WHERE danisan_kod_id = %s;",
                            (danisan_kodu,),
                        )
                        cur.execute(
                            "DELETE FROM personel WHERE personel_id = ANY(%s);",
                            (psikolog_ids,),
                        )
                        cur.execute(
                            "DELETE FROM kullanicilar WHERE kullanici_id = ANY(%s);",
                            (kullanici_ids,),
                        )
                        cur.execute(
                            "DELETE FROM odalar WHERE oda_id = %s;",
                            (oda_id,),
                        )
                        cur.execute(
                            "DELETE FROM roller WHERE rol_id = %s;",
                            (rol_id,),
                        )

                    conn.commit()

                except Exception:
                    conn.rollback()
                    raise
