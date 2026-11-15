"""Açılan ikinci pencereler ana pencerenin sağ içerik alanının ortasında açılır (menü açık ya da dar)."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QDialog, QHBoxLayout, QMainWindow, QMenu, QWidget

import client.pencere_konumu as pencere_konumu


@pytest.fixture
def ana_pencere(tkys_qapplication):
    ana = QMainWindow()
    govde = QWidget()
    yerlesim = QHBoxLayout(govde)
    yerlesim.setContentsMargins(0, 0, 0, 0)
    yerlesim.setSpacing(0)
    ana.menu = QWidget()
    ana.menu.setFixedWidth(280)
    ana.icerik = QWidget()
    yerlesim.addWidget(ana.menu)
    yerlesim.addWidget(ana.icerik, 1)
    ana.setCentralWidget(govde)
    ana.resize(1000, 700)
    ana.show()
    pencere_konumu.ana_pencereyi_tanit(ana, lambda: ana.icerik)
    QApplication.processEvents()
    yield ana
    ana.close()


def _merkez(pencere):
    return pencere.frameGeometry().center()


def test_acilan_pencere_icerik_alaninin_ortasinda_acilir(ana_pencere):
    pencere = QDialog()
    pencere.resize(300, 200)
    pencere.show()
    QApplication.processEvents()
    alan = ana_pencere.icerik
    beklenen = alan.mapToGlobal(alan.rect().center())
    assert abs(_merkez(pencere).x() - beklenen.x()) <= 1 and abs(_merkez(pencere).y() - beklenen.y()) <= 1
    assert _merkez(pencere).x() > ana_pencere.frameGeometry().center().x()      # tüm pencerenin değil, sağ alanın ortası
    pencere.close()


def test_menu_daralinca_yeni_acilan_pencere_yeni_ortaya_gelir(ana_pencere):
    ana_pencere.menu.setFixedWidth(76)
    QApplication.processEvents()
    pencere = QDialog()
    pencere.resize(300, 200)
    pencere.show()
    QApplication.processEvents()
    alan = ana_pencere.icerik
    beklenen = alan.mapToGlobal(alan.rect().center())
    assert abs(_merkez(pencere).x() - beklenen.x()) <= 1
    pencere.close()


def test_boyutu_sonradan_degisen_pencere_yeniden_ortalanir(ana_pencere):
    pencere = QWidget()
    pencere.resize(300, 300)
    pencere.show()
    QApplication.processEvents()
    pencere.resize(300, 200)
    assert pencere_konumu.ortala(pencere)
    alan = ana_pencere.icerik
    beklenen = alan.mapToGlobal(alan.rect().center())
    assert abs(_merkez(pencere).y() - beklenen.y()) <= 1
    pencere.close()


def test_acilir_menu_ve_ana_pencere_tasinmaz(ana_pencere):
    menu = QMenu()
    assert not pencere_konumu.ortala(menu)                    # Popup türü
    assert not pencere_konumu.ortala(ana_pencere)             # ana pencerenin kendisi
    kapali = QDialog()
    kapali.setProperty("ortalama_kapali", True)
    assert not pencere_konumu.ortala(kapali)


def test_pencere_ekranin_disina_tasmaz(ana_pencere):
    pencere = QDialog()
    pencere.resize(5000, 5000)
    pencere.show()
    QApplication.processEvents()
    ekran = ana_pencere.screen().availableGeometry()
    assert pencere.frameGeometry().left() >= ekran.left() and pencere.frameGeometry().top() >= ekran.top()
    pencere.close()


def test_ana_pencere_gorunmezken_hicbir_sey_yapilmaz(tkys_qapplication):
    ana = QMainWindow()
    pencere_konumu.ana_pencereyi_tanit(ana)
    diyalog = QDialog()
    assert not pencere_konumu.ortala(diyalog)
