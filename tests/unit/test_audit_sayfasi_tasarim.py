"""Denetim Kayıtları sayfasının yeni tasarımı: tarih alanı yalnız tarih aralığında görünür, işlem etiketi, sayaç, ayrıntı açma.

Sunucu ve veri davranışları test_audit_sayfasi_duzeltmeleri.py'de; burada görünüm/etkileşim katmanı sınanır.
"""
import gc
import json
import weakref
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QPushButton

import client.audit_kayitlari_ekrani as modul
from client.sayfa_tema import DurumRozetiDelegate, VARSAYILAN_DURUM_RENGI

OZET = {"toplam_kayit": 120, "basarisiz_giris": 4, "kullanici_islemleri": 30, "bugunku_islemler": 2}


def _yanit(veri):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = veri
    m.text = json.dumps(veri)
    m._tkys_oturum_reddedildi = False
    m.raise_for_status = lambda: None
    return m


def _kayit(no, olay="LOGIN"):
    return {
        "denetim_id": no, "kullanici_id": 1, "kullanici_adi": f"kisi{no}", "olay_turu": olay, "hedef_tablo": "kullanicilar", "hedef_kayit_id": no,
        "olusturulma_tarihi": f"2026-11-24T10:0{no}:00", "ayrinti": None, "istemci_adresi": "10.0.0.1", "hedef_kullanici_adi": None,
    }


def _ekran(kayitlar):
    def istek(metot, url, **kw):
        return _yanit({"ozet": OZET if not kw["params"].get("offset") else None, "kayitlar": kayitlar})

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        return modul.AuditKayitlariEkrani("http://x", "t")


def test_tarih_alani_yalniz_tarih_araligi_secilince_gorunur(tkys_qapplication):
    ekran = _ekran([_kayit(1)])
    assert ekran.tarih_alani.isHidden()
    for hazir in ("Bugün", "Son 7 Gün", "Son 30 Gün"):
        ekran.donem_secimi.setCurrentText(hazir)
        assert ekran.tarih_alani.isHidden()
    assert ekran.bitis.date() == QDate.currentDate() and ekran.baslangic.date() == QDate.currentDate().addDays(-29)

    ekran.donem_secimi.setCurrentText("Tarih Aralığı")
    assert not ekran.tarih_alani.isHidden()
    ekran.donem_secimi.setCurrentText("Tümü")
    assert ekran.tarih_alani.isHidden()


def test_sayac_ozet_ve_hata_durumu(tkys_qapplication):
    ekran = _ekran([_kayit(i) for i in range(3)])
    assert ekran.sayac_rozeti.text() == "120 kayıt"
    assert ekran.ozet_degerleri["basarisiz_giris"].text() == "4"
    assert ekran.tablo.rowCount() == 3 and len(ekran._satir_kayitlari) == 3

    import requests
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=requests.ConnectionError("yok")):
        ekran.kayitlari_getir()
    assert ekran.sayac_rozeti.text() == "0 kayıt" and ekran.tablo.rowCount() == 0 and ekran._satir_kayitlari == []


def test_islem_etiketi_rengi_islem_kodundan_gelir_tanimsiz_gri(tkys_qapplication):
    ekran = _ekran([_kayit(1, "LOGIN_FAILED"), _kayit(2, "TANIMSIZ_OLAY")])
    delege = ekran.tablo.itemDelegateForColumn(2)
    assert isinstance(delege, modul.IslemEtiketiDelegate) and isinstance(delege, DurumRozetiDelegate)
    assert delege.renk_bul(ekran.tablo.model().index(0, 2), "x") == modul.OLAY_RENKLERI["LOGIN_FAILED"]
    assert delege.renk_bul(ekran.tablo.model().index(1, 2), "x") == VARSAYILAN_DURUM_RENGI
    assert ekran.tablo.item(0, 2).text() == "Başarısız Giriş"                                # hücre metni değişmedi

    ekran.resize(1100, 700)
    ekran.show()
    tkys_qapplication.processEvents()
    assert not ekran.tablo.viewport().grab().isNull()                                       # çizim hata vermez
    ekran.close()


def test_goruntule_dugmesi_ve_cift_tik_dogru_satirin_ayrintisini_acar(tkys_qapplication):
    ekran = _ekran([_kayit(1), _kayit(2), _kayit(3)])
    with patch.object(ekran, "_audit_detayini_goster") as goster:
        ekran.tablo.cellWidget(1, 4).findChildren(QPushButton)[0].click()
        kayit, tarih = goster.call_args.args
        assert kayit["denetim_id"] == 2 and tarih == "24.11.2026 10:02:00"

        goster.reset_mock()
        ekran.tablo.itemDoubleClicked.emit(ekran.tablo.item(2, 0))
        assert goster.call_args.args[0]["denetim_id"] == 3


