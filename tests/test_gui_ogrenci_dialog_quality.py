"""
TKYS QA-001 - PySide6 GUI testleri.
Gercek API veya PostgreSQL kullanilmaz.
"""

import os
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from ogrenci_dialog import OgrenciEkleDialog


@pytest.fixture(scope="module")
def qt_app():
    uygulama = QApplication.instance()
    if uygulama is None:
        uygulama = QApplication([])
    return uygulama


@pytest.fixture
def dialog(qt_app):
    pencere = OgrenciEkleDialog(
        "http://testserver",
        "QA001_TEST_TOKEN",
    )
    yield pencere
    pencere.close()


def test_gui_zorunlu_alanlar_bos(dialog):
    with (
        patch("ogrenci_dialog.requests.post") as post,
        patch("ogrenci_dialog.QMessageBox.warning") as uyari,
    ):
        dialog.kaydet_tiklandi()

    post.assert_not_called()
    uyari.assert_called_once()


def test_gui_ogrenci_numarasi_harf_iceremez(dialog):
    dialog.le_ad_soyad.setText("QA Test")
    dialog.le_ogrenci_no.setText("123ABC")

    with (
        patch("ogrenci_dialog.requests.post") as post,
        patch("ogrenci_dialog.QMessageBox.warning") as uyari,
    ):
        dialog.kaydet_tiklandi()

    post.assert_not_called()
    uyari.assert_called_once()


def test_gui_gecerli_ogrenci_kaydi(dialog):
    dialog.le_ad_soyad.setText("QA Test")
    dialog.le_ogrenci_no.setText("23100011036")
    dialog.le_telefon.setText("05551234567")
    dialog.cb_tur.setCurrentIndex(0)

    with (
        patch("ogrenci_dialog.requests.post") as post,
        patch("ogrenci_dialog.QMessageBox.information") as bilgi,
    ):
        post.return_value.status_code = 200

        dialog.kaydet_tiklandi()

    post.assert_called_once()

    args, kwargs = post.call_args

    assert args[0] == "http://testserver/api/ogrenci-ekle"
    assert kwargs["json"]["ogrenci_numarasi"] == "23100011036"
    assert kwargs["json"]["tur"] == "GONULLU"

    assert kwargs["headers"]["Authorization"] == (
        "Bearer QA001_TEST_TOKEN"
    )

    bilgi.assert_called_once()
    assert dialog.result() == QDialog.Accepted
