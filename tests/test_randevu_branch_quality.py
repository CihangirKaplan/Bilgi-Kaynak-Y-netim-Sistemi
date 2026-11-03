"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu API Branch Coverage

Amac:
Randevu olusturma fonksiyonundaki kritik
yetkilendirme ve cakisma karar yollarini test etmek.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import randevu_olustur


def ornek_randevu(psikolog_id=1, oda_id=1):
    baslangic = datetime(2026, 12, 1, 10, 0)

    return SimpleNamespace(
        psikolog_id=psikolog_id,
        oda_id=oda_id,
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic + timedelta(hours=1),
    )


def test_quality_psikolog_baskasi_adina_randevu_olusturamaz():
    """
    QA-001 #186:
    Psikolog sadece kendi adina randevu olusturabilir.
    Beklenen: HTTP 403.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        ("PSIKOLOG",),
        (2,),
    ]

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch(
            "sunucu.otomatik_danisan_kodu_uret",
            return_value="DAN-2026-9999",
        ),
    ):
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(
                randevu=ornek_randevu(psikolog_id=1),
                kullanici_id=10,
            )

    assert hata.value.status_code == 403

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()


def test_quality_cakisan_randevu_http_409():
    """
    QA-001 #186:
    Cakisan randevu uygulama seviyesinde engellenmeli.
    Beklenen: HTTP 409.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        ("ADMIN",),   # Kullanici rolu
        (1,),         # Psikolog aktif
        (1,),         # Oda aktif
        (99,),        # Cakisan randevu bulundu
    ]

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch(
            "sunucu.otomatik_danisan_kodu_uret",
            return_value="DAN-2026-9999",
        ),
    ):
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(
                randevu=ornek_randevu(),
                kullanici_id=10,
            )

    assert hata.value.status_code == 409

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()
