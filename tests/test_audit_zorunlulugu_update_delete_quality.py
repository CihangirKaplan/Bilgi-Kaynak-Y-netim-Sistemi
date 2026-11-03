"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186

Audit zorunlulugu:
Faaliyet kayitlari ve faaliyet birimleri.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import (
    faaliyet_kaydi_guncelle,
    faaliyet_kaydi_sil,
    faaliyet_birimi_ekle,
    faaliyet_birimi_guncelle,
    faaliyet_birimi_sil,
)


def faaliyet_modeli():
    return SimpleNamespace(
        ogrenci_id=1,
        faaliyet_id=1,
        birim_id=1,
        miktar=2,
    )


def birim_modeli():
    return SimpleNamespace(
        birim_adi="QA001_TEST_BIRIMI",
    )


SENARYOLAR = [
    (
        "faaliyet_update",
        faaliyet_kaydi_guncelle,
        faaliyet_modeli,
    ),
    (
        "faaliyet_delete",
        faaliyet_kaydi_sil,
        None,
    ),
    (
        "birim_create",
        faaliyet_birimi_ekle,
        birim_modeli,
    ),
    (
        "birim_update",
        faaliyet_birimi_guncelle,
        birim_modeli,
    ),
    (
        "birim_delete",
        faaliyet_birimi_sil,
        None,
    ),
]


@pytest.mark.parametrize(
    "ad,fonksiyon,model_uret",
    SENARYOLAR,
    ids=[s[0] for s in SENARYOLAR],
)
def test_quality_audit_importerror_commit_engellenmeli(
    ad,
    fonksiyon,
    model_uret,
):
    """
    Audit basarisizsa ana islem commit edilmemeli.
    """

    conn = MagicMock()
    cursor = conn.cursor.return_value

    # Faaliyet birimi eklemede:
    # Ilk SELECT: birim yok.
    # INSERT RETURNING: yeni ID.
    if ad == "birim_create":
        cursor.fetchone.side_effect = [
            None,
            (501,),
        ]

    # Faaliyet birimi silmede:
    # Ilk SELECT: birim faaliyetlerde kullanilmiyor.
    elif ad == "birim_delete":
        cursor.fetchone.return_value = None

    # Digerlerinde kayit mevcut.
    else:
        cursor.fetchone.return_value = (501,)

    with (
        patch(
            "sunucu.psycopg2.connect",
            return_value=conn,
        ),
        patch(
            "denetim.denetim_kaydi_olustur",
            side_effect=ImportError(
                "QA001_AUDIT_IMPORT_ERROR"
            ),
        ) as audit,
    ):

        with pytest.raises(HTTPException) as hata:

            if ad == "birim_create":
                fonksiyon(
                    model_uret(),
                    yetkili_id=1,
                )

            elif model_uret is None:
                fonksiyon(501, 1)

            else:
                fonksiyon(
                    501,
                    model_uret(),
                    1,
                )

    assert hata.value.status_code == 500

    # Teknik hata bilgisi API yanitina sizmamali.
    assert "QA001_AUDIT_IMPORT_ERROR" not in str(
        hata.value.detail
    )

    # Audit islemi gercekten denenmis olmali.
    audit.assert_called_once()

    # Audit hatasinda ana islem kaydedilmemeli.
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
