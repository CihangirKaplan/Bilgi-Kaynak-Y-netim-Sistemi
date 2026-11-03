"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186
Test Alani: Hassas Veritabani Hata Mesajlari

Amac:
Veritabani hatalarinin teknik ayrintilarinin
API yanitlarinda kullaniciya sizdirilmamasini
dogrulamak.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from sunucu import (
    bakim_kaydi_ekle,
    kalibrasyon_kaydi_ekle,
    faaliyet_kaydi_ekle,
)


HASSAS_HATA = (
    "QA001_SECRET_INTERNAL_DB_INFO "
    "relation=cihaz_bakimlari "
    "host=internal-db"
)


@pytest.mark.parametrize(
    "fonksiyon",
    [
        bakim_kaydi_ekle,
        kalibrasyon_kaydi_ekle,
        faaliyet_kaydi_ekle,
    ],
    ids=[
        "bakim_kaydi",
        "kalibrasyon_kaydi",
        "ogrenci_faaliyet_kaydi",
    ],
)
def test_quality_veritabani_hatasi_hassas_bilgi_sizdirmaz(
    fonksiyon,
):
    """
    QA-001 #186:
    Teknik veritabani hata detaylari
    HTTP 500 yanitinda bulunmamali.
    """

    with patch(
        "sunucu.psycopg2.connect",
        side_effect=RuntimeError(HASSAS_HATA),
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(
                SimpleNamespace(),
                1,
            )

    assert hata.value.status_code == 500

    # Veritabani hata ayrintilari disari cikmamali.
    assert "QA001_SECRET_INTERNAL_DB_INFO" not in str(
        hata.value.detail
    )

    assert "internal-db" not in str(hata.value.detail)
