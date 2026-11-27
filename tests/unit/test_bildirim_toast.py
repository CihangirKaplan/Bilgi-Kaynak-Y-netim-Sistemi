"""Başarı bildirimi (toast): görünür, ana pencereye bağlanır, kendiliğinden kaybolur, forma değil sahibine bağlanır."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMainWindow, QWidget

from client.bildirim_toast import basari_bildirimi


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _pencere():
    p = QMainWindow()
    p.resize(900, 600)
    p.show()
    return p


def test_toast_ana_pencerenin_altinda_ortada_gorunur():
    p = _pencere()
    t = basari_bildirimi(p, "Kaydedildi.")
    assert t.text() == "Kaydedildi." and t.isVisible() and t.parent() is p
    assert abs((t.x() + t.width() // 2) - p.width() // 2) <= 2
    assert t.y() + t.height() < p.height()
    p.close()


def test_toast_formdan_cagrilinca_formun_sahibi_pencereye_baglanir():
    ana = _pencere()
    form = QDialog(ana)                                               # form kapanınca bildirim kaybolmamalı
    t = basari_bildirimi(form, "Kayıt eklendi.")
    assert t.parent() is ana
    ana.close()


def test_yeni_bildirim_eskisinin_yerini_alir_ve_kendiliginden_kaybolur():
    p = _pencere()
    ilk = basari_bildirimi(p, "bir", sure_ms=30)
    ikinci = basari_bildirimi(p, "iki", sure_ms=30)
    QApplication.processEvents()
    assert p._tkys_toast is ikinci
    QTest.qWait(700)                                                  # 30 ms bekleme + 350 ms solma
    QApplication.processEvents()
    assert not [e for e in p.findChildren(QLabel, "tkysToast") if e.isVisible()]
    p.close()


def test_pencere_yoksa_hata_vermez():
    assert basari_bildirimi(None, "x") is None


def test_kendiliginden_silinmis_eski_bildirimden_sonra_yenisi_hata_vermez():
    """Önceki bildirim süresi dolup kendini silince, sonraki bildirim "Internal C++ object already deleted" hatası vermemeli
    (Oda Yönetimi'nde oda ekledikten sonra odayı silerken görülen "Bağlantı hatası" penceresi)."""
    from PySide6.QtCore import QCoreApplication, QEvent
    p = _pencere()
    ilk = basari_bildirimi(p, "Oda başarıyla eklendi.")
    ilk.deleteLater()                                                  # animasyon bitince olan: etiket silinir
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    yeni = basari_bildirimi(p, "Oda silindi.")                         # eskiden RuntimeError fırlatırdı
    assert yeni.text() == "Oda silindi." and yeni.isVisible()
    p.close()