def test_satir_bilgisi_yeni_sayfada_yenilenir(tkys_qapplication):
    ekran = _ekran([_kayit(i) for i in range(1, 4)])
    yeni = [_kayit(7), _kayit(8)]
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: _yanit({"ozet": OZET, "kayitlar": yeni})):
        ekran.kayitlari_getir()
    assert [k["denetim_id"] for k, _ in ekran._satir_kayitlari] == [7, 8]
    with patch.object(ekran, "_audit_detayini_goster") as goster:
        ekran.tablo.cellWidget(0, 4).findChildren(QPushButton)[0].click()
    assert goster.call_args.args[0]["denetim_id"] == 7                                       # eski sayfanın satırı değil


def test_sayfa_silinince_temizlenir_cikista_qt_cokmez(tkys_qapplication):
    """Düğme bağlantısında sayfayı tutan `lambda` kullanılırsa sayfa çöp toplayıcıya görünmeyen bir döngüde kalır ve süreç
    kapanırken Qt'yi çökertir (çıkış kodu 139)."""
    ekran = _ekran([_kayit(i) for i in range(1, 4)])
    referans = weakref.ref(ekran)
    del ekran
    gc.collect()
    assert referans() is None


def test_ayrinti_penceresi_aciklanir_kapat_dugmesi_var(tkys_qapplication):
    ekran = _ekran([_kayit(1, "UPDATE")])
    acilan = {}

    def sahte_exec(pencere):
        acilan["baslik"] = [e.text() for e in pencere.findChildren(modul.QLabel) if e.objectName() == "formBaslik"]
        acilan["alanlar"] = [e.text() for e in pencere.findChildren(modul.QLabel) if e.objectName() == "alanAdi"]
        acilan["kapat"] = [b.text() for b in pencere.findChildren(QPushButton)]
        return 0

    with patch.object(modul.QDialog, "exec", sahte_exec):
        ekran._ayrintiyi_ac(0)
    assert acilan["baslik"] == ["Denetim Kaydı Detayları"]
    assert "Tarih / Saat" in acilan["alanlar"] and "İşlem Türü" in acilan["alanlar"]
    assert acilan["kapat"] == ["Kapat"]


def test_islem_secici_yazisi_kenara_yapismaz(tkys_qapplication):
    """Düğmenin iç boşluğu (padding) çalışmalıdır: menü oku için konulan bir alt-öğe kuralı bile boşluğu sıfırlayıp yazıyı sol kenara
    yapıştırabiliyor (gerçek ekranda görüldü). Düğme çizdirilip ilk koyu (yazı) sütunu aranır; kenar çizgisi açık renktir."""
    secici = modul.CokluIslemSecici()
    secici.setStyleSheet(secici.styleSheet())
    secici.kutular["LOGIN"].setChecked(True)
    secici.kutular["VIEW"].setChecked(True)
    secici.resize(300, 42)
    secici.show()
    tkys_qapplication.processEvents()
    resim = secici.grab().toImage()
    ilk_koyu = next(
        x for x in range(resim.width())
        if any(resim.pixelColor(x, y).red() < 90 and resim.pixelColor(x, y).blue() < 130 for y in range(resim.height()))
    )
    assert ilk_koyu >= 12, ilk_koyu                                                          # padding 14 px: yazı kenardan uzakta başlar
    secici.close()


def test_ayrinti_penceresinde_etiket_ve_deger_ayni_hizada(tkys_qapplication):
    kayit = _kayit(1, "VIEW")
    kayit["ayrinti"] = {"ne": "denetim kayıtları görüntülendi", "neden": "Uzun bir açıklama " * 12}
    ekran = _ekran([kayit])
    kontrol = {}

    def sahte_exec(pencere):
        # Özet kartındaki rozet/cümle/zaman satırı ızgara dışındadır; ızgaradaki alan adı ve değer etiketleri karşılaştırılır.
        etiketler = [e for e in pencere.findChildren(modul.QLabel)
                     if e.objectName() not in ("formBaslik", "islemRozeti", "olayCumlesi", "ipucu")]
        kontrol["hepsi_ustten"] = all(e.alignment() & Qt.AlignTop for e in etiketler)
        kontrol["sayi"] = len(etiketler)
        return 0

    with patch.object(modul.QDialog, "exec", sahte_exec):
        ekran._ayrintiyi_ac(0)
    assert kontrol["sayi"] >= 10 and kontrol["hepsi_ustten"]                                 # alan adı da değeri de üstten hizalı

