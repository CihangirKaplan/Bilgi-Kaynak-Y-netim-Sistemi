"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: RBAC ve Yetkilendirme
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import izin_kontrol


def test_quality_izin_adi_parametreli_sorgulanir():
    """Izin adi SQL metnine eklenmeden parametre olarak aktarilmali."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (0,)

    izin = "CIHAZ_EKLE' OR 1=1 --"

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            izin_kontrol(izin)(kullanici_id=42)

    assert hata.value.status_code == 403

    sorgu, parametreler = cursor.execute.call_args.args

    assert "%s" in sorgu
    assert izin not in sorgu
    assert parametreler == (42, izin)

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_veritabani_hatasinda_baglanti_kapanir():
    """RBAC sorgusu hata verse de kaynaklar kapatilmali."""
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.execute.side_effect = RuntimeError("QA-001 test hatasi")

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(RuntimeError, match="QA-001"):
            izin_kontrol("CIHAZ_EKLE")(kullanici_id=42)

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
