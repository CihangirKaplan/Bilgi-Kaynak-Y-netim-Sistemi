"""Randevu: geçmiş bir tarihe randevu verilemez; bugünün geçmiş saatleri serbesttir.

- Oluşturma: başlangıç günü bugünden önceyse 422, veritabanına hiç bağlanılmaz
- Düzenleme: başlangıç DEĞİŞİYORSA ve yeni gün geçmişteyse 422; başlangıç değişmiyorsa (geçmiş randevunun başka alanı düzeltilir) engel yok
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server.modeller import RandevuGuncelleModeli, RandevuOlusturModeli
from server.sunucu import GECMIS_TARIH_MESAJI, gecmis_tarihe_mi, randevu_guncelle, randevu_olustur


def son_is_gunu(gun_once=1):
    """Bugünden en az gun_once gün önceki en yakın iş günü (hafta sonu kuralı devreye girmesin)."""
    g = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) - timedelta(days=gun_once)
    while g.weekday() >= 5:
        g -= timedelta(days=1)
    return g


# ------------------------------------------------------------------ saf işlev
def test_dunku_gun_gecmis_bugun_ve_yarin_degil():
    simdi = datetime.now()
    assert gecmis_tarihe_mi(simdi - timedelta(days=1)) is True
    assert gecmis_tarihe_mi(simdi.replace(hour=0, minute=0, second=0, microsecond=0)) is False      # bugünün erken saati: serbest
    assert gecmis_tarihe_mi(simdi) is False and gecmis_tarihe_mi(simdi + timedelta(days=1)) is False


def test_saat_dilimli_zamanda_da_gun_karsilastirilir():
    assert gecmis_tarihe_mi(datetime.now(timezone.utc) - timedelta(days=2)) is True
    assert gecmis_tarihe_mi(datetime.now(timezone.utc) + timedelta(days=2)) is False


# ------------------------------------------------------------------ oluşturma
def test_gecmis_tarihe_randevu_olusturulamaz_ve_veritabanina_baglanilmaz():
    gecmis = son_is_gunu(2)
    model = RandevuOlusturModeli(danisan_kod_id="DAN-2026-0001", psikolog_id=1, oda_id=1, baslangic_zamani=gecmis, bitis_zamani=gecmis + timedelta(hours=1))
    with patch("server.sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            randevu_olustur(model, kullanici_id=1)
    assert hata.value.status_code == 422 and hata.value.detail == GECMIS_TARIH_MESAJI
    baglan.assert_not_called()


# ------------------------------------------------------------------ düzenleme
def _guncelle(mevcut_baslangic, degisiklikler):
    mevcut = ("DAN-2026-0001", 1, 1, mevcut_baslangic, mevcut_baslangic + timedelta(hours=1), "PLANLANDI", "YUZ_YUZE", "BIREYSEL_TERAPI")
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [(1,), mevcut, ("MUDUR",)] + [None] * 6
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        try:
            return randevu_guncelle(1, RandevuGuncelleModeli(**degisiklikler), kullanici_id=1), conn
        except HTTPException as h:
            return h, conn


def test_baslangici_gecmise_tasimak_422_verir():
    eski = son_is_gunu(0) + timedelta(days=7)
    yeni = son_is_gunu(2)
    sonuc, conn = _guncelle(eski, {"baslangic_zamani": yeni, "bitis_zamani": yeni + timedelta(hours=1)})
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 422 and sonuc.detail == GECMIS_TARIH_MESAJI
    conn.commit.assert_not_called()


def test_gecmis_randevunun_baslangici_degismiyorsa_tarih_denetimi_yapilmaz():
    gecmis = son_is_gunu(10)
    with patch("server.sunucu.gecmis_tarihe_mi", return_value=True) as denetim:
        sonuc, _ = _guncelle(gecmis, {"baslangic_zamani": gecmis, "bitis_zamani": gecmis + timedelta(hours=2)})     # başlangıç aynı, yalnızca bitiş
    assert not (isinstance(sonuc, HTTPException) and sonuc.detail == GECMIS_TARIH_MESAJI)
    denetim.assert_not_called()


def test_baska_alan_guncellenirken_gecmis_tarih_denetimi_yapilmaz():
    gecmis = son_is_gunu(10)
    sonuc, _ = _guncelle(gecmis, {"oda_id": 1})
    assert not (isinstance(sonuc, HTTPException) and sonuc.detail == GECMIS_TARIH_MESAJI)
