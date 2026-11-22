"""Cihaz Geçmişi: zaman çizgisi penceresi, süzgeç, özet çipleri ve Envanter'deki düğme."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import client.cihaz_ekranlari as envanter
import client.cihaz_gecmisi_penceresi as gp


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri, kod=200):
    y = MagicMock(status_code=kod, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


VERI = {
    "cihaz": {"cihaz_id": 5, "envanter_kodu": "EEG-01", "cihaz_adi": "Çok Kanallı EEG", "marka_model": "BrainX", "seri_no": "SN1", "durum": "Kullanima_Hazir",
              "etkin_durum": "Kalibrasyonda", "kayit_tarihi": "2025-01-10T09:00:00"},
    "ozet": {"bakim_sayisi": 2, "toplam_bakim_maliyeti": 12500.5, "kalibrasyon_sayisi": 1, "kalibrasyon_gecerlilik": "2027-06-10",
             "ariza_sayisi": 2, "acik_ariza_sayisi": 1, "rezervasyon_sayisi": 3, "rezervasyon_saati": 7.5},
    "olaylar": [
        {"tur": "Rezervasyon", "kayit_id": 1, "baslangic": "2026-12-01T10:00:00", "bitis": "2026-12-01T12:00:00", "baslik": "Nöroloji", "ayrinti": "Oda: A", "durum": "Aktif"},
        {"tur": "Arıza", "kayit_id": 2, "baslangic": "2026-11-20T09:00:00", "bitis": None, "baslik": "Ses", "ayrinti": "Aciliyet: Düşük", "durum": "Açık"},
        {"tur": "Kalibrasyon", "kayit_id": 3, "baslangic": "2026-10-23", "bitis": "2026-10-25", "baslik": "Sertifika S-9", "ayrinti": "Kurum: K", "durum": None},
        {"tur": "Bakım", "kayit_id": 4, "baslangic": "2026-09-23", "bitis": "2026-09-23", "baslik": "Filtre değişimi", "ayrinti": "Yapan: Ece", "durum": None},
    ],
    "sinir": 300,
}


def _ac(veri=VERI, kod=200):
    with patch.object(gp, "oturum_kontrollu_istek", return_value=_yanit(veri, kod)) as istek:
        p = gp.CihazGecmisiPenceresi("http://x/", "tok", 5)
    p.show()
    return p, istek


def test_yardimci_metinler():
    assert gp.tarih_metni("2026-11-02T09:30:00") == "02.11.2026 09:30" and gp.tarih_metni("2026-10-23") == "23.10.2026" and gp.tarih_metni(None) == ""
    assert gp.olay_zaman_metni({"baslangic": "2026-10-23", "bitis": "2026-10-23"}) == "23.10.2026"
    assert gp.olay_zaman_metni({"baslangic": "2026-10-23", "bitis": "2026-10-25"}) == "23.10.2026  →  25.10.2026"
    assert gp.olay_zaman_metni({"baslangic": "2026-12-01T10:00:00", "bitis": "2026-12-01T12:00:00"}) == "01.12.2026 10:00 – 12:00"
    assert gp.para_metni(12500.5) == "12.500,50 ₺"


def test_pencere_istegi_dogru_adrese_atar_ve_ozeti_gosterir():
    p, istek = _ac()
    assert istek.call_args.args[:2] == ("GET", "http://x/api/cihazlar/5/gecmis")
    assert p.lbl_ad.text() == "Çok Kanallı EEG" and "EEG-01" in p.lbl_alt.text() and "BrainX" in p.lbl_alt.text()
    assert "Kalibrasyonda" in p.durum_cipi.text()                           # ham durum değil, bugünkü etkin durum
    metin = " ".join(e.text() for e in p.baslik_karti.findChildren(QLabel))
    assert "2 bakım · 12.500,50 ₺" in metin and "1 kalibrasyon · geçerlilik 10.06.2027" in metin and "2 arıza · 1 açık" in metin and "3 rezervasyon · 7,5 saat" in metin
    p.close()


def test_kartlar_en_yeni_once_ve_turune_gore_suzulur():
    p, _ = _ac()
    assert [k.olay["tur"] for k in p.kartlar] == ["Rezervasyon", "Arıza", "Kalibrasyon", "Bakım"] and p.lbl_sayac.text() == "4 kayıt"
    assert p.kartlar[1].durum_hapi is not None and p.kartlar[2].durum_hapi is None
    p.suzgec_dugmeleri["Arıza"].click()
    assert [k.isVisible() for k in p.kartlar] == [False, True, False, False] and p.lbl_sayac.text() == "1 kayıt"
    p.suzgec_dugmeleri["Tümü"].click()
    assert all(k.isVisible() for k in p.kartlar)
    p.close()


def test_kaydi_olmayan_tur_icin_bilgi_mesaji():
    veri = dict(VERI, olaylar=[o for o in VERI["olaylar"] if o["tur"] != "Bakım"])
    p, _ = _ac(veri)
    p.suzgec_dugmeleri["Bakım"].click()
    assert p.lbl_bos.isVisible() and "bakım kaydı yok" in p.lbl_bos.text() and not p.kaydirma.isVisible()
    p.close()
    p, _ = _ac(dict(VERI, olaylar=[]))
    assert "henüz kayıt yok" in p.lbl_bos.text()
    p.close()


def test_sunucu_hatasinda_pencere_acilir_hata_yazar():
    p, _ = _ac({"detail": "Bu işlem için yetkiniz bulunmuyor."}, 403)
    assert "alınamadı" in p.lbl_ad.text() and p.veri is None
    p.close()


CIHAZLAR = [{"cihaz_id": 5, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "marka_model": None, "seri_no": None, "durum": "Kullanima_Hazir",
             "kayit_tarihi": "2026-01-01T00:00:00"}]


def _envanter(yetkili):
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=_yanit(CIHAZLAR)):
        e = envanter.CihazYonetimEkrani("http://x", "t", yetkili_mi=yetkili)
    e.resize(1300, 400)
    e.show()
    return e


def test_envanterde_gecmis_dugmesi_yalniz_yoneticiye_gorunur_ve_pencereyi_acar():
    e = _envanter(True)
    assert not e.tablo.isColumnHidden(5) and e.tablo.cellWidget(0, 5) is not None
    with patch("client.cihaz_gecmisi_penceresi.CihazGecmisiPenceresi") as pencere:
        e.tablo.cellWidget(0, 5).findChildren(envanter.QPushButton)[0].click()
    pencere.assert_called_once_with("http://x", "t", 5, e)
    pencere.return_value.exec.assert_called_once()
    e.close()
    e = _envanter(False)
    assert e.tablo.isColumnHidden(5) and e.tablo.cellWidget(0, 5) is None
    e.close()
