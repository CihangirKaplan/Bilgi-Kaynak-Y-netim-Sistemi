import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from client.audit_kayitlari_ekrani import (
    HEDEF_TABLO_ADLARI, OLAY_ADLARI, OLAY_RENKLERI, ayrinti_satirlari,
)
from server.denetim import SILINEBILIR_TABLOLAR, silinen_ayrintisi


def test_normal_tabloda_tum_alanlar_yazilir():
    ayrinti = silinen_ayrintisi("cihaz_bakimlari", {"bakim_id": 1, "yapilan_islem": "x"})
    assert ayrinti == {"silinen": {"bakim_id": 1, "yapilan_islem": "x"}}


def test_ogrencide_kisisel_alanlar_ayiklanir():
    satir = {"ogrenci_id": 5, "ad_soyad": "A B", "telefon": "555", "ogrenci_numarasi": "9", "tur": "GONULLU",
             "aktif_mi": False, "olusturulma_tarihi": "2010-01-01"}
    ayrinti = silinen_ayrintisi("ogrenciler", satir)
    assert "ad_soyad" not in ayrinti["silinen"] and "telefon" not in ayrinti["silinen"]
    assert ayrinti["silinen"]["ogrenci_id"] == 5
    assert ayrinti["maskelenen_alanlar"] == ["ad_soyad", "ogrenci_numarasi", "telefon"]


def test_silinebilir_tablolar_bilinen_tablolardir():
    assert set(SILINEBILIR_TABLOLAR) == {
        "cihaz_bakimlari", "cihaz_kalibrasyonlari", "cihaz_bakim_planlari",
        "ogrenci_faaliyet_takip", "faaliyet_birimleri", "roller", "ogrenciler",
        "odalar",
    }


def test_ekranda_silme_olayi_ve_tablo_adlari_var():
    assert OLAY_ADLARI["DELETE"] == "Silme" and "DELETE" in OLAY_RENKLERI
    for tablo in SILINEBILIR_TABLOLAR:
        assert tablo in HEDEF_TABLO_ADLARI, tablo
    assert "psikolog_odalar" in HEDEF_TABLO_ADLARI


def test_ayrinti_satirlari_silinen_veriyi_duzlestirir():
    satirlar = dict(ayrinti_satirlari({"silinen": {"yapilan_islem": "Filtre", "maliyet": None, "aktif_mi": True}}))
    assert satirlar == {"Yapilan islem": "Filtre", "Maliyet": "—", "Aktif mi": "Evet"}


def test_ayrinti_satirlari_oda_listesi_ve_maske():
    satirlar = dict(ayrinti_satirlari({"onceki_oda_idleri": [1, 2], "yeni_oda_idleri": [], "maskelenen_alanlar": ["telefon"]}))
    assert satirlar["Onceki oda idleri"] == "1, 2" and satirlar["Yeni oda idleri"] == "—"
    assert "telefon" in satirlar["Kişisel veri olduğu için kaydedilmeyen alanlar"]


@pytest.mark.parametrize("girdi", [None, "x", 5, []])
def test_ayrinti_yoksa_bos_liste(girdi):
    assert ayrinti_satirlari(girdi) == []
