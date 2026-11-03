"""
TKYS - QA-001 #186
Gercek PostgreSQL API + Audit Rollback Testi
"""

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import psycopg2
import pytest
from fastapi import HTTPException

import denetim
from sunucu import VT_AYARLARI, faaliyet_birimi_ekle


TEST_DB = "crkys_alembic_test"


def test_quality_api_ve_audit_birlikte_rollback():
    """API islemi basarisizsa ana kayit ve audit geri alinmali."""

    assert VT_AYARLARI["dbname"] == TEST_DB

    ad = "QA001_" + uuid4().hex[:16]
    audit_id = None
    audit_cagrildi = False

    kontrol = psycopg2.connect(**VT_AYARLARI)

    try:
        with kontrol.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            assert cursor.fetchone()[0] == TEST_DB

        kontrol.rollback()

        gercek_audit = denetim.denetim_kaydi_olustur

        def audit_sonrasi_hata(*args, **kwargs):
            nonlocal audit_id, audit_cagrildi

            assert kwargs.get("mevcut_cursor") is not None

            # Gercek audit kaydini ayni transaction'a yaz.
            gercek_audit(*args, **kwargs)

            audit_cagrildi = True
            audit_id = kwargs.get("hedef_kayit_id")

            if audit_id is None and len(args) >= 5:
                audit_id = args[4]

            # Audit yazildiktan sonra hata olustur.
            raise RuntimeError("QA001_TEST_ROLLBACK")

        with patch(
            "denetim.denetim_kaydi_olustur",
            side_effect=audit_sonrasi_hata,
        ):
            with pytest.raises(HTTPException) as hata:
                faaliyet_birimi_ekle(
                    SimpleNamespace(birim_adi=ad),
                    yetkili_id=None,
                )

        assert hata.value.status_code == 500
        assert audit_cagrildi
        assert audit_id is not None

        with kontrol.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM faaliyet_birimleri
                WHERE birim_adi = %s;
                """,
                (ad,),
            )
            assert cursor.fetchone()[0] == 0

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM denetim_kayitlari
                WHERE hedef_tablo = 'faaliyet_birimleri'
                  AND hedef_kayit_id = %s
                  AND olay_turu = 'CREATE';
                """,
                (audit_id,),
            )
            assert cursor.fetchone()[0] == 0

    finally:
        kontrol.rollback()
        kontrol.close()
