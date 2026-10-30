"""
TKYS QA-001 #186
Gercek PostgreSQL entegrasyon testleri icin merkezi guvenlik kontrolu.
"""

import os

import psycopg2
import pytest


TEST_DB = "crkys_alembic_test"

IZINLI_HOSTLAR = {
    "localhost",
    "127.0.0.1",
    "::1",
    "",
}

POSTGRESQL_TEST_DOSYALARI = {
    "test_transaction_quality.py",
    "test_randevu_transaction_quality.py",
    "test_randevu_eszamanlilik_quality.py",
    "test_audit_postgresql_quality.py",
    "test_api_audit_rollback_quality.py",
}


@pytest.fixture(autouse=True)
def postgresql_test_guvenligi(request, monkeypatch):
    """
    Gercek PostgreSQL testlerinde yanlis veritabanina
    baglanilmasini engeller.
    """

    dosya_adi = request.node.path.name
    test_adi = request.node.name

    gercek_pg_testi = (
        dosya_adi in POSTGRESQL_TEST_DOSYALARI
        or (
            dosya_adi == "test_cihaz_rezervasyon_eszamanlilik.py"
            and test_adi == "test_gercek_eszamanli_cihaz_rezervasyonu"
        )
    )

    if not gercek_pg_testi:
        return

    # Testlerin yanlislikla calistirilmasini engelle.
    if os.getenv("TKYS_PG_TEST_ONAY") != "EVET":
        pytest.fail(
            "Gercek PostgreSQL testleri kapali. "
            "Calistirmak icin TKYS_PG_TEST_ONAY=EVET gerekli."
        )

    from sunucu import VT_AYARLARI

    db_adi = VT_AYARLARI.get("dbname")
    db_host = str(VT_AYARLARI.get("host") or "").lower().strip()

    if db_adi != TEST_DB:
        pytest.fail(
            "Guvenlik engeli: Yalnizca "
            f"{TEST_DB} veritabaninda test yapilabilir."
        )

    if db_host not in IZINLI_HOSTLAR:
        pytest.fail(
            "Guvenlik engeli: Gercek PostgreSQL testleri "
            "yalnizca yerel sunucuda calisabilir."
        )

    orijinal_connect = psycopg2.connect

    def guvenli_connect(*args, **kwargs):
        # Bu testlerde baglanti parametreleri acik verilmelidir.
        if args or kwargs.get("dsn"):
            raise RuntimeError(
                "Guvenlik engeli: DSN ile baglantiya izin verilmiyor."
            )

        hedef_db = kwargs.get("dbname")
        hedef_host = str(kwargs.get("host") or "").lower().strip()

        if hedef_db != TEST_DB:
            raise RuntimeError(
                "Guvenlik engeli: Yanlis veritabani baglantisi."
            )

        if hedef_host not in IZINLI_HOSTLAR:
            raise RuntimeError(
                "Guvenlik engeli: Yerel olmayan PostgreSQL sunucusu."
            )

        conn = orijinal_connect(**kwargs)

        try:
            # Gercekte baglanilan veritabanini dogrula.
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database();")
                aktif_db = cursor.fetchone()[0]

            if aktif_db != TEST_DB:
                raise RuntimeError(
                    "Guvenlik engeli: Beklenmeyen aktif veritabani."
                )

            conn.rollback()
            return conn

        except Exception:
            conn.close()
            raise

    monkeypatch.setattr(psycopg2, "connect", guvenli_connect)
