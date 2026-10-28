"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Transaction ve Veri Butunlugu

Amac:
Audit hatasinda PostgreSQL cihaz guncellemesinin
gercekten geri alindigini dogrulamak.
"""

from contextlib import closing
from unittest.mock import patch

import psycopg2
import pytest

from modeller import CihazGuncelleModeli
from sunucu import VT_AYARLARI, cihaz_guncelle


TEST_ENVANTER_KODU = "TEST-ISSUE-115"


def cihaz_kaydini_getir():
    assert VT_AYARLARI["dbname"] == "crkys_alembic_test"

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            assert cursor.fetchone()[0] == "crkys_alembic_test"

            cursor.execute(
                """
                SELECT cihaz_id, durum
                FROM cihazlar
                WHERE envanter_kodu = %s;
                """,
                (TEST_ENVANTER_KODU,),
            )

            kayit = cursor.fetchone()
            assert kayit is not None, "QA test cihazi bulunamadi."
            return kayit


def test_quality_audit_hatasinda_gercek_postgresql_rollback():
    """Audit hatasinda cihaz durumu kalici olarak degismemelidir."""

    cihaz_id, eski_durum = cihaz_kaydini_getir()

    yeni_durum = (
        "Bakimda"
        if eski_durum != "Bakimda"
        else "Kullanima_Hazir"
    )

    try:
        with patch(
            "sunucu.denetim_kaydi_olustur",
            side_effect=RuntimeError("QA-001 kontrollu audit hatasi"),
        ) as mock_audit:

            with pytest.raises(
                RuntimeError,
                match="QA-001 kontrollu audit hatasi",
            ):
                cihaz_guncelle(
                    cihaz_id=cihaz_id,
                    guncelleme=CihazGuncelleModeli(
                        durum=yeni_durum
                    ),
                    kullanici_id=1,
                )

        mock_audit.assert_called_once()

        _, son_durum = cihaz_kaydini_getir()

        assert son_durum == eski_durum, (
            f"Rollback basarisiz: {eski_durum} -> {son_durum}"
        )

    finally:
        _, mevcut_durum = cihaz_kaydini_getir()

        if mevcut_durum != eski_durum:
            with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE cihazlar
                            SET durum = %s
                            WHERE cihaz_id = %s;
                            """,
                            (eski_durum, cihaz_id),
                        )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
