"""Öğrenciler sayfasının yeni tasarımı: sayaç, özet kartları, durum etiketi, çift tıklama, bellek/çıkış güvenliği.

Liste, süzgeç ve silme davranışları test_ogrenci_sayfasi_duzeltmeleri.py'de; burada görünüm/etkileşim katmanı sınanır.
"""
import gc
import json
import weakref
from unittest.mock import MagicMock, patch

import client.ogrenci_yonetim_ekrani as modul
from client.sayfa_tema import DurumRozetiDelegate


def _yanit(veri, kod=200):
    m = MagicMock()
    m.status_code = kod
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    return m


def _ogrenci(no, ad, tur="GONULLU", aktif=True, dolu=False, ertelendi=False):
    return {
        "ogrenci_id": no, "ad_soyad": ad, "ogrenci_numarasi": f"23100{no:03d}", "tur": tur,
        "tur_etiketi": "Gönüllü Öğrenci" if tur == "GONULLU" else "Asistan Öğrenci", "aktif_mi": aktif, "kullanici_id": None,
        "kullanici_adi": None, "rol_adi": None, "telefon": None, "olusturulma_tarihi": "2010-01-05T10:00:00",
        "kayit_suresi_doldu": dolu, "ertelemeye_kadar": "2030-01-01" if ertelendi else None, "ertelendi_mi": ertelendi,
    }


def _ekran(kayitlar):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(kayitlar)), \
            patch.object(modul.QMessageBox, "information", lambda *a, **k: 0):
        ekran = modul.OgrenciYonetimEkrani("http://x", "t")
        ekran.yenile()
    return ekran


def test_sayac_ve_ozet_kartlari_suzgece_gore_guncellenir(tkys_qapplication):
    ekran = _ekran([_ogrenci(1, "Ali"), _ogrenci(2, "Bora", aktif=False), _ogrenci(3, "Can", tur="ASISTAN")])
    assert ekran.sayac_rozeti.text() == "3 öğrenci"
    assert [ekran.degerler[a].text() for a in ("total", "active", "passive", "expired")] == ["3", "2", "1", "0"]

    ekran.durum_filtresi.setCurrentIndex(2)                                       # Pasif
    assert ekran.sayac_rozeti.text() == "1 öğrenci" and ekran.tablo.rowCount() == 1
    assert ekran.degerler["total"].text() == "3"                                   # kartlar süzgeçten etkilenmez, tüm kayıtları sayar
    assert "Görüntülenen 1" in ekran.ozet.text()

    ekran.filtreleri_temizle()
    assert ekran.sayac_rozeti.text() == "3 öğrenci"


def test_durum_etiketi_hucre_metnini_degistirmez_ve_renkleri_var(tkys_qapplication):
    ekran = _ekran([_ogrenci(1, "Ali"), _ogrenci(2, "Bora", aktif=False)])
    delege = ekran.tablo.itemDelegateForColumn(6)
    assert isinstance(delege, modul.EtiketDelegate) and isinstance(delege, DurumRozetiDelegate)
    assert [ekran.tablo.item(s, 6).text() for s in range(2)] == ["Aktif", "Pasif"]         # sıralama/arama/Excel metne bağlı kalır
    assert set(delege.renkler) == {"Aktif", "Pasif"} and delege.renkler["Aktif"] != delege.renkler["Pasif"]

    ekran.resize(1100, 700)
    ekran.show()
    tkys_qapplication.processEvents()
    assert not ekran.tablo.viewport().grab().isNull()                                       # çizim hata vermez
    ekran.close()


def test_satira_cift_tiklayinca_detay_acilir(tkys_qapplication):
    ekran = _ekran([_ogrenci(1, "Ali")])
    with patch.object(ekran, "detay_ac") as detay:
        ekran.tablo.cellDoubleClicked.emit(0, 0)
    detay.assert_called_once()


def test_ust_dugmeler_ve_basliklar(tkys_qapplication):
    ekran = _ekran([_ogrenci(1, "Ali")])
    assert ekran.ekle_btn.objectName() == "birincil" and ekran.sure_btn.objectName() == "uyari"
    assert ekran.sure_btn.text() == "Süresi Dolan Kayıtlar (0)"
    basliklar = [ekran.tablo.horizontalHeaderItem(i).text() for i in range(ekran.tablo.columnCount())]
    assert basliklar == ["AD SOYAD", "ÖĞRENCİ NO", "TELEFON", "ÖĞRENCİ GRUBU", "BAĞLI HESAP", "KAYIT TARİHİ", "DURUM"]


def test_sayfa_silinince_temizlenir_cikista_qt_cokmez(tkys_qapplication):
    """Düğme/sinyal bağlantısında sayfayı tutan `lambda` kullanılırsa sayfa çöp toplayıcıya görünmeyen bir döngüde kalır ve
    süreç kapanırken Qt'yi çökertir (çıkış kodu 139)."""
    ekran = _ekran([_ogrenci(i, f"Kisi{i}") for i in range(1, 4)])
    referans = weakref.ref(ekran)
    del ekran
    gc.collect()
    assert referans() is None


