"""Gerçek PostgreSQL: tarih sütunu indeksleri var ve sorgu planlayıcı denetim sıralamasında indeksi kullanabiliyor."""
import os

import psycopg2
import pytest

from server.sunucu import VT_AYARLARI

BEKLENEN = {
    "ix_denetim_kayitlari_tarih": ("denetim_kayitlari", "olusturulma_tarihi DESC, denetim_id DESC"),
    "ix_randevular_baslangic_zamani": ("randevular", "baslangic_zamani"),
    "ix_ogrenci_faaliyet_takip_faaliyet_tarihi": ("ogrenci_faaliyet_takip", "faaliyet_tarihi"),
}


@pytest.fixture
def imlec():
    assert os.getenv("TKYS_PG_TEST_ONAY") == "EVET"
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"
    conn = psycopg2.connect(**VT_AYARLARI)
    c = conn.cursor()
    try:
        yield c
    finally:
        conn.rollback()
        conn.close()


@pytest.mark.parametrize("ad,beklenen", BEKLENEN.items())
def test_indeks_var(imlec, ad, beklenen):
    tablo, sutunlar = beklenen
    imlec.execute("SELECT tablename, indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname = %s", (ad,))
    satir = imlec.fetchone()
    assert satir is not None, f"{ad} indeksi yok"
    assert satir[0] == tablo and sutunlar in satir[1]


def test_denetim_siralamasi_indeksi_kullanir(imlec):
    """Denetim ekranının sorgusu (en yeni önce, sayfalı) tabloyu sıralamadan indeksten okunabilmeli."""
    imlec.execute("SET LOCAL enable_seqscan = off")
    imlec.execute("EXPLAIN SELECT denetim_id FROM denetim_kayitlari ORDER BY olusturulma_tarihi DESC, denetim_id DESC LIMIT 50")
    plan = "\n".join(satir[0] for satir in imlec.fetchall())
    assert "ix_denetim_kayitlari_tarih" in plan and "Sort" not in plan
