"""Küçük kullanım iyileştirmeleri: Kişi/telefon görünümü, Yönetim Raporları otomatik yükleme, tembel sayfa oluşturma."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QWidget

import client.main_window as ana
from client.gorunum_bicimleri import birim_goster, telefon_goster
from client.yonetim_raporlari_panel import YonetimRaporlariEkrani


def test_birim_adi_okunur_yazilir():
    assert birim_goster("KISI") == "Kişi" and birim_goster("saat") == "Saat"
    assert birim_goster("Özel Birim") == "Özel Birim" and birim_goster(None) == ""


@pytest.mark.parametrize("ham,beklenen", [
    ("5550000000", "0555 000 00 00"), ("05550000000", "0555 000 00 00"), ("(555) 000 00 00", "0555 000 00 00"),
    ("", "—"), (None, "—"), ("123", "123"), ("+905550000000", "+905550000000"),
])
def test_telefon_goruntusu(ham, beklenen):
    assert telefon_goster(ham) == beklenen


def test_yonetim_raporlari_tur_ve_donem_degisince_kendiliginden_yuklenir():
    with patch("client.yonetim_raporlari_panel.oturum_kontrollu_istek"):
        panel = YonetimRaporlariEkrani("http://x", "t")
    with patch.object(YonetimRaporlariEkrani, "raporu_yukle") as yukle:
        panel.rapor_turu.setCurrentIndex(1 if panel.rapor_turu.currentIndex() == 0 else 0)
        assert yukle.call_count == 1                                   # tür değişimi yükler
        yukle.reset_mock()
        hazir = next(m for m in (panel.donem.itemText(i) for i in range(panel.donem.count()))
                     if m not in ("Tarih Aralığı", panel.donem.currentText()))
        panel.donem.setCurrentText(hazir)
        assert yukle.call_count == 1                                   # hazır dönem yükler
        yukle.reset_mock()
        panel.donem.setCurrentText("Tarih Aralığı")
        assert yukle.call_count == 0                                   # özel aralıkta kullanıcı Yenile'ye basar
        panel.sayfa_gosterildi()
        assert yukle.call_count == 1                                   # sayfa açılınca yüklenir


def test_yonetim_raporlari_sayfa_acilinca_yenilenir_listede_kayitli():
    assert ana.AnaPencere.SAYFA_YENILEME["Yönetim Raporları ve İstatistikler"] == ("yonetim_raporlari_ekrani", "sayfa_gosterildi")


def test_sayfalar_ilk_acilista_kurulur_giriste_degil():
    pencere = ana.AnaPencere.__new__(ana.AnaPencere)
    kurulan = []
    pencere._bekleyen_sayfalar = {0: {"ad": "A"}}
    from PySide6.QtWidgets import QStackedWidget
    pencere.stack = QStackedWidget()
    pencere.stack.addWidget(QWidget())
    pencere.sayfa_modul = lambda oge: (kurulan.append(oge["ad"]), QWidget())[1]
    ilk = pencere.stack.widget(0)
    pencere._sayfayi_olustur(0)
    pencere._sayfayi_olustur(0)                                        # ikinci çağrı tekrar kurmaz
    assert kurulan == ["A"] and pencere.stack.widget(0) is not ilk and pencere.stack.count() == 1


def test_bakim_plani_durum_sutunu_uzun_metni_kesmez():
    from PySide6.QtWidgets import QLabel
    import client.bakim_plani_ekranlari as b
    from unittest.mock import MagicMock
    plan = {"plan_id": 1, "cihaz_id": 1, "envanter_kodu": "EEG-01", "cihaz_adi": "EEG", "gorev_turu": "Haftalık Şarj", "tur": "Bakım",
            "periyot_gun": 30, "uyari_suresi_gun": 7, "sonraki_gorev_tarihi": "2020-01-09", "kalan_gun": -123456, "durum": "Gecikmiş", "aktif_mi": True}
    yanit = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    yanit.json.return_value = [plan]
    with patch.object(b, "oturum_kontrollu_istek", return_value=yanit):
        ekran = b.BakimPlanlariEkrani("http://x", "T")
        ekran.resize(1100, 600)
        ekran.show()
        ekran.verileri_yukle()
    etiket = ekran.tablo.cellWidget(0, 5).findChild(QLabel)
    assert ekran.tablo.columnWidth(5) >= etiket.sizeHint().width()
    ekran.close()
