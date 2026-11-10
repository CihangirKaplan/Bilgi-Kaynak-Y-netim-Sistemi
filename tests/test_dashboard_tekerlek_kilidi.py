"""Tablo/bildirim kutusu uçlarına gelince fare tekerleği ana ekranı kaydırmamalı; kaydırılamayan tabloda ise sayfaya geçmeli."""
from unittest.mock import patch

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget

from dashboard_ekrani import DashboardEkrani, KaydirmaKilitliAlan, KaydirmaKilitliTablo


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def tekerlek(widget, delta):
    """Gerçek bir tekerlek olayı gönderir ve widget'ın kabul edip etmediğini döndürür."""
    merkez = QPointF(widget.width() / 2, widget.height() / 2)
    olay = QWheelEvent(merkez, widget.mapToGlobal(merkez), QPoint(0, 0), QPoint(0, delta), Qt.NoButton,
                       Qt.NoModifier, Qt.NoScrollPhase, False)
    olay.ignore()
    QApplication.sendEvent(widget.viewport(), olay)
    return olay.isAccepted()


def tablo(satir, kaydirilabilir):
    t = KaydirmaKilitliTablo(satir, 1)
    t.setFixedHeight(100)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn if kaydirilabilir else Qt.ScrollBarAlwaysOff)
    return t


def test_kaydirilabilir_tabloda_en_alta_gelince_olay_sayfaya_gecmez(qt_app):
    t = tablo(30, True)
    t.show()
    t.verticalScrollBar().setValue(t.verticalScrollBar().maximum())
    assert tekerlek(t, -120) is True                    # zaten en altta, aşağı daha: tabloda kalır
    t.verticalScrollBar().setValue(0)
    assert tekerlek(t, 120) is True                     # en üstte, yukarı daha: tabloda kalır
    t.close()


def test_kaydirilabilir_tabloda_ortada_normal_kayar(qt_app):
    t = tablo(30, True)
    t.show()
    onceki = t.verticalScrollBar().value()
    assert tekerlek(t, -120) is True
    assert t.verticalScrollBar().value() > onceki
    t.close()


def test_kaydirilamayan_tabloda_olay_sayfaya_birakilir(qt_app):
    t = tablo(2, False)
    t.show()
    assert tekerlek(t, -120) is False                   # sayfa normal kayabilsin
    t.close()


def test_bildirim_kutusu_uca_gelince_olay_sayfaya_gecmez(qt_app):
    ic = QWidget()
    ic_lay = QVBoxLayout(ic)
    for _ in range(40):
        ic_lay.addWidget(QWidget())
    alan = KaydirmaKilitliAlan()
    alan.setWidgetResizable(True)
    alan.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    alan.setWidget(ic)
    alan.setFixedHeight(120)
    alan.show()
    alan.verticalScrollBar().setValue(alan.verticalScrollBar().maximum())
    assert tekerlek(alan, -120) is True                 # en altta, aşağı daha: kutuda kalır
    alan.verticalScrollBar().setValue(0)
    assert tekerlek(alan, 120) is True
    alan.close()


def test_bildirim_kutusu_kaydirilamazsa_olay_sayfaya_birakilir(qt_app):
    alan = KaydirmaKilitliAlan()
    alan.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    alan.setWidget(QWidget())
    alan.show()
    assert tekerlek(alan, -120) is False
    alan.close()


def test_dashboardun_tablolari_ve_bildirim_kutusu_kilitli_siniflardir(qt_app):
    with patch.object(DashboardEkrani, "_getir", side_effect=lambda yol: {} if "ozet" in yol else []):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    p.zamanlayici.stop()
    for t in (p.tablo_randevu, p.tablo_rez, p.tablo_islem):
        assert isinstance(t, KaydirmaKilitliTablo)
    p.close()


def test_dashboardun_cok_bildirimli_kutusu_kilitli_alandir(qt_app):
    islemler = [{"cihaz_adi": f"E{i} - Cihaz", "islem_turu": "Bakım", "kalan_gun": -i, "tarih": "01.01.2026"}
                for i in range(9)]

    def getir(yol):
        return {"/api/dashboard/ozet": {}, "/api/dashboard/yaklasan-islemler": islemler}.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=True)
    p.zamanlayici.stop()
    alan = p.findChild(QScrollArea, "bildirimKaydirma")
    assert alan is not None and isinstance(alan, KaydirmaKilitliAlan)
    p.close()
