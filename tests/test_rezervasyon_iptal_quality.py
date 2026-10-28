"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Cihaz Rezervasyonu Iptal ve Veri Butunlugu
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import rezervasyon_iptal


def test_quality_bulunamayan_rezervasyon_iptal_edilemez():
    """QA-001 #186: Olmayan rezervasyon HTTP 404 dondurmeli."""

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = None

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            rezervasyon_iptal(
                rezervasyon_id=999,
                kullanici_id=1,
            )

    assert hata.value.status_code == 404

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_iptal_edilmis_rezervasyon_tekrar_iptal_edilemez():
    """
    QA-001 #186:
    Zaten iptal edilmis bir rezervasyonun
    tekrar iptal edilmesi engellenmeli.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    def sorgu_simulasyonu(sql, *args, **kwargs):
        # Simule edilen rezervasyon zaten iptal edilmis.
        # Yalnizca aktif rezervasyonlari guncelleyen
        # sorgu bu kaydi bulamamali.
        if "UPDATE cihaz_rezervasyonlari" in sql:
            if "iptal_edildi_mi = FALSE" in sql:
                cursor.fetchone.return_value = None
            else:
                cursor.fetchone.return_value = (10,)

    cursor.execute.side_effect = sorgu_simulasyonu

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.denetim_kaydi_olustur") as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            rezervasyon_iptal(
                rezervasyon_id=10,
                kullanici_id=1,
            )

    assert hata.value.status_code == 404

    conn.commit.assert_not_called()
    audit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_aktif_rezervasyon_iptal_edilebilir():
    """QA-001 #186: Aktif rezervasyon basariyla iptal edilmeli."""

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (10,)

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.denetim_kaydi_olustur") as audit,
    ):
        sonuc = rezervasyon_iptal(
            rezervasyon_id=10,
            kullanici_id=1,
        )

    assert sonuc["durum"] == "basarili"

    conn.commit.assert_called_once()
    audit.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_rezervasyon_iptal_audit_ayni_transaction():
    """
    TKYS - Quality Assurance (QA-001)
    GitHub Issue: #186
    Test Alani: Audit Transaction Butunlugu

    Rezervasyon iptali ve audit kaydi
    ayni veritabani cursor'unu kullanmali.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (10,)

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.denetim_kaydi_olustur") as audit,
    ):
        sonuc = rezervasyon_iptal(
            rezervasyon_id=10,
            kullanici_id=1,
        )

    assert sonuc["durum"] == "basarili"

    audit.assert_called_once()

    # Audit kaydi ayni transaction'a dahil edilmeli.
    assert audit.call_args.kwargs["mevcut_cursor"] is cursor

    conn.commit.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_rezervasyon_iptal_audit_hatasinda_rollback():
    """
    TKYS - Quality Assurance (QA-001)
    GitHub Issue: #186
    Test Alani: Audit hatasinda Transaction Rollback
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (10,)

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch(
            "sunucu.denetim_kaydi_olustur",
            side_effect=RuntimeError("QA-001 audit hatasi"),
        ) as audit,
    ):
        with pytest.raises(RuntimeError, match="QA-001 audit hatasi"):
            rezervasyon_iptal(
                rezervasyon_id=10,
                kullanici_id=1,
            )

    # Audit ayni cursor ile yapilmaya calisilmali.
    assert audit.call_args.kwargs["mevcut_cursor"] is cursor

    # Audit basarisizsa rezervasyon iptali de kaydedilmemeli.
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
