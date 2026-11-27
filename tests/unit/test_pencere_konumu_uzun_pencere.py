"""Ekranı neredeyse dolduran pencere, ekranın dikey ortasına yerleşir (üstte ve altta eşit boşluk); küçük pencereler eskisi gibi içerik alanının ortasına."""
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from client import pencere_konumu


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _kur(ana_yuk, dialog_yuk):
    ana = QWidget()
    ana.setGeometry(0, 0, 400, ana_yuk)
    ana.show()
    QApplication.processEvents()
    pencere_konumu.ana_pencereyi_tanit(ana, lambda: ana)
    d = QDialog(ana)
    d.resize(300, dialog_yuk)
    d.show()
    QApplication.processEvents()
    return ana, d


def test_uzun_pencere_ekranin_dikey_ortasina_yerlesir_ustte_ve_altta_esit_bosluk(qt_app):
    ekran = QApplication.primaryScreen().availableGeometry()
    ana, d = _kur(ana_yuk=120, dialog_yuk=int(ekran.height() * 0.85))      # ana pencere çok kısa: içerik alanı ortası ekranın üst tarafında
    pencere_konumu.ortala(d)
    cerceve = d.frameGeometry()
    ust, alt = cerceve.top() - ekran.top(), ekran.bottom() - cerceve.bottom()
    assert abs(ust - alt) <= 2 and ust > 0
    d.close(); ana.close()


def test_kisa_pencere_icerik_alaninin_ortasinda_kalir_ekrana_yapismaz(qt_app):
    ekran = QApplication.primaryScreen().availableGeometry()
    ana, d = _kur(ana_yuk=300, dialog_yuk=120)
    pencere_konumu.ortala(d)
    merkez_y = d.frameGeometry().center().y()
    assert abs(merkez_y - ana.mapToGlobal(ana.rect().center()).y()) <= 2          # kısa pencere: eski davranış (ana pencerenin ortası)
    assert d.frameGeometry().height() < ekran.height() * 0.75
    d.close(); ana.close()
