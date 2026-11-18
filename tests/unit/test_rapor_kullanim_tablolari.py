import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from client.yonetim_raporlari_panel import cihaz_kullanim_tablosu, oda_kullanim_tablosu

KULLANIM = {
    "odalar": [
        {"oda_adi": "Oda A", "randevu_sayisi": 12, "randevu_saati": 12.0, "cihaz_rezervasyon_sayisi": 2,
         "cihaz_rezervasyon_saati": 4.5, "etkinlik_sayisi": 1, "etkinlik_saati": 2.0, "toplam_saat": 18.5},
    ],
    "cihazlar": [
        {"envanter_kodu": "EEG-01", "cihaz_adi": "EEG", "rezervasyon_sayisi": 3, "rezervasyon_saati": 6.5, "iptal_edilen_rezervasyon": 1},
    ],
}


def test_oda_tablosu_saat_ve_sayilari_gosterir():
    baslik, sutunlar, satirlar = oda_kullanim_tablosu(KULLANIM)
    assert "Oda Kullanımı" in baslik and sutunlar == ["Oda", "Randevu", "Rez./Etkinlik", "Toplam Saat"]
    assert satirlar == [("Oda A", "12 (12 sa)", "3 (6.5 sa)", "18.5")]


def test_cihaz_tablosu_saat_ve_iptali_gosterir():
    baslik, sutunlar, satirlar = cihaz_kullanim_tablosu(KULLANIM)
    assert "Cihaz Kullanımı" in baslik
    assert satirlar == [("EEG-01 - EEG", 3, "6.5", 1)]


def test_kullanim_verisi_yoksa_bilgi_satiri_gosterilir():
    for tablo in (oda_kullanim_tablosu(None), cihaz_kullanim_tablosu(None)):
        assert tablo[1] == ["Bilgi"] and "alınamadı" in tablo[2][0][0]


def test_bos_liste_bos_donem_mesaji_verir_ve_en_cok_sinirini_uygular():
    assert "yok" in oda_kullanim_tablosu({"odalar": [], "cihazlar": []})[2][0][0]
    cok = {"odalar": [dict(KULLANIM["odalar"][0], oda_adi=f"O{i}") for i in range(20)], "cihazlar": []}
    assert len(oda_kullanim_tablosu(cok)[2]) == 8