# ------------------------------------------------------------------ Detay / Puanlar penceresi
FAALIYETLER = [
    {"tarih": "2026-11-20", "faaliyet": "Danışma masası nöbeti", "adet": 4, "birim": "Saat", "birim_puan": 2.5, "toplam_puan": 10.0},
    {"tarih": "2026-11-18", "faaliyet": "Deney katılımcı kaydı", "adet": 3, "birim": "Kişi", "birim_puan": 1.0, "toplam_puan": 3.0},
]


def _detay_incele(faaliyetler, toplam, olay=None):
    """Detay penceresini sahte sunucuyla açar; pencere kapanmadan önce içeriği toplanıp döner."""
    from PySide6.QtWidgets import QDateEdit, QLabel, QTableWidget

    ekran = _ekran([_ogrenci(1, "Ali")])
    ekran.tablo.selectRow(0)
    bulgu = {}

    def istek(metot, url, **kw):
        return _yanit({"ogrenci_id": 1, "toplam_puan": toplam, "faaliyetler": faaliyetler})

    def exec_(dialog):
        bulgu["dialog"] = dialog
        bulgu["baslik"] = [e.text() for e in dialog.findChildren(QLabel) if e.objectName() == "formBaslik"]
        bulgu["toplam"] = next(e.text() for e in dialog.findChildren(QLabel) if e.objectName() == "puanKart")
        tablo = dialog.findChildren(QTableWidget)[0]
        bulgu["tablo"] = tablo
        bulgu["basliklar"] = [tablo.horizontalHeaderItem(i).text() for i in range(tablo.columnCount())]
        bulgu["satirlar"] = [[tablo.item(r, c).text() for c in range(tablo.columnCount())] for r in range(tablo.rowCount())]
        bulgu["bos"] = next(e for e in dialog.findChildren(QLabel) if e.objectName() == "bosMesaj")
        bulgu["tarihler"] = dialog.findChildren(QDateEdit)
        if olay:
            olay(dialog, bulgu)
        return 0

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek), patch.object(modul.QDialog, "exec", exec_):
        ekran.detay_ac()
    return ekran, bulgu


def test_detay_penceresi_ogrenci_toplam_ve_faaliyetleri_gosterir(tkys_qapplication):
    _, bulgu = _detay_incele(FAALIYETLER, 13)
    assert bulgu["baslik"] == ["Ali • 23100001"]
    assert bulgu["toplam"] == "Toplam Puan: 13"
    assert bulgu["basliklar"] == ["TARİH", "FAALİYET", "ADET", "BİRİM", "BİRİM PUAN", "TOPLAM PUAN"]
    assert bulgu["satirlar"][0] == ["20.11.2026", "Danışma masası nöbeti", "4", "Saat", "2.5", "10.0"]
    assert len(bulgu["satirlar"]) == 2 and bulgu["bos"].isHidden()
    assert len(bulgu["tarihler"]) == 2                                                     # başlangıç ve bitiş


def test_detay_penceresi_kayit_yoksa_bos_mesaj_gosterir(tkys_qapplication):
    _, bulgu = _detay_incele([], 0)
    assert bulgu["toplam"] == "Toplam Puan: 0" and bulgu["satirlar"] == []
    assert not bulgu["bos"].isHidden() and "faaliyet kaydı bulunamadı" in bulgu["bos"].text()
    assert bulgu["tablo"].isHidden()


def test_detay_penceresi_gecersiz_aralikta_temizlenir(tkys_qapplication):
    def olay(dialog, bulgu):
        baslangic, bitis = bulgu["tarihler"]
        baslangic.setDate(bitis.date().addDays(3))                                         # başlangıç bitişten sonra
        bulgu["toplam_sonra"] = next(e.text() for e in dialog.findChildren(modul.QLabel) if e.objectName() == "puanKart")
        bulgu["satir_sonra"] = bulgu["tablo"].rowCount()

    _, bulgu = _detay_incele(FAALIYETLER, 13, olay)
    assert bulgu["toplam_sonra"] == "Toplam Puan: —" and bulgu["satir_sonra"] == 0


def test_detay_penceresi_kapaninca_silinmek_uzere_isaretlenir(tkys_qapplication):
    """Pencere sayfanın çocuğu olarak bellekte kalmaz: kapanınca silinmek üzere işaretlenir (bellek ve çıkış güvenliği)."""
    ekran = _ekran([_ogrenci(1, "Ali")])
    ekran.tablo.selectRow(0)
    silinen = []

    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit({"ogrenci_id": 1, "toplam_puan": 0, "faaliyetler": []})), \
            patch.object(modul.QDialog, "exec", lambda dialog: 0), \
            patch.object(modul.QDialog, "deleteLater", lambda dialog: silinen.append(dialog)):
        ekran.detay_ac()
    assert len(silinen) == 1 and silinen[0].windowTitle() == "Öğrenci Detayı ve Faaliyet Puanları"
