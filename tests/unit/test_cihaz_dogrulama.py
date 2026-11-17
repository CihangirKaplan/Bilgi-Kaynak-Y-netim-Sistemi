"""Cihaz yaşam döngüsü girdi doğrulamaları: veritabanı sınırlarıyla (VARCHAR/DECIMAL/CHECK) uyumlu olmalı.
Gerçek PostgreSQL kullanılmaz."""
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from client.api_yoneticisi import hata_detayi_metni
from server.modeller import (
    ArizaBildirimModeli, ArizaGuncelleModeli, BakimGuncelleModeli, BakimOlusturModeli,
    KalibrasyonGuncelleModeli, KalibrasyonOlusturModeli, RezervasyonOlusturModeli,
)

BAKIM = dict(cihaz_id=1, bakim_tarihi=date(2030, 2, 1), bakim_yapan_kisi="Ali", yapilan_islem="Temizlik",
             bakim_baslangic_tarihi=date(2030, 2, 1), bakim_bitis_tarihi=date(2030, 2, 2))
KALIBRASYON = dict(cihaz_id=1, kalibrasyon_yapan_kurum="Kurum", gecerlilik_tarihi=date(2031, 1, 1), sertifika_no="C1",
                   kalibrasyon_baslangic_tarihi=date(2030, 6, 1), kalibrasyon_bitis_tarihi=date(2030, 6, 2))
ARIZA = dict(cihaz_id=1, ariza_baslik="Wi-Fi arızası", ariza_aciklama="Bağlantı kopuyor")


@pytest.mark.parametrize("aciliyet", ["Düşük", "Orta", "Yüksek", "Kritik"])
def test_gecerli_aciliyet_kabul_edilir(aciliyet):
    assert ArizaBildirimModeli(**ARIZA, aciliyet=aciliyet).aciliyet == aciliyet


@pytest.mark.parametrize("aciliyet", ["BAMBASKA", "Orta]x", "", "kritik"])
def test_gecersiz_aciliyet_reddedilir(aciliyet):
    with pytest.raises(ValidationError):
        ArizaBildirimModeli(**ARIZA, aciliyet=aciliyet)
    with pytest.raises(ValidationError):
        ArizaGuncelleModeli(ariza_baslik="Baslik", ariza_aciklama="Aciklama", aciliyet=aciliyet, cozuldu_mu=False)


def test_bakim_siniri_ve_tarih_sirasi():
    assert BakimOlusturModeli(**BAKIM).maliyet == 0.0
    for kotu in ({"bakim_yapan_kisi": "K" * 101}, {"maliyet": -1}, {"maliyet": 1e8},
                 {"bakim_bitis_tarihi": date(2030, 1, 1)}, {"cihaz_id": 0}):
        with pytest.raises(ValidationError):
            BakimOlusturModeli(**{**BAKIM, **kotu})
    BakimOlusturModeli(**{**BAKIM, "maliyet": 99_999_999.99, "bakim_bitis_tarihi": date(2030, 2, 1)})


def test_bakim_guncelleme_tek_alan_ve_ters_tarih():
    assert BakimGuncelleModeli(bakim_bitis_tarihi=date(2030, 1, 1)).model_dump(exclude_unset=True)   # tek alan: sunucu mevcutla karşılaştırır
    with pytest.raises(ValidationError):
        BakimGuncelleModeli(bakim_baslangic_tarihi=date(2030, 3, 2), bakim_bitis_tarihi=date(2030, 3, 1))
    with pytest.raises(ValidationError):
        BakimGuncelleModeli(maliyet=-5)


def test_kalibrasyon_tarih_sirasi():
    KalibrasyonOlusturModeli(**KALIBRASYON)
    with pytest.raises(ValidationError):
        KalibrasyonOlusturModeli(**{**KALIBRASYON, "kalibrasyon_bitis_tarihi": date(2030, 5, 1)})
    with pytest.raises(ValidationError):
        KalibrasyonGuncelleModeli(kalibrasyon_baslangic_tarihi=date(2030, 3, 2), kalibrasyon_bitis_tarihi=date(2030, 3, 1))


def test_rezervasyonda_bos_metin_null_olur():
    r = RezervasyonOlusturModeli(cihaz_id=1, baslangic_zamani="2030-01-01T10:00:00", bitis_zamani="2030-01-01T11:00:00",
                                 proje_turu="", proje_adi_aciklamasi="   ")
    assert r.proje_turu is None and r.proje_adi_aciklamasi is None
    with pytest.raises(ValidationError):
        RezervasyonOlusturModeli(cihaz_id=1, baslangic_zamani="2030-01-01T10:00:00", bitis_zamani="2030-01-01T11:00:00",
                                 proje_adi_aciklamasi="x" * 256)


def _yanit(detay):
    return SimpleNamespace(json=lambda: {"detail": detay})


def test_hata_detayi_her_bicimde_duz_metin_doner():
    assert hata_detayi_metni(_yanit("Düz hata")) == "Düz hata"
    assert hata_detayi_metni(_yanit({"kod": "X", "mesaj": "Çakışma var"})) == "Çakışma var"
    liste = [{"msg": "String should have at most 255 characters"}, {"msg": "Value error, Bitiş önce olamaz."}]
    assert hata_detayi_metni(_yanit(liste)) == "String should have at most 255 characters\nBitiş önce olamaz."
    assert isinstance(hata_detayi_metni(_yanit([])), str)
    assert hata_detayi_metni(SimpleNamespace(json=lambda: 1 / 0), "yedek") == "yedek"
