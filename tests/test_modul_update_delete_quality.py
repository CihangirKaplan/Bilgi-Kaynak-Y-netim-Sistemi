"""
TKYS - Quality Assurance (QA-001)
GitHub Issue: #186

Bakim, kalibrasyon ve ogrenci faaliyetleri
UPDATE / DELETE islevsel testleri.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from sunucu import (
    bakim_guncelle,
    bakim_kaydi_sil,
    kalibrasyon_guncelle,
    kalibrasyon_kaydi_sil,
    faaliyet_kaydi_guncelle,
    faaliyet_kaydi_sil,
)


def bakim_modeli():
    model = MagicMock()
    model.model_dump.return_value = {
        "yapilan_islem": "QA kontrol"
    }
    return model


def kalibrasyon_modeli():
    model = MagicMock()
    model.model_dump.return_value = {
        "sertifika_no": "QA001-TEST"
    }
    return model


def faaliyet_modeli():
    return SimpleNamespace(
        ogrenci_id=1,
        faaliyet_id=1,
        birim_id=1,
        miktar=2,
    )


SENARYOLAR = [
    (
        "bakim_update",
        bakim_guncelle,
        bakim_modeli,
        "UPDATE",
        "cihaz_bakimlari",
    ),
    (
        "bakim_delete",
        bakim_kaydi_sil,
        None,
        "DELETE",
        "cihaz_bakimlari",
    ),
    (
        "kalibrasyon_update",
        kalibrasyon_guncelle,
        kalibrasyon_modeli,
        "UPDATE",
        "cihaz_kalibrasyonlari",
    ),
    (
        "kalibrasyon_delete",
        kalibrasyon_kaydi_sil,
        None,
        "DELETE",
        "cihaz_kalibrasyonlari",
    ),
    (
        "faaliyet_update",
        faaliyet_kaydi_guncelle,
        faaliyet_modeli,
        "UPDATE",
        "ogrenci_faaliyet_takip",
    ),
    (
        "faaliyet_delete",
        faaliyet_kaydi_sil,
        None,
        "DELETE",
        "ogrenci_faaliyet_takip",
    ),
]


def islemi_calistir(fonksiyon, model_uret):
    """UPDATE ve DELETE fonksiyonlarini ortak sekilde cagir."""

    if model_uret is None:
        return fonksiyon(501, 1)

    return fonksiyon(501, model_uret(), 1)


def audit_bilgileri(audit):
    """Pozisyonel veya isimlendirilmis audit argumanlarini oku."""

    args = audit.call_args.args
    kwargs = audit.call_args.kwargs

    olay = kwargs.get("olay_turu")
    tablo = kwargs.get("hedef_tablo")
    kayit_id = kwargs.get("hedef_kayit_id")

    if olay is None and len(args) > 1:
        olay = args[1]

    if tablo is None and len(args) > 3:
        tablo = args[3]

    if kayit_id is None and len(args) > 4:
        kayit_id = args[4]

    return olay, tablo, kayit_id


@pytest.mark.parametrize(
    "ad,fonksiyon,model_uret,islem,tablo",
    SENARYOLAR,
    ids=[s[0] for s in SENARYOLAR],
)
def test_quality_update_delete_basarili(
    ad, fonksiyon, model_uret, islem, tablo
):
    """SQL, audit ve commit basarili olmali."""

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (501,)

    audit = MagicMock()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.denetim_kaydi_olustur", audit),
        patch("denetim.denetim_kaydi_olustur", audit),
    ):
        sonuc = islemi_calistir(fonksiyon, model_uret)

    assert sonuc["durum"] == "basarili"

    # Dogru tabloda UPDATE / DELETE sorgusu calismali.
    assert any(
        islem in str(c.args[0]).upper()
        and tablo in str(c.args[0])
        for c in cursor.execute.call_args_list
    )

    # Audit ayni transaction icinde olmali.
    audit.assert_called_once()

    olay, audit_tablo, kayit_id = audit_bilgileri(audit)

    assert olay == islem
    assert audit_tablo == tablo
    assert kayit_id == 501

    assert audit.call_args.kwargs["mevcut_cursor"] is cursor

    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "ad,fonksiyon,model_uret,islem,tablo",
    SENARYOLAR,
    ids=[s[0] for s in SENARYOLAR],
)
def test_quality_update_delete_kayit_yok(
    ad, fonksiyon, model_uret, islem, tablo
):
    """Bulunamayan kayitta HTTP 404 donmeli."""

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = None

    audit = MagicMock()

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.denetim_kaydi_olustur", audit),
        patch("denetim.denetim_kaydi_olustur", audit),
    ):
        with pytest.raises(HTTPException) as hata:
            islemi_calistir(fonksiyon, model_uret)

    assert hata.value.status_code == 404

    audit.assert_not_called()

    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "ad,fonksiyon,model_uret,islem,tablo",
    SENARYOLAR,
    ids=[s[0] for s in SENARYOLAR],
)
def test_quality_update_delete_audit_hatasi(
    ad, fonksiyon, model_uret, islem, tablo
):
    """Audit hatasi ana islemi geri almali."""

    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (501,)

    audit = MagicMock(
        side_effect=RuntimeError("QA001_INTERNAL_AUDIT_ERROR")
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.denetim_kaydi_olustur", audit),
        patch("denetim.denetim_kaydi_olustur", audit),
    ):
        with pytest.raises(HTTPException) as hata:
            islemi_calistir(fonksiyon, model_uret)

    assert hata.value.status_code == 500

    # Hassas hata ayrintisi API yanitina sizmamali.
    assert "QA001_INTERNAL_AUDIT_ERROR" not in str(
        hata.value.detail
    )

    audit.assert_called_once()

    assert audit.call_args.kwargs["mevcut_cursor"] is cursor

    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()

    cursor.close.assert_called_once()
    conn.close.assert_called_once()
