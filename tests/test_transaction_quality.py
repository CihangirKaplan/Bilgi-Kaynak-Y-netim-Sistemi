"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Transaction ve Veri Butunlugu

Audit hatasinda PostgreSQL cihaz guncellemesinin
gercekten geri alindigini dogrular.
"""

from contextlib import closing
from unittest.mock import patch
from uuid import uuid4

import psycopg2
import pytest

from modeller import CihazGuncelleModeli
from sunucu import VT_AYARLARI, cihaz_guncelle


def gecici_cihaz_olustur():
    """Yalnizca bu teste ait bir cihaz olustur."""
    envanter_kodu = f"QA001-{uuid4().hex[:16]}"

    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO cihazlar (envanter_kodu, cihaz_adi)
                    VALUES (%s, %s)
                    RETURNING cihaz_id, durum;
                    """,
                    (envanter_kodu, "QA-001 Gecici Test Cihazi"),
                )
                cihaz_id, durum = cursor.fetchone()

            conn.commit()
            return cihaz_id, envanter_kodu, durum

        except Exception:
            conn.rollback()
            raise


def cihaz_durumunu_getir(cihaz_id):
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT durum FROM cihazlar WHERE cihaz_id = %s;",
                (cihaz_id,),
            )
            kayit = cursor.fetchone()

            assert kayit is not None, "QA test cihazi bulunamadi."
            return kayit[0]


def gecici_cihaz_sil(cihaz_id, envanter_kodu):
    """Yalnizca bu testin olusturdugu cihazi sil."""
    with closing(psycopg2.connect(**VT_AYARLARI)) as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM cihazlar
                    WHERE cihaz_id = %s
                      AND envanter_kodu = %s;
                    """,
                    (cihaz_id, envanter_kodu),
                )

                assert cursor.rowcount == 1, (
                    "Gecici QA cihazinin temizlenmesi basarisiz."
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise


def test_quality_audit_hatasinda_gercek_postgresql_rollback():
    """Audit hatasinda cihaz durumu kalici olarak degismemelidir."""

    cihaz_id, envanter_kodu, eski_durum = gecici_cihaz_olustur()

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

        son_durum = cihaz_durumunu_getir(cihaz_id)

        assert son_durum == eski_durum, (
            f"Rollback basarisiz: {eski_durum} -> {son_durum}"
        )

    finally:
        gecici_cihaz_sil(cihaz_id, envanter_kodu)
