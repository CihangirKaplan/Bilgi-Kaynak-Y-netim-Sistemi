"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186

Bakim, kalibrasyon ve ogrenci faaliyetleri
CREATE islemlerinin islevsel testleri.
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
    (bakim_kaydi_ekle, bakim_modeli, "cihaz_bakimlari"),
    (
        kalibrasyon_kaydi_ekle,
        kalibrasyon_modeli,
        "cihaz_kalibrasyonlari",
    ),
    (
        faaliyet_kaydi_ekle,
        faaliyet_modeli,
        "ogrenci_faaliyet_takip",
    ),
]


@pytest.mark.parametrize(
    "fonksiyon,model_uret,tablo",
    SENARYOLAR,
    ids=["bakim", "kalibrasyon", "faaliyet"],
)
def test_quality_create_basarili(
    fonksiyon, model_uret, tablo
):
    """INSERT, audit ve commit basarili olmali."""

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (501,)

    with (
        patch(
            "sunucu.psycopg2.connect",
            return_value=conn,
        ),
        patch(
            "denetim.denetim_kaydi_olustur"
        ) as audit,
    ):
        sonuc = fonksiyon(model_uret(), 1)

    assert sonuc["durum"] == "basarili"

    # Ana kayit olusturulmali.
    assert any(
        "INSERT INTO" in str(c.args[0])
        and tablo in str(c.args[0])
        for c in cursor.execute.call_args_list
    )

    # Audit ayni transaction'da olmali.
    audit.assert_called_once()

    cagri = audit.call_args
    assert cagri.kwargs["mevcut_cursor"] is cursor

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "fonksiyon,model_uret,tablo",
    SENARYOLAR,
    ids=["bakim", "kalibrasyon", "faaliyet"],
)
def test_quality_create_insert_hatasinda_rollback(
    fonksiyon, model_uret, tablo
):
    """INSERT basarisizsa commit yapilmamali."""

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.execute.side_effect = RuntimeError(
        "QA001_INTERNAL_DB_ERROR"
    )

    with (
        patch(
            "sunucu.psycopg2.connect",
            return_value=conn,
        ),
        patch(
            "denetim.denetim_kaydi_olustur"
        ) as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(model_uret(), 1)

    assert hata.value.status_code == 500

    assert "QA001_INTERNAL_DB_ERROR" not in str(
        hata.value.detail
    )

    audit.assert_not_called()

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "fonksiyon,model_uret,tablo",
    SENARYOLAR,
    ids=["bakim", "kalibrasyon", "faaliyet"],
)
def test_quality_create_audit_hatasinda_rollback(
    fonksiyon, model_uret, tablo
):
    """Audit basarisizsa ana islem kaydedilmemeli."""

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
            side_effect=RuntimeError(
                "QA001_AUDIT_ERROR"
            ),
        ) as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            fonksiyon(model_uret(), 1)

    assert hata.value.status_code == 500

    assert "QA001_AUDIT_ERROR" not in str(
        hata.value.detail
    )

    audit.assert_called_once()

    assert (
        audit.call_args.kwargs["mevcut_cursor"]
        is cursor
    )

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
