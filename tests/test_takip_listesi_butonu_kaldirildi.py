"""Cihaz Envanteri sayfasında, V1.0 kapsamında olmayan 'Takip Kontrol Listesi' (yapım aşamasında) butonu bulunmaz."""
import main_window as mw

KAYNAK = open("main_window.py", encoding="utf-8").read()


def envanter_blogu():
    return KAYNAK[KAYNAK.index('ad="Cihaz Envanteri"'):KAYNAK.index('ad="Cihaz Rezervasyonu"')]


def test_buton_ve_yapim_asamasi_mesaji_kaynakta_yok():
    assert "Takip Kontrol Listesi" not in KAYNAK
    assert "yapım aşamasında" not in KAYNAK.lower()
    assert not hasattr(mw.AnaPencere, "takip_listesi_tetikle")


def test_envanter_sayfasinin_dugmeleri_cihaz_ekle_ve_envanteri_duzenle():
    blok = envanter_blogu()
    assert "＋  Cihaz Ekle" in blok and "✎  Envanteri Düzenle" in blok
    assert "Takip" not in blok and blok.count('"＋') + blok.count('"✎') + blok.count('"☑') == 2


def test_diger_envanter_dugmeleri_hala_baglidir():
    assert "btn.clicked.connect(self.cihaz_ekle_tetikle)" in KAYNAK
    assert "btn.clicked.connect(self.cihaz_envanter_duzenle_tetikle)" in KAYNAK


def test_izin_tanimi_silinmedi_yalnizca_dugme_kaldirildi():
    # Veritabanı/rol verisine dokunulmaz; yetki matrisindeki satır yerinde kalır.
    assert '"Cihaz takip kontrol listesini yönetme"' in KAYNAK
