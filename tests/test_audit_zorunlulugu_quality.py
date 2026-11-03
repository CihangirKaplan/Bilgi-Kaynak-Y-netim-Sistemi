"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186

Test Alani: Audit Zorunlulugu

Audit islemi ImportError nedeniyle basarisizsa
ana veritabani islemi commit edilmemeli.
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import (
    bakim_kaydi_ekle,
    kalibrasyon_kaydi_ekle,
    faaliyet_kaydi_ekle,
)


def bakim_modeli():
    return SimpleNamespace(
        cihaz_id=1,
        bakim_yapan_kisi="QA Test",
        yapilan_islem="Kontrol",
        maliyet=100,
        bakim_tarihi=date(2026, 10, 27),
        bakim_baslangic_tarihi=date(2026, 10, 27),
        bakim_bitis_tarihi=date(2026, 10, 27),
        sonraki_bakim_tarihi=date(2027, 10, 27),
    )


def kalibrasyon_modeli():
    return SimpleNamespace(
        cihaz_id=1,
        kalibrasyon_yapan_kurum="QA Test",
        gecerlilik_tarihi=date(2027, 10, 27),
        sertifika_no="QA001-TEST",
        kalibrasyon_baslangic_tarihi=date(2026, 10, 27),
        kalibrasyon_bitis_tarihi=date(2026, 10, 27),
    )


def faaliyet_modeli():
    return SimpleNamespace(
        ogrenci_id=1,
        faaliyet_id=1,
        birim_id=1,
        miktar=2,
    )


SENARYOLAR = [
    (bakim_kaydi_ekle, bakim_modeli),
    (kalibrasyon_kaydi_ekle, kalibrasyon_modeli),
    (faaliyet_kaydi_ekle, faaliyet_modeli),
]


@pytest.mark.parametrize(
    "fonksiyon,model_uret",
    SENARYOLAR,
    ids=["bakim", "kalibrasyon", "faaliyet"],
)
def test_quality_audit_importerror_commit_engellenmeli(
    fonksiyon,
    model_uret,
):
    """
    Audit hatasi ana islemin kaydedilmesini
    engellemeli ve rollback yapilmali.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.return_value = (501,)

    with (
        patch(
            "sunucu.psycopg2.connect",
            return_value=conn,
        ),
        patch(
            "denetim.denetim_kaydi_olustur",
            side_effect=ImportError(
                "QA001_AUDIT_MODULE_ERROR"
            ),
        ) as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(model_uret(), 1)

    assert hata.value.status_code == 500

    # Teknik hata bilgisi API yanitina sizmamali.
    assert "QA001_AUDIT_MODULE_ERROR" not in str(
        hata.value.detail
    )

    audit.assert_called_once()

    # Audit basarisizsa ana islem kaydedilmemeli.
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
