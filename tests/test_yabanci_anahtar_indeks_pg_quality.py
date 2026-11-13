"""Gerçek PostgreSQL: her yabancı anahtar sütununun başında bir indeks olmalı.

Bu test CI'daki "PostgreSQL Entegrasyon Testleri" işinde (alembic upgrade head sonrası) çalışır. PostgreSQL yabancı
anahtar sütunu için kendiliğinden indeks oluşturmaz; indeks yoksa o sütuna göre arama ve bağlı kayıt denetimi
tablo büyüdükçe tüm tabloyu tarar. Biri indeksi olmayan yeni bir yabancı anahtar eklerse PR kırmızı olur.
"""

import os

import psycopg2

from sunucu import VT_AYARLARI

INDEKSSIZ_YABANCI_ANAHTARLAR = """
    SELECT c.conrelid::regclass::text, c.conname
    FROM pg_constraint c
    WHERE c.contype = 'f'
      AND NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = c.conrelid
          AND (i.indkey::int2[])[0:cardinality(c.conkey)-1] = c.conkey
      )
    ORDER BY 1, 2
"""


def _dogru_veritabani(cursor):
    # Yanlış veritabanında çalışmayı kesinlikle engelle.
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    cursor.execute("SELECT current_database()")
    assert cursor.fetchone()[0] == "crkys_alembic_test"


def test_her_yabanci_anahtarin_indeksi_var():
    conn = psycopg2.connect(**VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            _dogru_veritabani(cursor)
            cursor.execute("SELECT COUNT(*) FROM pg_constraint WHERE contype = 'f'")
            assert cursor.fetchone()[0] > 20, "Yabancı anahtarlar okunamadı; sorgu bozulmuş olabilir."

            cursor.execute(INDEKSSIZ_YABANCI_ANAHTARLAR)
            eksikler = [f"{tablo}.{kisit}" for tablo, kisit in cursor.fetchall()]
            assert not eksikler, (
                "İndeksi olmayan yabancı anahtarlar var: "
                + ", ".join(eksikler)
                + ". Yeni bir migrasyonla CREATE INDEX ekleyin."
            )
    finally:
        conn.close()
