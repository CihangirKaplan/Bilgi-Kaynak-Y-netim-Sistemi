"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu Transaction ve Veri Butunlugu

Amac:
PostgreSQL EXCLUDE kisitlarinin gercek veritabani
uzerinde randevu cakismalarini engelledigini dogrulamak.
"""

from contextlib import closing
from datetime import datetime, timedelta
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.errors import ExclusionViolation

from sunucu import VT_AYARLARI


def test_quality_randevu_cakisma_kisitlari_postgresql():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    etiket = uuid4().hex[:12]

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as cursor:

                cursor.execute("SELECT current_database();")
                assert cursor.fetchone()[0] == "crkys_alembic_test"

                cursor.execute("SET LOCAL lock_timeout = '3s';")
                cursor.execute("SET LOCAL statement_timeout = '10s';")

                # Psikolog rolunu bul veya transaction icinde olustur.
                cursor.execute(
                    "SELECT rol_id FROM roller WHERE rol_adi = %s;",
                    ("PSIKOLOG",),
                )
                kayit = cursor.fetchone()

                if kayit:
                    rol_id = kayit[0]
                else:
                    cursor.execute(
                        """
                        INSERT INTO roller (rol_adi)
                        VALUES (%s)
                        RETURNING rol_id;
                        """,
                        ("PSIKOLOG",),
                    )
                    rol_id = cursor.fetchone()[0]

                # Iki gecici oda olustur.
                oda_ids = []

                for i in (1, 2):
                    cursor.execute(
                        """
                        INSERT INTO odalar (oda_adi, kapasite)
                        VALUES (%s, %s)
                        RETURNING oda_id;
                        """,
                        (f"QA001-{etiket}-ODA-{i}", 2),
                    )
                    oda_ids.append(cursor.fetchone()[0])

                # Iki gecici psikolog/personel olustur.
                psikolog_ids = []

                for i in (1, 2):
                    cursor.execute(
                        """
                        INSERT INTO kullanicilar
                            (kullanici_adi, parola_hash, rol_id)
                        VALUES (%s, %s, %s)
                        RETURNING kullanici_id;
                        """,
                        (
                            f"qa001_{etiket}_p{i}",
                            "qa001-test-kaydi",
                            rol_id,
                        ),
                    )
                    kullanici_id = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT INTO personel
                            (kullanici_id, personel_kodu)
                        VALUES (%s, %s)
                        RETURNING personel_id;
                        """,
                        (
                            kullanici_id,
                            f"QA001-{etiket}-{i}",
                        ),
                    )
                    psikolog_ids.append(cursor.fetchone()[0])

                # Gecici danisan kodu olustur.
                danisan_kodu = f"QA001-{etiket}"

                cursor.execute(
                    """
                    INSERT INTO danisan_kodlari
                        (danisan_kod_id, ucretli_mi)
                    VALUES (%s, TRUE);
                    """,
                    (danisan_kodu,),
                )

                oda1, oda2 = oda_ids
                psikolog1, psikolog2 = psikolog_ids

                baslangic = (
                    datetime.now().replace(microsecond=0)
                    + timedelta(days=60)
                )
                bitis = baslangic + timedelta(hours=1)

                def randevu_ekle(psikolog, oda, ilk, son):
                    cursor.execute(
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
                            psikolog,
                            oda,
                            ilk,
                            son,
                        ),
                    )

                # 1. Ilk randevu basarili olmali.
                randevu_ekle(
                    psikolog1,
                    oda1,
                    baslangic,
                    bitis,
                )

                cakis_baslangic = baslangic + timedelta(minutes=30)
                cakis_bitis = bitis + timedelta(minutes=30)

                # 2 ve 3. Iki farkli cakisma senaryosu.
                senaryolar = [
                    (
                        psikolog2,
                        oda1,
                        "oda_randevu_cakisma",
                    ),
                    (
                        psikolog1,
                        oda2,
                        "psikolog_randevu_cakisma",
                    ),
                ]

                for psikolog, oda, beklenen_kisit in senaryolar:
                    cursor.execute("SAVEPOINT qa001_cakisma;")

                    try:
                        with pytest.raises(ExclusionViolation) as hata:
                            randevu_ekle(
                                psikolog,
                                oda,
                                cakis_baslangic,
                                cakis_bitis,
                            )

                        assert (
                            hata.value.diag.constraint_name
                            == beklenen_kisit
                        )

                    finally:
                        cursor.execute(
                            "ROLLBACK TO SAVEPOINT qa001_cakisma;"
                        )
                        cursor.execute(
                            "RELEASE SAVEPOINT qa001_cakisma;"
                        )

                # 4. Bitisik saatlerde randevu olusturulabilmeli.
                randevu_ekle(
                    psikolog1,
                    oda1,
                    bitis,
                    bitis + timedelta(hours=1),
                )

                # Sadece iki basarili randevu bulunmali.
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM randevular
                    WHERE danisan_kod_id = %s;
                    """,
                    (danisan_kodu,),
                )

                assert cursor.fetchone()[0] == 2

        finally:
            # Basarili veya basarisiz her durumda
            # gecici verileri geri al.
            conn.rollback()
