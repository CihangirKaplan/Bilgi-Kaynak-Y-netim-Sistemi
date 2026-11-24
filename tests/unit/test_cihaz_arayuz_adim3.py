"""Cihaz yaşam döngüsü arayüz düzeltmeleri: dar pencerede taşma, tarih biçimi, Raporlar süzgeci, Rezervasyon sütunu ve düğmeleri."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

import client.cihaz_ariza_ekranlari as ariza_modulu
import client.cihaz_bakim_ekranlari as bakim_modulu
import client.cihaz_raporlari_ekrani as rapor_modulu
import client.cihaz_rezervasyon_ekranlari as rez_modulu
import client.cihaz_uygunluk_ekrani as uyg_modulu
from client.tablo_tasarimi import tarih_saat_goster


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False, headers={})
    y.json.return_value = veri
    return y


def _gun(n):
    return (date.today() + timedelta(days=n)).isoformat()


@pytest.mark.parametrize("girdi,beklenen", [("2026-11-23T11:59:00", "23.11.2026 11:59"), ("2026-11-23 11:59", "23.11.2026 11:59"),
                                             ("2026-11-23", "23.11.2026"), (None, ""), ("", ""), ("bozuk", "bozuk")])
def test_tarih_saat_goster(girdi, beklenen):
    assert tarih_saat_goster(girdi) == beklenen


def test_ariza_tarihleri_gun_ay_yil_gosterilir_ve_dogru_siralanir():
    veri = [{"ariza_id": 1, "cihaz_adi": "E-1 - EEG", "sorun_basligi": "a", "durum": "Çözüldü", "aciliyet": "Orta",
             "bildirim_tarihi": "2026-11-23T11:59:00", "cozum_tarihi": "2026-11-24T08:00:00", "cozum_notu": "x"},
            {"ariza_id": 2, "cihaz_adi": "E-2 - EKG", "sorun_basligi": "b", "durum": "Açık", "aciliyet": "Orta",
             "bildirim_tarihi": "2026-02-05T09:15:00"}]
    with patch.object(ariza_modulu, "oturum_kontrollu_istek", return_value=_yanit(veri)):
        e = ariza_modulu.ArizaYonetimEkrani("http://x", "t")
    metinler = sorted(e.tablo.item(s, 5).text() for s in range(2))
    assert metinler == ["05.02.2026 09:15", "23.11.2026 11:59"]
    assert "Çözüm tarihi: 24.11.2026 08:00" in ariza_modulu.ariza_ipucu(veri[0])
    e.close()


BAKIMLAR = [{"bakim_id": i, "cihaz_adi": f"E-{i} - Çok Uzun Adlı Bir Cihaz Modeli {i}", "bakim_yapan_kisi": "Ece Yılmaz",
             "yapilan_islem": "Filtre değişimi ve genel kalibrasyon kontrolü", "maliyet": 1250.5,
             "bakim_baslangic_tarihi": _gun(-30), "bakim_bitis_tarihi": _gun(-28), "bakim_tarihi": _gun(-30),
             "sonraki_bakim_tarihi": _gun(150), "uyari_suresi_gun": 7} for i in range(1, 4)]


@pytest.mark.parametrize("genislik", [1100, 1280, 1500, 1920])
def test_bakim_kayitlari_tum_sutunlar_sigar_islem_sutunu_ezilmez(genislik):
    """Tek başına ekran, ana penceredeki 1366 px'ten (yan menü sonrası ~1000 px tablo) daha geniş değil: 1100 px bunu temsil eder."""
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", return_value=_yanit(BAKIMLAR)):
        e = bakim_modulu.BakimYonetimEkrani("http://x", "t")
    e.resize(genislik, 600)
    e.show()
    QApplication.processEvents()
    assert e.tablo.columnWidth(2) >= bakim_modulu.YAPILAN_ISLEM_EN_AZ                       # "YAPILAN İŞLEM" başlığı kesilmez
    assert e.tablo.horizontalHeader().length() <= e.tablo.viewport().width() + 2            # BİLDİRİM ve İŞLEM pencere dışında kalmaz
    assert e.tablo.horizontalScrollBar().maximum() == 0
    e.close()


