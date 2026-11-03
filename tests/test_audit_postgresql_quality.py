"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186

Gercek PostgreSQL Audit Transaction Testleri

Yalnizca crkys_alembic_test veritabaninda calisir.
"""

from uuid import uuid4

import psycopg2

from denetim import denetim_kaydi_olustur
from sunucu import VT_AYARLARI


TEST_DB = "crkys_alembic_test"


def guvenli_baglanti():
    """Yalnizca test veritabanina baglan."""

    assert VT_AYARLARI["dbname"] == TEST_DB, (
        "QA-001: Test veritabani disinda islem yasak."
    )

    conn = psycopg2.connect(**VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            aktif_db = cursor.fetchone()[0]

        assert aktif_db == TEST_DB, (
            f"Yanlis veritabani: {aktif_db}"
        )

        conn.rollback()
        return conn

    except Exception:
        conn.close()
        raise


def kayit_sayisi(cursor, hedef):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM denetim_kayitlari
        WHERE hedef_tablo = %s
          AND hedef_kayit_id = 1;
        """,
        (hedef,),
    )

    return cursor.fetchone()[0]


def test_quality_gercek_postgresql_audit_rollback():
    """
    Audit kaydi ayni transaction icinde
    rollback ile geri alinabilmeli.
    """

    hedef = "qa001_" + uuid4().hex[:16]

    conn1 = None
    conn2 = None

    try:
        conn1 = guvenli_baglanti()
        conn2 = guvenli_baglanti()

        with conn1.cursor() as cursor1, conn2.cursor() as cursor2:

            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="CREATE",
                hedef_tablo=hedef,
                hedef_kayit_id=1,
                mevcut_cursor=cursor1,
            )

            # Ayni transaction kaydi gormeli.
            assert kayit_sayisi(cursor1, hedef) == 1

            # Commit edilmedigi icin diger baglanti gormemeli.
            assert kayit_sayisi(cursor2, hedef) == 0

            conn1.rollback()

            # Rollback sonrasi kayit bulunmamali.
            assert kayit_sayisi(cursor1, hedef) == 0
            assert kayit_sayisi(cursor2, hedef) == 0

    finally:
        if conn1 is not None:
            conn1.rollback()
            conn1.close()

        if conn2 is not None:
            conn2.rollback()
            conn2.close()


def test_quality_gercek_postgresql_audit_commit():
    """
    Commit edilen audit kaydi baska baglantidan
    gorulebilmeli.

    Test kaydi sonunda temizlenir.
    """

    hedef = "qa001_" + uuid4().hex[:16]

    conn1 = None
    conn2 = None

    try:
        conn1 = guvenli_baglanti()
        conn2 = guvenli_baglanti()

        with conn1.cursor() as cursor1, conn2.cursor() as cursor2:

            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="CREATE",
                hedef_tablo=hedef,
                hedef_kayit_id=1,
                mevcut_cursor=cursor1,
            )

            # Commit oncesi diger baglanti gorememeli.
            assert kayit_sayisi(cursor2, hedef) == 0

            conn1.commit()

            # Commit sonrasi diger baglanti gorebilmeli.
            assert kayit_sayisi(cursor2, hedef) == 1

    finally:
        if conn2 is not None:
            conn2.rollback()
            conn2.close()

        if conn1 is not None:
            try:
                conn1.rollback()

                # Yalnizca bu teste ait benzersiz kaydi sil.
                with conn1.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM denetim_kayitlari
                        WHERE hedef_tablo = %s
                          AND hedef_kayit_id = 1;
                        """,
                        (hedef,),
                    )

                conn1.commit()

            except Exception:
                conn1.rollback()
                raise

            finally:
                conn1.close()
