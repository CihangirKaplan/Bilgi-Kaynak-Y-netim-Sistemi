"""Cihaz Raporları sayfası: Cihaz Rezervasyon ve Geciken Bakım Planı raporları ek sekme olarak, menüde ayrı madde olarak değil."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

import client.main_window as ana
import test_rapor_bakim_plani as tb
import test_rapor_sayfalari as tr
from client.cihaz_raporlari_ekrani import CihazRaporlariEkrani

SEKMELER = ["Bakım Geçmişi", "Kalibrasyon", "Arızalar", "Cihaz Rezervasyonu", "Geciken Bakım Planları"]


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _bos_istek(yontem, url, **k):
    y = MagicMock()
    y.status_code = 200
    y.json.return_value = [] if url.endswith("/api/cihazlar") else {"bakim_ozeti": {}, "bakimlar": [], "kalibrasyonlar": [], "arizalar": [], "ozet": {}}
    return y


def _sayfa():
    with patch("client.cihaz_raporlari_ekrani.oturum_kontrollu_istek", _bos_istek), \
         patch("client.cihaz_raporlari_ekrani.oturum_hatasi_mi", return_value=False):
        e = CihazRaporlariEkrani("http://x", "t")
    e.resize(1400, 800)
    e.show()
    QApplication.processEvents()
    return e


def _rapor_istekleri(url_sonu_bakim="/api/bakim-plani-raporu", url_sonu_rez="/api/cihaz-rezervasyon-raporu"):
    kayit = []
    bakim = tr.sahte_istek(tb.VERI, kayit)
    rez = tr.sahte_istek(tr.CIHAZ, kayit)

    def istek(yontem, url, **k):
        return (bakim if "bakim-plani" in url else rez)(yontem, url, **k)
    return istek, kayit


def test_sayfada_bes_sekme_var_ve_ek_sekmeler_ilk_acilista_istek_atmaz(qt_app):
    e = _sayfa()
    assert [e.rapor_sekmeleri.tabText(i) for i in range(e.rapor_sekmeleri.count())] == SEKMELER
    assert e.ek_sekme_ekrani("Cihaz Rezervasyonu") is None and e.ek_sekme_ekrani("Geciken Bakım Planları") is None    # tembel
    assert e.ust_alan.isVisible()
    e.close()


def test_ek_sekme_secilince_ekran_olusur_ust_suzgec_ve_kartlar_gizlenir_geri_donunce_gorunur(qt_app):
    e = _sayfa()
    istek, kayit = _rapor_istekleri()
    with patch("client.rapor_sayfasi_taban.oturum_kontrollu_istek", istek), \
         patch("client.rapor_sayfasi_taban.oturum_hatasi_mi", return_value=False), \
         patch("client.cihaz_rezervasyon_raporu_ekrani.oturum_kontrollu_istek", istek), \
         patch("client.cihaz_rezervasyon_raporu_ekrani.oturum_hatasi_mi", return_value=False):
        e.rapor_sekmeleri.setCurrentIndex(3)
        rez = e.ek_sekme_ekrani("Cihaz Rezervasyonu")
        assert rez is not None and not e.ust_alan.isVisible()
        assert rez.kartlar["rezervasyon"][0].text() == "2" and rez.tablolar["cihaz"].rowCount() == 2     # kendi verisi geldi
        e.rapor_sekmeleri.setCurrentIndex(4)
        plan = e.ek_sekme_ekrani("Geciken Bakım Planları")
        assert plan is not None and plan is not rez and not e.ust_alan.isVisible()
        assert plan.tablolar["geciken"].rowCount() == len(tb.VERI["geciken"])
        onceki = len(kayit)
        e.rapor_sekmeleri.setCurrentIndex(3)                                  # yeniden seçilince güncel veriyle yenilenir
        assert len(kayit) > onceki and e.ek_sekme_ekrani("Cihaz Rezervasyonu") is rez
        e.rapor_sekmeleri.setCurrentIndex(0)
        assert e.ust_alan.isVisible()                                         # bakım sekmesinde süzgeç ve kartlar geri gelir
    e.close()


def test_menude_ayri_rapor_maddeleri_yok_cihaz_raporlari_var():
    adlar = [oge["ad"] for _, ogeler in ana.MENU for oge in ogeler]
    assert "Cihaz Raporları" in adlar
    assert "Cihaz Rezervasyon Raporu" not in adlar and "Geciken Bakım Planı Raporu" not in adlar
