"""TKYS Öğrenci Yönetimi güvenlik ve doğrulama testleri."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from server.sunucu import (
    _ogrenci_saklama_suresi_kontrol,
    OgrenciSilOnayModeli,
    OgrenciErteleModeli,
)


def test_olmayan_ogrenci_bulunamaz():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    with pytest.raises(HTTPException) as hata:
        _ogrenci_saklama_suresi_kontrol(cursor, 999999)

    assert hata.value.status_code == 404


def test_danisma_ogrencisi_saklama_islemine_alinmaz():
    cursor = MagicMock()
    cursor.fetchone.return_value = (
        "DANISMA_MASASI",
        False,
        datetime(2018, 1, 1),
        None,
        "2020001",
    )

    with pytest.raises(HTTPException) as hata:
        _ogrenci_saklama_suresi_kontrol(cursor, 1)

    assert hata.value.status_code == 409


def test_aktif_gonullu_saklama_islemine_alinmaz():
    """Aktif öğrencinin saklama süresi işlemez: kayıt tarihi ne kadar eski olursa olsun silinemez/ertelenemez."""
    cursor = MagicMock()
    cursor.fetchone.return_value = ("GONULLU", True, None, None, "2010001")

    with pytest.raises(HTTPException) as hata:
        _ogrenci_saklama_suresi_kontrol(cursor, 1)

    assert hata.value.status_code == 409
    assert "aktif" in hata.value.detail


def test_iki_yili_dolmayan_pasif_gonullu_engellenir():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        ("GONULLU", False, datetime(2026, 1, 1), None, "2025001"),
        (False,),
    ]

    with pytest.raises(HTTPException) as hata:
        _ogrenci_saklama_suresi_kontrol(cursor, 1)

    assert hata.value.status_code == 409
    assert "2 yıl" in hata.value.detail


def test_iki_yildir_pasif_gonullu_kontrolu_gecer():
    cursor = MagicMock()
    cursor.fetchone.side_effect = [
        ("GONULLU", False, datetime(2022, 1, 1), None, "2015001"),
        (True,),
    ]

    sonuc = _ogrenci_saklama_suresi_kontrol(cursor, 1)

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
    from server.sunucu import app

    beklenen = {
        ("GET", "/api/ogrenciler-yonetim"),
        ("GET", "/api/ogrenciler/{ogrenci_id}/puanlar"),
        ("PATCH", "/api/ogrenciler/{ogrenci_id}/silme-ertele"),
        ("DELETE", "/api/ogrenciler/{ogrenci_id}/saklama-suresi-sil"),
        ("PATCH", "/api/ogrenciler/{ogrenci_id}/aktiflik"),
    }

    def rotalar(liste):
        """`include_router` ile eklenen uçlar `app.routes` içinde yönlendirici sarmalayıcısının içindedir."""
        for r in liste:
            yield r
            asil = getattr(r, "original_router", None)
            if asil is not None:
                yield from rotalar(asil.routes)

    mevcut = {
        (metot, route.path)
        for route in rotalar(app.routes)
        for metot in getattr(route, "methods", [])
    }

    assert beklenen <= mevcut


def test_ogrenci_ekleme_yalnizca_gonullu_kabul_eder():
    from pydantic import ValidationError
    from server.modeller import OgrenciEkleModeli

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

    # Gönüllü ve Asistan bu uçtan eklenir. Danışma Masası öğrencisi giriş hesabı gerektirdiği için
    # "Kullanıcı & Personel" ekranından oluşturulur; tanımsız türler de reddedilir.
    assert OgrenciEkleModeli(**veri, tur="ASISTAN").tur == "ASISTAN"

    for tur in ("DANISMA_MASASI", "GECERSIZ", "", "gonullu", None):
        with pytest.raises(ValidationError):
            OgrenciEkleModeli(**veri, tur=tur)


def test_saklama_suresi_sorgulari_pasife_alinmaya_dayanir_10_yil_kalmadi():
    """Saklama süresi pasife alındıktan 2 yıldır; kayıt tarihinden 10 yıl kuralı sunucuda kalmamalı."""
    from pathlib import Path

    for dosya in ("server/sunucu.py", "server/ogrenci_api.py", "server/rapor_ogrenci_faaliyet.py"):
        kaynak = Path(dosya).read_text(encoding="utf-8")
        assert "INTERVAL '10 years'" not in kaynak, dosya
    sunucu = Path("server/ogrenci_api.py").read_text(encoding="utf-8")                   # uçlar server/ogrenci_api.py'ye taşındı
    assert "pasife_alinma_tarihi" in sunucu and "INTERVAL '2 years'" in sunucu
    assert "SAKLAMA_YIL = 2" in Path("server/rapor_ogrenci_faaliyet.py").read_text(encoding="utf-8")
