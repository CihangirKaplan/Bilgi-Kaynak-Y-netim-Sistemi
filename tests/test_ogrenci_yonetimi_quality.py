"""TKYS Öğrenci Yönetimi güvenlik ve doğrulama testleri."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from sunucu import (
    _ogrenci_on_yil_kontrol,
    OgrenciSilOnayModeli,
    OgrenciErteleModeli,
)


def test_olmayan_ogrenci_bulunamaz():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    with pytest.raises(HTTPException) as hata:
        _ogrenci_on_yil_kontrol(cursor, 999999)

    assert hata.value.status_code == 404


def test_danisma_ogrencisi_on_yil_islemine_alinmaz():
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "DANISMA_MASASI",
        datetime(2018, 1, 1),
        None,
        "2020001",
    )

    with pytest.raises(HTTPException) as hata:
        _ogrenci_on_yil_kontrol(cursor, 1)

    assert hata.value.status_code == 409


def test_on_yili_dolmayan_gonullu_engellenir():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (
            "GONULLU",
            datetime(2025, 1, 1),
            None,
            "2025001",
        ),
        (False,),
    ]

    with pytest.raises(HTTPException) as hata:
        _ogrenci_on_yil_kontrol(cursor, 1)

    assert hata.value.status_code == 409


def test_on_yili_dolan_gonullu_kontrolu_gecer():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        (
            "GONULLU",
            datetime(2015, 1, 1),
            None,
            "2015001",
        ),
        (True,),
    ]

    sonuc = _ogrenci_on_yil_kontrol(cursor, 1)

    assert sonuc == (None, "2015001")


def test_silme_onayi_boolean_olmali():
    with pytest.raises(ValidationError):
        OgrenciSilOnayModeli(onayla="evet")


def test_silme_onayi_ekstra_alan_kabul_etmez():
    with pytest.raises(ValidationError):
        OgrenciSilOnayModeli(
            onayla=True,
            ogrenci_id=123,
        )


def test_erteleme_tarihi_gecerli_olmali():
    with pytest.raises(ValidationError):
        OgrenciErteleModeli(
            yeni_uyari_tarihi="gecersiz"
        )


def test_ogrenci_yonetimi_api_yollari_tanimli():
    from sunucu import app

    beklenen = {
        ("GET", "/api/ogrenciler-yonetim"),
        ("GET", "/api/ogrenciler/{ogrenci_id}/puanlar"),
        ("PATCH", "/api/ogrenciler/{ogrenci_id}/silme-ertele"),
        ("DELETE", "/api/ogrenciler/{ogrenci_id}/on-yil-sil"),
        ("PATCH", "/api/ogrenciler/{ogrenci_id}/aktiflik"),
    }

    mevcut = {
        (metot, route.path)
        for route in app.routes
        for metot in getattr(route, "methods", [])
    }

    assert beklenen <= mevcut


def test_ogrenci_ekleme_yalnizca_gonullu_kabul_eder():
    from pydantic import ValidationError
    from modeller import OgrenciEkleModeli

    veri = {
        "ad_soyad": "Test Öğrenci",
        "ogrenci_numarasi": "2026999",
        "telefon": "05000000000",
    }

    gonullu = OgrenciEkleModeli(
        **veri,
        tur="GONULLU",
    )

    assert gonullu.tur == "GONULLU"

    for tur in (
        "DANISMA_MASASI",
        "ASISTAN",
        "GECERSIZ",
    ):
        with pytest.raises(ValidationError):
            OgrenciEkleModeli(**veri, tur=tur)
