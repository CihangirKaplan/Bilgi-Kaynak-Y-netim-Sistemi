"""Geciken Bakım Planı Raporu sayfası + yönetim paneli görünümü + durum kuralı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

import pytest

import client.main_window as ana
from client.bakim_plani_raporu_ekrani import BakimPlaniRaporuEkrani
from client.yonetim_raporlari_panel import EK_KAYNAKLAR, RAPOR_TURLERI, bakim_gecikme_gorunumu
from server.rapor_bakim_plani import plan_durumu
from server.sunucu import bakim_plani_durumu
from test_rapor_sayfalari import ekran_ac, sahte_istek, yaz_ve_oku

PLAN = dict(cihaz_id=1, envanter_kodu="EEG-01", cihaz_adi="EEG", periyot_gun=30, uyari_suresi_gun=7, aktif_mi=True, son_yapilan=None)
VERI = {
    "ozet": {"aktif_plan": 4, "geciken_plan": 2, "yaklasan_plan": 1, "planli_plan": 1, "pasif_plan": 1, "gecikme_orani": 0.5,
             "ortalama_gecikme_gun": 7.0, "en_cok_gecikme_gun": 10, "plani_olmayan_cihaz": 1},
    "geciken": [dict(PLAN, plan_id=1, gorev_turu="Haftalık Şarj", tur="Bakım", sonraki_gorev_tarihi="2026-11-09", kalan_gun=-10, gecikme_gun=10,
                     durum="Gecikmiş", son_yapilan="2026-01-15"),
                dict(PLAN, plan_id=2, gorev_turu="Kalibrasyon Yıllık", tur="Kalibrasyon", sonraki_gorev_tarihi="2026-11-15", kalan_gun=-4,
                     gecikme_gun=4, durum="Gecikmiş")],
    "yaklasan": [dict(PLAN, plan_id=3, gorev_turu="=Aylık", tur="Bakım", sonraki_gorev_tarihi="2026-11-22", kalan_gun=3, gecikme_gun=0, durum="Yaklaşıyor")],
    "planlar": [],
    "cihaz_ozeti": [{"cihaz_id": 1, "cihaz": "EEG-01 - EEG", "geciken": 2, "yaklasan": 1, "plan_sayisi": 4}],
    "tur_ozeti": [{"tur": "Bakım", "gecikmis": 1, "yaklasiyor": 1, "planli": 1, "pasif": 1}, {"tur": "Kalibrasyon", "gecikmis": 1, "yaklasiyor": 0, "planli": 0, "pasif": 0}],
    "planisiz_cihazlar": [{"cihaz_id": 2, "envanter_kodu": "TMS-02", "cihaz_adi": "TMS"}],
}
VERI["planlar"] = VERI["geciken"] + VERI["yaklasan"]


@pytest.mark.parametrize("kalan,uyari,aktif", [(-1, 3, True), (0, 3, True), (3, 3, True), (4, 3, True), (-5, 3, False), (0, 0, True), (10, 0, True)])
def test_durum_kurali_bakim_planlari_ekraniyla_ayni(kalan, uyari, aktif):
    assert plan_durumu(kalan, uyari, aktif) == bakim_plani_durumu(kalan, uyari, aktif)


def test_sayfa_kartlar_tablolar_ve_excel(tmp_path):
    ekran, kayit = ekran_ac(BakimPlaniRaporuEkrani, VERI)
    assert "baslangic" not in kayit[0][1]                                          # bugünkü durum: dönemsiz
    assert ekran.kartlar["geciken"][0].text() == "2" and "%50" in ekran.kartlar["geciken"][1].text()
    assert ekran.kartlar["ortalama"][0].text() == "7,0" and "10 gün" in ekran.kartlar["ortalama"][1].text()
    assert ekran.kartlar["planisiz"][0].text() == "1"
    assert ekran.tablolar["geciken"].rowCount() == 2 and ekran.tablolar["geciken"].item(0, 2).text() == "09.11.2026"
    assert ekran.tablolar["geciken"].item(0, 3).text() == "10" and ekran.tablolar["geciken"].item(1, 4).text() == "—"
    assert ekran.tablolar["tur"].rowCount() == 2 and ekran.tablolar["planisiz"].item(0, 0).text() == "TMS-02 - TMS"
    kitap = yaz_ve_oku(ekran, VERI, tmp_path)
    assert kitap.sheetnames == ["Özet", "Geciken Planlar", "Yaklaşan Planlar", "Tüm Planlar", "Cihaz Bazlı", "Planı Olmayan Cihazlar"]
    satir = [h.value for h in kitap["Geciken Planlar"][2]]
    assert satir[1] == "Haftalık Şarj" and satir[5] == -10 and satir[6] == "Gecikmiş"          # gecikme eksi kalan gün olarak
    assert kitap["Yaklaşan Planlar"]["B2"].quotePrefix is True                                    # formül gibi görünen plan adı formül olmaz


def test_suzgecler_istege_eklenir():
    ekran, kayit = ekran_ac(BakimPlaniRaporuEkrani, VERI)
    kayit.clear()
    with patch("client.rapor_sayfasi_taban.oturum_kontrollu_istek", sahte_istek(VERI, kayit)), \
         patch("client.rapor_sayfasi_taban.oturum_hatasi_mi", return_value=False):
        ekran.tur_sec.setCurrentIndex(2)
        ekran.durum_sec.setCurrentIndex(1)
    assert kayit[-1][1] == {"tur": "kalibrasyon", "durum": "gecikmis"}


def test_geciken_plan_yokken_bos_durum_yazilir():
    bos = dict(VERI, geciken=[], yaklasan=[], planlar=[], cihaz_ozeti=[], tur_ozeti=[], planisiz_cihazlar=[],
               ozet=dict(VERI["ozet"], geciken_plan=0, gecikme_orani=None, ortalama_gecikme_gun=None, en_cok_gecikme_gun=None, yaklasan_plan=0))
    ekran, _ = ekran_ac(BakimPlaniRaporuEkrani, bos)
    assert ekran.kartlar["ortalama"][0].text() == "—" and ekran.kartlar["ortalama"][1].text() == "Geciken plan yok"
    assert ekran.tablolar["geciken"].rowCount() == 0


def test_menude_ve_panelde_tanimli():
    adlar = {o["ad"]: o for _, grup in ana.MENU for o in grup}
    assert adlar["Geciken Bakım Planı Raporu"]["izin"] == "Cihaz raporlarını görüntüleme"
    assert "Geciken Bakım Planı Raporu" in ana.AnaPencere.SAYFA_YENILEME
    assert "Bakım Gecikmeleri" in RAPOR_TURLERI and EK_KAYNAKLAR["bakim_plani"] == ("bakim-plani-raporu", False)


def test_panel_gorunumu_4_kart_5_tablo():
    kartlar, tablolar = bakim_gecikme_gorunumu(VERI)
    assert len(kartlar) == 4 and len(tablolar) == 5 and tablolar[0][2][0] == ("EEG-01 - EEG", "Haftalık Şarj", 10)
    for ad, sutunlar, satirlar in tablolar:
        assert all(len(satir) == len(sutunlar) for satir in satirlar), ad
    yok_kartlar, yok_tablolar = bakim_gecikme_gorunumu(None)
    assert len(yok_kartlar) == 4 and len(yok_tablolar) == 5