def test_bakim_kayitlari_cok_dar_pencerede_kaydirma_cikar_islem_sutunu_ezilmez():
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", return_value=_yanit(BAKIMLAR)):
        e = bakim_modulu.BakimYonetimEkrani("http://x", "t")
    e.resize(850, 600)
    e.show()
    QApplication.processEvents()
    assert e.tablo.columnWidth(2) >= bakim_modulu.YAPILAN_ISLEM_EN_AZ
    assert e.tablo.horizontalScrollBar().maximum() > 0                                      # sığmayan sütunlara kaydırarak ulaşılır
    e.close()


def test_bakim_kayitlari_genis_pencerede_islem_sutunu_kalan_yeri_alir():
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", return_value=_yanit(BAKIMLAR)):
        e = bakim_modulu.BakimYonetimEkrani("http://x", "t")
    e.resize(1900, 600)
    e.show()
    QApplication.processEvents()
    assert e.tablo.columnWidth(2) > 300 and e.tablo.horizontalHeader().length() <= e.tablo.viewport().width() + 2
    e.close()


def test_uygunluk_1400_pikselde_yatay_tasma_yok():
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "acceptance"))
    import test_cihaz_uygunluk_ekrani as t
    sunucu = t.Sunucu([t.cihaz(1, "E-1", "EEG", [t.d("REZERVASYON", "2026-11-04T09:00:00", "2026-11-04T10:00:00")])])
    with patch.object(t.ekran_modulu, "oturum_kontrollu_istek", sunucu), \
            patch.object(uyg_modulu.CihazUygunlukEkrani, "_bugun", lambda self: t.BUGUN), \
            patch.object(uyg_modulu.CihazUygunlukEkrani, "_simdi", lambda self: t.SIMDI):
        e = uyg_modulu.CihazUygunlukEkrani("http://x", "t")
    e.resize(1100, 600)
    e.show()
    QApplication.processEvents()
    assert e.tablo.horizontalHeader().length() <= e.tablo.viewport().width() + 2            # ana pencerede 1366 px'e denk gelen tablo genişliği
    e.close()


def _bos_istek(yontem, url, **k):
    y = MagicMock(status_code=200)
    y.json.return_value = [] if url.endswith("/api/cihazlar") else {"bakim_ozeti": {}, "bakimlar": [], "kalibrasyonlar": [], "arizalar": [], "ozet": {}}
    return y


def _rapor_ekrani():
    with patch("client.cihaz_raporlari_ekrani.oturum_kontrollu_istek", _bos_istek), \
         patch("client.cihaz_raporlari_ekrani.oturum_hatasi_mi", return_value=False):
        e = rapor_modulu.CihazRaporlariEkrani("http://x", "t")
    e.resize(1400, 800)
    e.show()
    QApplication.processEvents()
    return e


def test_raporlar_donem_tumu_iken_tarih_kutulari_pasif_diger_donemlerde_aktif():
    e = _rapor_ekrani()
    assert e.donem.currentText() == "Tümü"
    assert not e.baslangic.isEnabled() and not e.bitis.isEnabled()
    assert not e.baslangic_etiketi.isEnabled() and not e.bitis_etiketi.isEnabled()
    e.donem.setCurrentText("Bu Ay")
    assert e.baslangic.isEnabled() and e.bitis.isEnabled() and e.baslangic.date().day() == 1
    e.donem.setCurrentText("Tümü")
    assert not e.baslangic.isEnabled()
    e.close()


def test_raporlar_gece_yarisi_saati_yazilmaz_gercek_saat_yazilir():
    tarih = rapor_modulu.CihazRaporlariEkrani._tarih
    assert tarih("2026-11-23T00:00:00") == "23.11.2026" and tarih("2026-11-23") == "23.11.2026"
    assert tarih("2026-11-23T14:30:00") == "23.11.2026 14:30" and tarih(None) == "—"


