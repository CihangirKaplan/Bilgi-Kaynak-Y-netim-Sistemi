"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Randevu Deadlock Hata Yonetimi

Amac:
Tekrarlanan PostgreSQL deadlock hatalarinin
kontrollu bicimde ele alinmasini dogrulamak.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from fastapi import HTTPException

from sunucu import randevu_olustur


def test_quality_randevu_deadlock_sonrasi_503():
    """Kalici deadlock hatasi kullaniciya HTTP 503 olarak bildirilmeli."""

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.execute.side_effect = psycopg2.errors.DeadlockDetected(
        "QA-001 kontrollu deadlock"
    )

    baslangic = datetime(2026, 12, 1, 10, 0)

    randevu = SimpleNamespace(
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic + timedelta(hours=1),
    )

    with patch("sunucu.psycopg2.connect", return_value=conn) as mock_connect:
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(
                randevu=randevu,
                kullanici_id=1,
            )

    assert hata.value.status_code == 503
    assert mock_connect.call_count == 3
    assert conn.rollback.call_count == 3


    conn.rollback.assert_called()
    conn.commit.assert_not_called()
    cursor.close.assert_called()
    conn.close.assert_called()


def test_quality_randevu_deadlock_sonrasi_basarili_yeniden_deneme():
    """
    TKYS - Quality Assurance (QA-001)
    GitHub Issue: #186

    Ilk denemede deadlock, ikinci denemede basarili randevu.
    """

    ilk_baglanti = MagicMock()
    ikinci_baglanti = MagicMock()

    ilk_cursor = ilk_baglanti.cursor.return_value
    ikinci_cursor = ikinci_baglanti.cursor.return_value

    # Ilk baglanti deadlock hatasi uretsin.
    ilk_cursor.execute.side_effect = (
        psycopg2.errors.DeadlockDetected(
            "QA-001 kontrollu ilk deadlock"
        )
    )

    # Ikinci baglanti normal sorgu sonuclari dondursun.
    ikinci_cursor.fetchone.side_effect = [
        ("ADMIN",),  # Kullanici rolu
        (1,),        # Aktif psikolog
        (1,),        # Aktif oda
        None,        # Randevu cakismasi yok
        (123,),      # Olusturulan randevu ID
    ]

    baslangic = datetime(2026, 12, 1, 10, 0)

    randevu = SimpleNamespace(
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic + timedelta(hours=1),
        psikolog_id=1,
        oda_id=1,
    )

    with (
        patch(
            "sunucu.psycopg2.connect",
            side_effect=[ilk_baglanti, ikinci_baglanti],
        ) as mock_connect,
        patch(
            "sunucu.otomatik_danisan_kodu_uret",
            return_value="DAN-2026-9999",
        ),
        patch("time.sleep") as mock_sleep,
    ):
        sonuc = randevu_olustur(
            randevu=randevu,
            kullanici_id=1,
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["randevu_id"] == 123

    # Sadece iki kez baglanti acilmali.
    assert mock_connect.call_count == 2

    # Basarisiz ilk deneme geri alinmali.
    ilk_baglanti.rollback.assert_called_once()
    ilk_baglanti.commit.assert_not_called()

    # Ikinci deneme basariyla kaydedilmeli.
    ikinci_baglanti.commit.assert_called_once()
    ikinci_baglanti.rollback.assert_not_called()

    # Deadlock sonrasi yeniden deneme araligi.
    mock_sleep.assert_called_once()

    # Iki baglanti da kapatilmali.
    ilk_baglanti.close.assert_called_once()
    ikinci_baglanti.close.assert_called_once()
