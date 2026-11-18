"""Randevu formu: geçmiş tarih seçilemez (sunucu asıl korumadır); geçmişte kalmış randevunun kendi tarihi düzenlemede görünür kalır.

Alt sınır testlerde conftest tarafından çok eski bir tarihe sabitlenir; bu dosya gerçek 'bugün'ü kullanmak için kendi değerini koyar.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate

import client.randevu_ekranlari as modul
from client.randevu_ekranlari import RandevuDuzenleFormu, RandevuOlusturFormu


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


def sahte_sunucu(yontem, url, **kwargs):
    if url.endswith("/api/randevular/doluluk"):
        return cevap({"dolu_araliklar": []})
    if url.endswith("/api/psikologlar"):
        return cevap([{"personel_id": 3, "ad_soyad": "Ayşe", "kullanici_id": 13}])
    if "/odalar" in url:
        return cevap([{"oda_id": 2, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}])
    return cevap([])


@pytest.fixture(autouse=True)
def gercek_bugun(monkeypatch):
    monkeypatch.setattr(modul, "bugunun_tarihi", QDate.currentDate)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte_sunucu):
        yield


def test_yeni_randevu_formunda_tarih_secici_bugunden_baslar_gecmis_secilemez():
    form = RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    bugun = QDate.currentDate()
    assert form.dt_tarih.minimumDate() == bugun
    form.dt_tarih.setDate(bugun.addDays(-3))
    assert form.dt_tarih.date() >= bugun                                 # geçmiş tarih kabul edilmez
    form.close()


def test_duzenleme_formunda_gelecek_randevu_gecmise_tasinamaz():
    gelecek = QDate.currentDate().addDays(10)
    eski = {"danisan_kod_id": "DAN-2026-0001", "psikolog_id": 3, "oda_id": 2, "durum": "PLANLANDI",
            "baslangic_zamani": gelecek.toString("yyyy-MM-dd") + "T10:00:00", "bitis_zamani": gelecek.toString("yyyy-MM-dd") + "T11:00:00"}
    form = RandevuDuzenleFormu("http://testserver", "TOKEN", 11, 1, eski)
    assert form.dt_tarih.minimumDate() == QDate.currentDate() and form.dt_tarih.date() == gelecek
    form.dt_tarih.setDate(QDate.currentDate().addDays(-2))
    assert form.dt_tarih.date() >= QDate.currentDate()
    form.close()


def test_duzenleme_formunda_gecmis_randevunun_kendi_tarihi_gorunur_kalir():
    gecmis = QDate.currentDate().addDays(-20)
    eski = {"danisan_kod_id": "DAN-2026-0001", "psikolog_id": 3, "oda_id": 2, "durum": "PLANLANDI",
            "baslangic_zamani": gecmis.toString("yyyy-MM-dd") + "T10:00:00", "bitis_zamani": gecmis.toString("yyyy-MM-dd") + "T11:00:00"}
    form = RandevuDuzenleFormu("http://testserver", "TOKEN", 11, 1, eski)
    assert form.dt_tarih.date() == gecmis and form.dt_tarih.minimumDate() == gecmis      # kendi tarihi kırpılmaz
    form.dt_tarih.setDate(gecmis.addDays(-5))
    assert form.dt_tarih.date() == gecmis                                                # ama daha eskiye de gidilmez
    form.close()
