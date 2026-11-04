"""
TKYS QA-001
Rol-izin matrisi ve izin ekleme API'lerinde
teknik hata bilgilerinin sizdirilmamasi.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import (
    rol_izin_matrisi_getir,
    izin_ekle,
)


HASSAS_HATA = (
    "QA001_SECRET_INTERNAL_DB_INFO "
    "host=internal-db "
    "relation=rol_izinleri"
)


@pytest.mark.parametrize(
    "fonksiyon, parametreler",
    [
        (
            rol_izin_matrisi_getir,
            {"kullanici_id": 42},
        ),
        (
            izin_ekle,
            {
                "izin_verisi": {"izin_adi": "QA_TEST_IZIN"},
                "kullanici_id": 42,
            },
        ),
    ],
    ids=["rol_izin_matrisi", "izin_ekleme"],
)
def test_veritabani_hatasi_hassas_bilgi_sizdirmaz(
    fonksiyon,
    parametreler,
    capsys,
):
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.execute.side_effect = RuntimeError(HASSAS_HATA)

    with patch(
        "sunucu.psycopg2.connect",
        return_value=conn,
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(**parametreler)

    # API, sunucu hatasini bildirmeli.
    assert hata.value.status_code == 500

    # Teknik veritabani ayrintilari API yanitina girmemeli.
    assert "QA001_SECRET_INTERNAL_DB_INFO" not in str(
        hata.value.detail
    )

    assert "internal-db" not in str(hata.value.detail)

    # Hassas hata bilgisi standart terminal ciktisina yazilmamali.
    cikti = capsys.readouterr()
    assert "QA001_SECRET_INTERNAL_DB_INFO" not in cikti.out

    # Veritabani kaynaklari kapatilmali.
    cursor.close.assert_called_once()
    conn.close.assert_called_once()

    # Basarisiz islem kaydedilmemeli.
    conn.commit.assert_not_called()
