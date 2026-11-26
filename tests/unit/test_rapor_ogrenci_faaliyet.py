"""Öğrenci Raporu ve Faaliyet Raporu sayfaları + yönetim paneli görünümleri: ekran, süzgeç, Excel içeriği."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

import client.main_window as ana
from client.faaliyet_raporu_ekrani import FaaliyetRaporuEkrani
from client.ogrenci_raporu_ekrani import OgrenciRaporuEkrani
from client.yonetim_raporlari_panel import EK_KAYNAKLAR, RAPOR_TURLERI, faaliyet_gorunumu, ogrenci_mevcut_gorunumu
from test_rapor_sayfalari import ekran_ac, yaz_ve_oku

OGRENCI = {
    "ozet": {"toplam": 3, "aktif": 2, "pasif": 1, "son_30_gun_yeni": 1, "saklama_suresi_dolmus": 1, "saklama_ertelenen": 1,
             "saklama_yaklasan": 0, "faaliyetsiz_aktif": 1},
    "tur_dagilimi": [{"tur": "GONULLU", "etiket": "Gönüllü Öğrenci", "toplam": 2, "aktif": 1, "pasif": 1},
                     {"tur": "ASISTAN", "etiket": "Asistan Öğrenci", "toplam": 1, "aktif": 1, "pasif": 0}],
    "bolum_dagilimi": [{"bolum": "Psikoloji", "ogrenci": 1}, {"bolum": "Belirtilmemiş", "ogrenci": 2}],
    "ogrenciler": [
        {"ogrenci_id": 1, "ad_soyad": "Ayşe Y", "ogrenci_numarasi": "N1", "tur": "GONULLU", "tur_etiketi": "Gönüllü Öğrenci", "aktif_mi": True,
         "bolum": None, "sinif": None, "olusturulma_tarihi": "2010-01-01T00:00:00", "faaliyet_sayisi": 0, "toplam_puan": 0.0,
         "son_faaliyet_tarihi": None, "saklama_durumu": "Süresi doldu", "saklama_bitis": "2022-01-01", "pasife_alinma_tarihi": "2020-01-01", "erteleme_tarihi": None,
         "yeni_kayit_mi": False, "faaliyetsiz_mi": True},
        {"ogrenci_id": 2, "ad_soyad": "=KOTU()", "ogrenci_numarasi": "N2", "tur": "ASISTAN", "tur_etiketi": "Asistan Öğrenci", "aktif_mi": False,
         "bolum": "Psikoloji", "sinif": "3", "olusturulma_tarihi": "2025-05-05T00:00:00", "faaliyet_sayisi": 4, "toplam_puan": 12.0,
         "son_faaliyet_tarihi": "2026-10-01", "saklama_durumu": None, "saklama_bitis": None, "erteleme_tarihi": None,
         "yeni_kayit_mi": True, "faaliyetsiz_mi": False},
    ],
    "kurallar": {"saklama_yil": 10, "yaklasan_ay": 12, "faaliyetsiz_gun": 90},
}
FAALIYET = {
    "ozet": {"kayit_sayisi": 2, "faaliyet_miktari": 5, "toplam_puan": 19.0, "faaliyet_yapan_ogrenci": 1, "ortalama_puan_kayit": 9.5},
    "faaliyetler": [{"faaliyet_id": 1, "faaliyet": "Seminer", "kayit_sayisi": 2, "miktar": 5, "puan": 19.0}],
    "birimler": [{"birim": "SAAT", "kayit_sayisi": 2, "miktar": 5}],
    "ogrenci_turleri": [{"tur": "GONULLU", "etiket": "Gönüllü Öğrenci", "ogrenci_sayisi": 1, "kayit_sayisi": 2, "puan": 19.0}],
    "faaliyet_secenekleri": [{"faaliyet_id": 1, "faaliyet_adi": "Seminer"}],
    "kayitlar": [{"takip_id": 7, "ogrenci": "Ayşe Y", "ogrenci_numarasi": "N1", "tur": "Gönüllü Öğrenci", "faaliyet": "Seminer", "birim": "SAAT",
                  "adet": 3, "birim_puan": 5.0, "toplam_puan": 15.0, "tarih": "2026-11-02"}],
    "donem": {"baslangic": "2026-11-01", "bitis": "2026-11-30"},
}


def test_ogrenci_raporu_sayfasi_kartlar_tablolar_ve_excel(tmp_path):
    ekran, kayit = ekran_ac(OgrenciRaporuEkrani, OGRENCI)
    assert "baslangic" not in kayit[0][1]                                         # öğrenci raporu dönemsizdir
    assert ekran.kartlar["toplam"][0].text() == "3" and ekran.kartlar["saklama"][0].text() == "1"
    assert "1 ertelendi" in ekran.kartlar["saklama"][1].text()
    assert ekran.tablolar["tur"].rowCount() == 2 and ekran.tablolar["liste"].rowCount() == 2
    assert ekran.tablolar["liste"].item(0, 3).text() == "01.01.2010" and ekran.tablolar["liste"].item(0, 4).text() == "—"
    assert ekran.tablolar["liste"].item(1, 5).text() == "—" and ekran.tablolar["liste"].item(0, 5).text() == "Süresi doldu"
    kitap = yaz_ve_oku(ekran, OGRENCI, tmp_path)
    assert kitap.sheetnames == ["Özet", "Öğrenci Listesi", "Tür Dağılımı", "Bölüm Dağılımı", "Saklama Süresi"]
    assert kitap["Saklama Süresi"].max_row == 2                                     # başlık + yalnızca saklama durumu olan öğrenci
    assert kitap["Öğrenci Listesi"]["A3"].quotePrefix is True                        # formül gibi görünen ad formül olmaz
    basliklar = [h.value for h in kitap["Öğrenci Listesi"][1]]
    assert "Telefon" not in basliklar and "telefon" not in str(OGRENCI)


def test_ogrenci_suzgecleri_istege_eklenir():
    from unittest.mock import patch
    ekran, kayit = ekran_ac(OgrenciRaporuEkrani, OGRENCI)
    kayit.clear()
    from test_rapor_sayfalari import sahte_istek
    with patch("client.rapor_sayfasi_taban.oturum_kontrollu_istek", sahte_istek(OGRENCI, kayit)), \
         patch("client.rapor_sayfasi_taban.oturum_hatasi_mi", return_value=False):
        ekran.tur_sec.setCurrentIndex(3)
        ekran.durum_sec.setCurrentIndex(2)
    assert kayit[-1][1] == {"tur": "ASISTAN", "durum": "pasif"}


def test_faaliyet_raporu_sayfasi_kartlar_tablolar_ve_excel(tmp_path):
    ekran, kayit = ekran_ac(FaaliyetRaporuEkrani, FAALIYET)
    assert {"baslangic", "bitis"} <= set(kayit[0][1])
    assert ekran.faaliyet_sec.count() == 2 and ekran.faaliyet_sec.itemText(1) == "Seminer"
    assert ekran.kartlar["kayit"][0].text() == "2" and ekran.kartlar["puan"][0].text() == "19"
    assert ekran.kartlar["ogrenci"][0].text() == "1" and "bekleyen" not in ekran.kartlar and "bekleyen" not in ekran.tablolar
    assert ekran.tablolar["faaliyet"].columnCount() == 4 and ekran.tablolar["faaliyet"].item(0, 3).text() == "19"
    assert not hasattr(ekran, "onay_sec")                                           # onay süzgeci yok
    ekran.goster(FAALIYET)
    assert ekran.faaliyet_sec.count() == 2                                          # liste çoğalmaz
    kitap = yaz_ve_oku(ekran, FAALIYET, tmp_path)
    assert kitap.sheetnames == ["Özet", "Faaliyet Türü", "Birim", "Öğrenci Türü", "Faaliyet Detayı"]
    assert [h.value for h in kitap["Faaliyet Detayı"][1]][-1] == "Tarih" and kitap["Faaliyet Detayı"].max_column == 10


def test_yeni_sayfalar_menude_ve_izinleri_tanimli():
    adlar = {o["ad"]: o for _, grup in ana.MENU for o in grup}
    for ad in ("Öğrenci Raporu", "Faaliyet Raporu"):
        assert adlar[ad]["izin"] == "Faaliyet kayıtlarını düzenleme" and adlar[ad]["izin"] in ana.IZIN_KODLARI
        assert ad in ana.AnaPencere.SAYFA_YENILEME


@pytest.mark.parametrize("gorunum,veri,kart_sayisi,tablo_sayisi", [(ogrenci_mevcut_gorunumu, OGRENCI, 4, 5), (faaliyet_gorunumu, FAALIYET, 4, 5)])
def test_panel_gorunumleri_kart_ve_tablo_sayisi(gorunum, veri, kart_sayisi, tablo_sayisi):
    kartlar, tablolar = gorunum(veri)
    assert len(kartlar) == kart_sayisi and len(tablolar) == tablo_sayisi
    for ad, sutunlar, satirlar in tablolar:
        assert all(len(satir) == len(sutunlar) for satir in satirlar), ad
    yok_kartlar, yok_tablolar = gorunum(None)
    assert len(yok_kartlar) == kart_sayisi and len(yok_tablolar) == tablo_sayisi


def test_panel_ogrenci_gorunumu_saklama_ve_faaliyetsizleri_listeler():
    _, tablolar = ogrenci_mevcut_gorunumu(OGRENCI)
    assert tablolar[2][2] == [("Ayşe Y", "Süresi doldu")] and tablolar[3][2] == [("Ayşe Y", "Hiç yok")]
    assert {"Öğrenci Mevcudu", "Faaliyetler"} <= set(RAPOR_TURLERI) and "Faaliyet Onayları" not in RAPOR_TURLERI
    assert EK_KAYNAKLAR["ogrenci_rapor"][1] is False and EK_KAYNAKLAR["faaliyet_rapor"][1] is True
