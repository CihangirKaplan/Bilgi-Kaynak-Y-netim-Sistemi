"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186

Test Alani:
HTTP durum kodlarinin korunmasi.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import (
    bakim_guncelle,
    kalibrasyon_guncelle,
    faaliyet_kaydi_guncelle,
)


@pytest.mark.parametrize(
    "fonksiyon",
    [
        bakim_guncelle,
        kalibrasyon_guncelle,
        faaliyet_kaydi_guncelle,
    ],
)
def test_quality_bulunamayan_kayit_404_donmeli(fonksiyon):
    """
    Kayit bulunamadiginda HTTP 404 korunmali.
    Genel Exception blogu bu hatayi 500'e cevirmemeli.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    # SELECT sorgusu kayit bulamiyor.
    cursor.fetchone.return_value = None

    with patch(
        "sunucu.psycopg2.connect",
        return_value=conn,
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(
                999999,
                MagicMock(),
                1,
            )

    assert hata.value.status_code == 404

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "fonksiyon",
    [
        bakim_guncelle,
        kalibrasyon_guncelle,
    ],
)
def test_quality_bos_guncelleme_422_donmeli(fonksiyon):
    """
    Bos guncelleme isteginde HTTP 422 korunmali.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    # Kayit mevcut.
    cursor.fetchone.return_value = (1,)

    model = MagicMock()

    # Guncellenecek alan gonderilmemis.
    model.model_dump.return_value = {}

    with patch(
        "sunucu.psycopg2.connect",
        return_value=conn,
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(
                1,
                model,
                1,
            )

    assert hata.value.status_code == 422

    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_quality_faaliyet_silme_bulunamayan_kayit_404():
    """
    TKYS - QA-001 #186
    Faaliyet kaydi yoksa DELETE islemi HTTP 404 donmeli.
    """

    from sunucu import faaliyet_kaydi_sil

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = None

    with patch(
        "sunucu.psycopg2.connect",
        return_value=conn,
    ):
        with pytest.raises(HTTPException) as hata:
            faaliyet_kaydi_sil(
                takip_id=999999,
                yetkili_id=1,
            )

    assert hata.value.status_code == 404

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
