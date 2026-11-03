from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg2
import pytest
from fastapi import HTTPException

from sunucu import ogrenci_ekle


def ogrenci_modeli():
    return SimpleNamespace(
        ad_soyad="QA Test",
        ogrenci_numarasi="QA001",
        telefon="05000000000",
        tur="Gönüllü",
    )


def test_ogrenci_ekle_benzersizlik_hatasi_400():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.execute.side_effect = (
        psycopg2.errors.UniqueViolation("QA001_TEST")
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            ogrenci_ekle(ogrenci_modeli(), 1)

    assert hata.value.status_code == 400
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()


def test_ogrenci_ekle_veritabani_hatasi_500():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.execute.side_effect = RuntimeError(
        "QA001_SECRET_DATABASE_ERROR"
    )

    with patch("sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            ogrenci_ekle(ogrenci_modeli(), 1)

    assert hata.value.status_code == 500
    assert "QA001_SECRET_DATABASE_ERROR" not in str(
        hata.value.detail
    )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.close.assert_called_once()
    conn.close.assert_called_once()
