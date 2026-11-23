"""Faaliyet sayfaları arayüz düzeltmeleri: Puan Raporu süzgeç satırı ve Faaliyet Kayıtları listesi (arama, boş durum)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QLabel, QLineEdit, QTableWidget, QTableWidgetItem, QWidget

import client.main_window as ana
import client.puan_raporu_ekrani as puan_modulu


def _yanit(veri):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    return m


def _kesisir(a, b):
    return a.intersects(b)


def test_puan_raporu_suzgec_satirlari_1280_pikselde_birbirine_girmez(tkys_qapplication):
    veri = {"ozet": {}, "ogrenciler": []}
    with patch.object(puan_modulu, "oturum_kontrollu_istek", return_value=_yanit(veri)):
        ekran = puan_modulu.PuanRaporuEkrani("http://x", "t")
        ekran.resize(1000, 700)                       # 1280 piksel ekranda yan menüden artan alan
        ekran.show()
        tkys_qapplication.processEvents()
    # Kutular ve etiketler kendi önerilen boyutlarında kalır (daralıp yazının üstüne binmez / yazı kesilmez).
    for parca in (ekran.donem, ekran.baslangic, ekran.bitis, ekran.tur_sec, ekran.durum_sec, ekran.puansiz_kutusu):
        assert parca.width() >= parca.minimumSizeHint().width(), parca
    assert ekran.puansiz_kutusu.width() >= ekran.puansiz_kutusu.sizeHint().width()          # "Puanı olmayanları da göster" kesilmez
    # Dönem satırı ile öğrenci süzgeçleri ayrı satırlardadır.
    assert ekran.tur_sec.geometry().top() > ekran.donem.geometry().bottom()
    assert not _kesisir(ekran.tur_sec.geometry(), ekran.durum_sec.geometry())
    ekran.close()


def _liste(tkys_qapplication):
    kap = QWidget()
    sahte = SimpleNamespace(
        arama_faaliyet=QLineEdit(kap), tablo_faaliyetler=QTableWidget(kap), bos_mesaj_faaliyet=QLabel(kap),
    )
    sahte.tablo_faaliyetler.setColumnCount(7)
    for no, (ad, numara, faaliyet) in enumerate([
        ("Ayşe Kaya", "2201001", "Yüz Yüze Anket"), ("Mehmet Demir", "2201002", "Sponsorluk"), ("Ayşe Kaya", "2201001", "Online Anket"),
    ]):
        sahte.tablo_faaliyetler.insertRow(no)
        for sutun, deger in ((1, ad), (2, numara), (3, faaliyet)):
            sahte.tablo_faaliyetler.setItem(no, sutun, QTableWidgetItem(deger))
    return kap, sahte


def _gorunen(sahte):
    return [s for s in range(sahte.tablo_faaliyetler.rowCount()) if not sahte.tablo_faaliyetler.isRowHidden(s)]


def test_faaliyet_listesi_arama_ad_numara_ve_faaliyete_gore_suzer(tkys_qapplication):
    kap, sahte = _liste(tkys_qapplication)
    for aranan, beklenen in (("", [0, 1, 2]), ("ayşe", [0, 2]), ("2201002", [1]), ("sponsor", [1]), ("ANKET", [0, 2])):
        sahte.arama_faaliyet.setText(aranan)
        ana.AnaPencere._faaliyet_listesini_suz(sahte)
        assert _gorunen(sahte) == beklenen, aranan
        assert sahte.tablo_faaliyetler.isHidden() is False and sahte.bos_mesaj_faaliyet.isHidden() is True
    kap.deleteLater()


def test_faaliyet_listesi_bos_ve_sonuc_yok_mesajlari(tkys_qapplication):
    kap, sahte = _liste(tkys_qapplication)
    sahte.arama_faaliyet.setText("bulunmayan")
    ana.AnaPencere._faaliyet_listesini_suz(sahte)
    assert sahte.tablo_faaliyetler.isHidden() and not sahte.bos_mesaj_faaliyet.isHidden()
    assert sahte.bos_mesaj_faaliyet.text() == "Aramaya uyan faaliyet kaydı yok."

    sahte.tablo_faaliyetler.setRowCount(0)                                   # hiç kayıt yok
    sahte.arama_faaliyet.setText("")
    ana.AnaPencere._faaliyet_listesini_suz(sahte)
    assert sahte.bos_mesaj_faaliyet.text() == "Henüz faaliyet kaydı yok." and not sahte.bos_mesaj_faaliyet.isHidden()
    kap.deleteLater()
