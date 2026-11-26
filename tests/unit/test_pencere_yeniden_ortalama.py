"""Açıldıktan sonra büyüyen pencere (ör. rol seçilince yetki özeti açılan form) yeniden ortalanır, ekranın altına taşmaz."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QWidget

from client.pencere_konumu import ana_pencereyi_tanit


def test_buyuyen_dialog_yeniden_ortalanir_ve_ekrana_sigar(tkys_qapplication):
    ana = QWidget()
    ana.resize(1000, 600)
    ana.show()
    ana_pencereyi_tanit(ana)
    d = QDialog(ana)
    d.resize(400, 200)
    d.show()
    for _ in range(5):
        QApplication.processEvents()
    ilk_ust = d.frameGeometry().y()
    d.resize(400, 560)
    for _ in range(5):
        QApplication.processEvents()
    g = d.frameGeometry()
    alan = d.screen().availableGeometry()
    assert g.y() < ilk_ust                                   # büyüdükçe yukarı kaydı (yalnızca aşağı uzamadı)
    assert g.bottom() <= alan.bottom() and g.top() >= alan.top()
    d.close(); ana.close()
