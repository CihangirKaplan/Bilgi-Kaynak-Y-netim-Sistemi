"""Cihaz Yaşam Döngüsü listelerinden Excel aktarımı: Rezervasyon, Bakım, Kalibrasyon, Arıza, Planlar. Ekranda görünen satırlar, cihaz hücresi
iki sütuna ayrılır, rozet metinleri yazılır, aktarım denetim kaydına bildirilir."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import openpyxl
import pytest
from PySide6.QtWidgets import QApplication, QPushButton

import client.bakim_plani_ekranlari as plan_modulu
import client.cihaz_ariza_ekranlari as ariza_modulu
import client.cihaz_bakim_ekranlari as bakim_modulu
import client.cihaz_kalibrasyon_ekranlari as kalib_modulu
import client.cihaz_rezervasyon_ekranlari as rez_modulu
import client.liste_excel as liste_excel


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


def _gun(n):
    return (date.today() + timedelta(days=n)).isoformat()


def _ac(modul, sinif, veri):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(veri)):
        e = getattr(modul, sinif)("http://sunucu", "belirtec")
    e.resize(1500, 500)
    e.show()
    QApplication.processEvents()
    return e


def _aktar(ekran, tmp_path):
    """excele_aktar'ı çalıştırır; (açılan çalışma kitabı, denetim isteği) döndürür."""
    yol = str(tmp_path / "liste.xlsx")
    istekler = []
    with patch.object(liste_excel.QFileDialog, "getSaveFileName", return_value=(yol, "")), \
         patch.object(liste_excel.QMessageBox, "information"), patch.object(liste_excel.QMessageBox, "warning") as uyari, \
         patch.object(liste_excel, "oturum_kontrollu_istek", side_effect=lambda *a, **k: istekler.append((a, k)) or _yanit({})), \
         patch.object(liste_excel, "oturum_hatasi_mi", return_value=False):
        ekran.excele_aktar()
    uyari.assert_not_called()
    return openpyxl.load_workbook(yol), istekler


def _tablo_satirlari(kitap):
    sayfa = [s for s in kitap.worksheets if s.title != "Özet"][0]
    return [[h.value for h in sayfa[1]]] + [[h.value for h in satir] for satir in sayfa.iter_rows(min_row=2)]


def _denetim(istekler, liste, satir_sayisi):
    (yontem, adres), k = istekler[0][0][:2], istekler[0][1]
    assert (yontem, adres) == ("POST", "http://sunucu/api/liste-aktarim-kaydi")
    assert k["json"] == {"liste": liste, "satir_sayisi": satir_sayisi}


def test_tum_cihaz_listelerinde_excel_dugmesi_var():
    veri = {rez_modulu: ("RezervasyonYonetimEkrani", []), bakim_modulu: ("BakimYonetimEkrani", []), kalib_modulu: ("KalibrasyonYonetimEkrani", []),
            plan_modulu: ("BakimPlanlariEkrani", []), ariza_modulu: ("ArizaYonetimEkrani", [])}
    for modul, (sinif, v) in veri.items():
        e = _ac(modul, sinif, v)
        assert any("Excel" in b.text() for b in e.findChildren(QPushButton)), sinif
        e.close()


def test_rezervasyon_gorunen_satirlar_cihaz_iki_sutun(tmp_path):
    veri = [{"rezervasyon_id": 1, "cihaz_id": "EEG-01 - Çok Kanallı EEG", "envanter_kodu": "EEG-01", "cihaz_adi": "Çok Kanallı EEG", "bolum_adi": "Nöroloji",
             "oda_adi": "Oda A", "proje_turu": "TÜBİTAK", "proje_adi_aciklamasi": "x", "durum": "Aktif",
             "baslangic_zamani": "2026-12-01T10:00:00", "bitis_zamani": "2026-12-01T12:00:00"},
            {"rezervasyon_id": 2, "cihaz_id": "TMS-02 - TMS", "envanter_kodu": "TMS-02", "cihaz_adi": "TMS", "bolum_adi": "Psikiyatri", "oda_adi": "Oda B",
             "proje_turu": None, "proje_adi_aciklamasi": None, "durum": "İptal Edildi",
             "baslangic_zamani": "2026-12-02T10:00:00", "bitis_zamani": "2026-12-02T11:00:00"}]
    e = _ac(rez_modulu, "RezervasyonYonetimEkrani", veri)
    e.arama.setText("nöroloji")                                       # yalnızca ilk satır görünür
    QApplication.processEvents()
    kitap, istekler = _aktar(e, tmp_path)
    satirlar = _tablo_satirlari(kitap)
    assert satirlar[0] == ["Envanter Kodu", "Cihaz Adı", "Bölüm", "Oda", "Proje", "Tarih ve Saat", "Rezerve Eden", "Durum"]
    assert len(satirlar) == 2 and satirlar[1][:3] == ["EEG-01", "Çok Kanallı EEG", "Nöroloji"] and satirlar[1][7] == "Aktif"
    _denetim(istekler, "REZERVASYON", 1)
    e.close()