REZERVASYONLAR = [
    {"rezervasyon_id": 1, "cihaz_id": "E-1 - EEG", "envanter_kodu": "E-1", "cihaz_adi": "EEG", "durum": "Aktif", "rezerve_eden": "ayse",
     "bolum_adi": "Nöroloji", "oda_adi": "Oda 1", "yonetebilir": True,
     "baslangic_zamani": "2027-12-02T10:00:00", "bitis_zamani": "2027-12-02T11:00:00"},
    {"rezervasyon_id": 2, "cihaz_id": "E-2 - EKG", "envanter_kodu": "E-2", "cihaz_adi": "EKG", "durum": "Aktif", "rezerve_eden": "mehmet",
     "bolum_adi": "Kardiyoloji", "oda_adi": "Oda 2", "yonetebilir": False,
     "baslangic_zamani": "2027-12-03T10:00:00", "bitis_zamani": "2027-12-03T11:00:00"},
    {"rezervasyon_id": 3, "cihaz_id": "E-3 - USG", "envanter_kodu": "E-3", "cihaz_adi": "USG", "durum": "İptal Edildi", "rezerve_eden": None,
     "bolum_adi": "Radyoloji", "oda_adi": "Oda 3", "yonetebilir": True,
     "baslangic_zamani": "2027-12-04T10:00:00", "bitis_zamani": "2027-12-04T11:00:00"},
]


def _rez_ekrani():
    with patch.object(rez_modulu, "oturum_kontrollu_istek", return_value=_yanit(REZERVASYONLAR)):
        e = rez_modulu.RezervasyonYonetimEkrani("http://x", "t", yetkili_mi=True)
    e.resize(1500, 600)
    e.show()
    QApplication.processEvents()
    return e


def _satir(e, rez_id):
    return next(s for s in range(e.tablo.rowCount()) if any(r["rezervasyon_id"] == rez_id and e.tablo.item(s, 0).text().startswith(r["envanter_kodu"])
                                                           for r in REZERVASYONLAR))


def test_rezervasyon_listesinde_rezerve_eden_sutunu_ve_arama():
    e = _rez_ekrani()
    basliklar = [e.tablo.horizontalHeaderItem(i).text() for i in range(e.tablo.columnCount())]
    assert basliklar == ["CİHAZ", "BÖLÜM", "ODA", "PROJE", "TARİH VE SAAT", "REZERVE EDEN", "DURUM", "İŞLEM"]
    assert e.tablo.item(_satir(e, 1), rez_modulu.SUTUN_REZERVE_EDEN).text() == "ayse"
    assert e.tablo.item(_satir(e, 3), rez_modulu.SUTUN_REZERVE_EDEN).text() == "—"
    e.arama.setText("mehmet")
    QApplication.processEvents()
    assert e.tablo.rowCount() == 1 and e.tablo.item(0, 0).text().startswith("E-2")
    e.close()


def test_rezervasyon_duzenle_ve_iptal_dugmeleri_yalniz_yonetebilen_aktif_satirda():
    e = _rez_ekrani()
    kap = e.tablo.cellWidget(_satir(e, 1), rez_modulu.SUTUN_ISLEM)
    dugmeler = kap.findChildren(QPushButton)
    assert [d.toolTip() for d in dugmeler] == ["Düzenle", "Rezervasyonu iptal et"]
    assert e.tablo.cellWidget(_satir(e, 2), rez_modulu.SUTUN_ISLEM) is None                 # başkasının rezervasyonu: yönetme yetkisi yok
    assert e.tablo.cellWidget(_satir(e, 3), rez_modulu.SUTUN_ISLEM) is None                 # iptal edilmiş
    with patch.object(e, "rezervasyon_duzenle") as duzenle:
        dugmeler[0].click()
    duzenle.assert_called_once()
    assert duzenle.call_args[0][0]["rezervasyon_id"] == 1
    with patch.object(e, "rezervasyon_iptal_et") as iptal:
        dugmeler[1].click()
    iptal.assert_called_once_with(1)
    e.close()
