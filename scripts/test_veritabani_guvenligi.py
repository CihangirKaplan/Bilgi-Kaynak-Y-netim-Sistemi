"""Test verisi oluşturan scriptler için veritabanı güvenlik kontrolü."""

import os


def test_veritabanini_dogrula():
    db_adi = os.getenv("DB_NAME", "").strip()
    db_host = os.getenv("DB_HOST", "localhost").strip().lower()
    onay = os.getenv("TKYS_PG_TEST_ONAY")

    if db_adi != "crkys_alembic_test":
        raise SystemExit(
            "Güvenlik engeli: Test verileri yalnızca "
            "crkys_alembic_test veritabanına yazılabilir."
        )

    if db_host not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit(
            "Güvenlik engeli: Yalnızca yerel PostgreSQL sunucusuna izin verilir."
        )

    if onay != "EVET":
        raise SystemExit(
            "Güvenlik engeli: TKYS_PG_TEST_ONAY=EVET gerekli."
        )
