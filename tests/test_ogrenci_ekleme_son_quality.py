"""
TKYS - QA-001 / Issue #186
Ogrenci ekleme son guvenlik kontrolleri.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from sunucu import app, mevcut_kullanici_id, ogrenci_ekle


def ogrenci_verisi():
    return {
        "ad_soyad": "QA Test",
        "ogrenci_numarasi": "23100011036",
        "telefon": "05551234567",
        "tur": "GONULLU",
        "bolum": "",
        "sinif": "",
    }


def test_yetkisiz_kullanici_ogrenci_ekleyemez():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    # Rolun ilgili izni yok.
    cursor.fetchone.return_value = (0,)

    app.dependency_overrides[mevcut_kullanici_id] = lambda: 17

    try:
        with patch("sunucu.psycopg2.connect", return_value=conn):
            with TestClient(app) as client:
                cevap = client.post(
                    "/api/ogrenci-ekle",
                    json=ogrenci_verisi(),
                )

        assert cevap.status_code == 403

        assert any(
            "rol_izinleri" in str(c.args[0])
            and c.args[1] == (
                17,
                "FAALIYET_KAYITLARI_DUZENLE",
            )
            for c in cursor.execute.call_args_list
        )

        conn.commit.assert_not_called()

    finally:
        app.dependency_overrides.pop(
            mevcut_kullanici_id, None
        )


def test_ogrenci_audit_hatasinda_rollback():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (501,)

    ogrenci = SimpleNamespace(**{
        k: v for k, v in ogrenci_verisi().items()
        if k in (
            "ad_soyad",
            "ogrenci_numarasi",
            "telefon",
            "tur",
        )
    })

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch(
            "denetim.denetim_kaydi_olustur",
            side_effect=RuntimeError(
                "QA001_AUDIT_ERROR"
            ),
        ) as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            ogrenci_ekle(ogrenci, yetkili_id=1)

    assert hata.value.status_code == 500

    assert "QA001_AUDIT_ERROR" not in str(
        hata.value.detail
    )

    audit.assert_called_once()

    assert audit.call_args.kwargs["mevcut_cursor"] is cursor

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
