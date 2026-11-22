"""Bakım ve kalibrasyon kayıtları için ayrı görüntüleme izni: menü, ekran ve izin eşlemesi."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

import client.cihaz_bakim_ekranlari as bakim_modulu
import client.cihaz_kalibrasyon_ekranlari as kalib_modulu
import client.main_window as mw


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()
    yield
    mw._SUNUCU_YETKILERI.clear()


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


def _gun(n):
    return (date.today() + timedelta(days=n)).isoformat()


def test_izin_eslemesi_gorunteleme_ve_yonetme_ayri_kodlar():
    assert mw.IZIN_KODLARI["Bakım kayıtlarını görüntüleme"] == ("BAKIM_KAYITLARI_GORUNTULE",)
    assert mw.IZIN_KODLARI["Kalibrasyon kayıtlarını görüntüleme"] == ("KALIBRASYON_KAYITLARI_GORUNTULE",)
    assert mw.IZIN_KODLARI["Bakım kayıtlarını yönetme"] == ("BAKIM_KAYITLARI_YONET",)
    menu = {oge["ad"]: oge for _, ogeler in mw.MENU for oge in ogeler}
    assert menu["Bakım Kayıtları"]["izin"] == "Bakım kayıtlarını görüntüleme" and menu["Kalibrasyon"]["izin"] == "Kalibrasyon kayıtlarını görüntüleme"
    assert menu["Bakım Kayıtları"]["aksiyon"] == [("＋  Bakım Kaydı", "Bakım kayıtlarını yönetme")]          # ekleme düğmesi yönetme izni ister


def test_yalniz_goruntuleme_izni_sayfayi_acar_ama_yonetme_vermez():
    mw.yetkileri_ayarla("memur", ["BAKIM_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_GORUNTULE"])
    ana = SimpleNamespace(aktif_rol="memur")
    assert mw.AnaPencere._sayfa_izinli_mi(ana, "Bakım Kayıtları") and mw.AnaPencere._sayfa_izinli_mi(ana, "Kalibrasyon")
    assert not mw.izin_var("memur", "Bakım kayıtlarını yönetme") and not mw.izin_var("memur", "Kalibrasyon kayıtlarını yönetme")
    mw.yetkileri_ayarla("memur", ["BAKIM_KAYITLARI_YONET"])                                   # yalnız yönetme: sayfa menüde yok (görüntüleme şart)
    assert not mw.AnaPencere._sayfa_izinli_mi(ana, "Bakım Kayıtları")


BAKIMLAR = [{"bakim_id": 7, "cihaz_adi": "E-1 - EEG", "bakim_yapan_kisi": "Ece", "yapilan_islem": "Filtre", "maliyet": 100,
             "bakim_baslangic_tarihi": _gun(-30), "bakim_bitis_tarihi": _gun(-30), "bakim_tarihi": _gun(-30), "sonraki_bakim_tarihi": _gun(30), "uyari_suresi_gun": 7}]
KALIBRASYONLAR = [{"kalibrasyon_id": 3, "cihaz_adi": "E-1 - EEG", "kalibrasyon_yapan_kurum": "K", "sertifika_no": "C-1",
                   "kalibrasyon_baslangic_tarihi": _gun(-100), "kalibrasyon_bitis_tarihi": _gun(-100), "gecerlilik_tarihi": _gun(265), "uyari_suresi_gun": 30}]


def _ac(modul, sinif, veri, **k):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(veri)):
        e = getattr(modul, sinif)("http://x", "t", **k)
    e.resize(1400, 400)
    e.show()
    QApplication.processEvents()
    return e


@pytest.mark.parametrize("modul,sinif,veri,sutun", [(bakim_modulu, "BakimYonetimEkrani", BAKIMLAR, 7), (kalib_modulu, "KalibrasyonYonetimEkrani", KALIBRASYONLAR, 6)])
def test_yetkisiz_gorunum_duzenle_sil_dugmesi_ve_cift_tikla_duzenleme_yok(modul, sinif, veri, sutun):
    e = _ac(modul, sinif, veri, yetkili_mi=False)
    assert e.tablo.rowCount() == 1 and e.tablo.isColumnHidden(sutun) and e.tablo.cellWidget(0, sutun) is None
    from client.tablo_tasarimi import satir_kimligi
    assert satir_kimligi(e.tablo, 0) is None                                  # kimlik atanmadığı için çift tıklayınca düzenleme açılmaz
    e.close()
    e = _ac(modul, sinif, veri)                                               # varsayılan: yetkili
    assert not e.tablo.isColumnHidden(sutun) and e.tablo.cellWidget(0, sutun) is not None and satir_kimligi(e.tablo, 0) is not None
    e.close()