def test_bakim_ve_kalibrasyon_rozet_metinleri_yazilir(tmp_path):
    bakim = [{"bakim_id": 7, "cihaz_adi": "DENEME-006 - Ultrason", "bakim_yapan_kisi": "Ece", "yapilan_islem": "Prob", "maliyet": 9800,
              "bakim_baslangic_tarihi": _gun(-30), "bakim_bitis_tarihi": _gun(-30), "bakim_tarihi": _gun(-30),
              "sonraki_bakim_tarihi": _gun(3), "uyari_suresi_gun": 7}]
    e = _ac(bakim_modulu, "BakimYonetimEkrani", bakim)
    kitap, istekler = _aktar(e, tmp_path)
    satirlar = _tablo_satirlari(kitap)
    assert satirlar[0][:4] == ["Envanter Kodu", "Cihaz Adı", "Yapan Kişi", "Yapılan İşlem"]
    assert satirlar[1][:4] == ["DENEME-006", "Ultrason", "Ece", "Prob"] and satirlar[1][7]                 # bildirim rozeti metni boş değil
    _denetim(istekler, "BAKIM", 1)
    e.close()

    kalib = [{"kalibrasyon_id": 3, "cihaz_adi": "E-5 - Defibrilatör", "kalibrasyon_yapan_kurum": "Kurum", "sertifika_no": "C-1",
              "kalibrasyon_baslangic_tarihi": _gun(-100), "kalibrasyon_bitis_tarihi": _gun(-100), "gecerlilik_tarihi": _gun(265), "uyari_suresi_gun": 30}]
    e = _ac(kalib_modulu, "KalibrasyonYonetimEkrani", kalib)
    kitap, istekler = _aktar(e, tmp_path)
    satirlar = _tablo_satirlari(kitap)
    assert satirlar[1][:5] == ["E-5", "Defibrilatör", "Kurum", "C-1", satirlar[1][4]] and satirlar[1][5]
    _denetim(istekler, "KALIBRASYON", 1)
    e.close()


def test_ariza_cozum_bilgisi_de_aktarilir(tmp_path):
    veri = [{"ariza_id": 5, "cihaz_adi": "Çok Kanallı EEG", "envanter_kodu": "E-42", "ariza_baslik": "Ekran", "ariza_aciklama": "Ekran açılmıyor",
             "aciliyet": "Kritik", "durum": "Çözüldü", "bildirim_tarihi": "2026-11-18T10:00:00", "cozum_tarihi": "2026-11-19T09:30:00", "cozum_notu": "Kablo değişti"},
            {"ariza_id": 4, "cihaz_adi": "TMS", "envanter_kodu": "E-2", "ariza_baslik": "Ses", "ariza_aciklama": "Ses yok", "aciliyet": "Düşük", "durum": "Açık",
             "bildirim_tarihi": "2026-11-10T10:00:00"}]
    e = _ac(ariza_modulu, "ArizaYonetimEkrani", veri)
    kitap, istekler = _aktar(e, tmp_path)
    satirlar = _tablo_satirlari(kitap)
    assert satirlar[0][-3:] == ["Açıklama", "Çözüm Tarihi", "Çözüm Notu"]
    ilk = [s for s in satirlar[1:] if s[0] == "5"][0]
    assert ilk[1:3] == ["E-42", "Çok Kanallı EEG"] and ilk[5] == "Çözüldü" and ilk[-3:] == ["Ekran açılmıyor", "19.11.2026 09:30", "Kablo değişti"]
    acik = [s for s in satirlar[1:] if s[0] == "4"][0]
    assert acik[5] == "Açık" and acik[-2:] == [None, None]                           # boş hücreler Excel'de boş
    _denetim(istekler, "ARIZA", 2)
    e.close()


def test_planlar_aktarilir_ve_kayit_yoksa_bilgilendirir(tmp_path):
    veri = [{"plan_id": 1, "cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "gorev_turu": "Yıllık bakım", "periyot_gun": 365, "uyari_suresi_gun": 30,
             "sonraki_gorev_tarihi": _gun(20), "kalan_gun": 20, "durum": "Yaklaşıyor", "aktif_mi": True, "tur": "Bakım"}]
    e = _ac(plan_modulu, "BakimPlanlariEkrani", veri)
    kitap, istekler = _aktar(e, tmp_path)
    satirlar = _tablo_satirlari(kitap)
    assert satirlar[1][:3] == ["E-1", "EEG", "Yıllık bakım"] and satirlar[1][-1].startswith("Yaklaşıyor")
    _denetim(istekler, "BAKIM_PLANI", 1)
    e.arama.setText("olmayan-bir-sey")
    QApplication.processEvents()
    with patch.object(liste_excel.QMessageBox, "information") as bilgi, patch.object(liste_excel.QFileDialog, "getSaveFileName") as dosya:
        e.excele_aktar()
    bilgi.assert_called_once()
    dosya.assert_not_called()                                          # görünen kayıt yoksa dosya sorulmaz
    e.close()
