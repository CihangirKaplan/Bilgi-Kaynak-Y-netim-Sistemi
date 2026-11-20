"""Sıralamanın gerçek ekranlarda (başlığa fare tıklamasıyla) çalıştığını doğrular."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "acceptance"))

from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import client.cihaz_ekranlari as envanter
import test_liste_excel as ortak


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def tikla(tablo, sutun):
    """Başlığa gerçek fare tıklaması gönderir."""
    h = tablo.horizontalHeader()
    x = h.sectionViewportPosition(sutun) + h.sectionSize(sutun) // 2
    QTest.mouseClick(h.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(x, h.height() // 2))


def sutun_metni(tablo, sutun):
    return [tablo.item(s, sutun).text() for s in range(tablo.rowCount())]


def test_cihaz_envanteri_basliga_tiklayinca_siralanir_rozet_ve_arama_uyumlu():
    ekran = ortak._envanter()
    ekran.show()
    tikla(ekran.tablo, 1)                                         # CİHAZ ADI
    assert sutun_metni(ekran.tablo, 1) == ["EEG", "Monitör", "TMS"]
    tikla(ekran.tablo, 1)
    assert sutun_metni(ekran.tablo, 1) == ["TMS", "Monitör", "EEG"]
    tikla(ekran.tablo, 4)                                         # DURUM: yalnızca rozet metni var
    assert sutun_metni(ekran.tablo, 0) == ["E-2", "E-3", "E-1"]   # Arızalı, Kullanıma Hazır, Kullanıma Hazır
    ekran.arama.setText("tms")                                    # arama sıralamadan sonra doğru satırı gösterir
    assert [ekran.tablo.item(s, 0).text() for s in range(3) if not ekran.tablo.isRowHidden(s)] == ["E-2"]
    ekran.close()


def test_cihaz_envanteri_yenileyince_sira_ve_ok_sifirlanir_excel_sirayi_izler(tmp_path):
    ekran = ortak._envanter()
    tikla(ekran.tablo, 1)
    assert ekran.tablo.horizontalHeader().isSortIndicatorShown()
    assert [c["envanter_kodu"] for c in ekran.gorunen_cihazlar()] == ["E-1", "E-3", "E-2"]   # Excel ekrandaki sırayı izler
    with patch.object(envanter, "oturum_kontrollu_istek", return_value=ortak._yanit(ortak.CIHAZLAR)):
        ekran.verileri_yukle()
    assert sutun_metni(ekran.tablo, 0) == ["E-1", "E-2", "E-3"]   # sunucu sırası
    assert not ekran.tablo.horizontalHeader().isSortIndicatorShown()
    ekran.close()


def test_ogrenci_tablosu_sirali_ve_excel_ayni_sirada(tmp_path):
    ekran = ortak._ogrenci_ekrani()
    tikla(ekran.tablo, 1)                                         # Öğrenci No: 77, 0012 -> sayı gibi: 12, 77
    assert sutun_metni(ekran.tablo, 1) == ["0012", "77"]
    tikla(ekran.tablo, 1)
    assert sutun_metni(ekran.tablo, 1) == ["77", "0012"]
    ekran.close()


def test_danisan_tablosu_sirali_kod_ve_randevu_sayisi():
    import test_danisanlar_ekrani as dt
    dt.AKTIF.clear()
    sunucu = dt.Sunucu()
    dt.AKTIF["s"] = sunucu
    with patch.object(dt.modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(dt.rmodul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran = dt.DanisanlarEkrani("http://testserver", "TOKEN", 11)
        tikla(ekran.tablo, 4)                                     # Randevu sayısı: 0, 1, 4
        assert sutun_metni(ekran.tablo, 4) == ["0", "1", "4"]
        tikla(ekran.tablo, 4)
        assert sutun_metni(ekran.tablo, 4) == ["4", "1", "0"]
        secili_kod = ekran.tablo.item(0, 0).text()
        ekran.tablo.selectRow(0)
        assert (ekran.secili_danisan() or {}).get("danisan_kod_id") == secili_kod        # kimlik satırla birlikte
        ekran.close()
