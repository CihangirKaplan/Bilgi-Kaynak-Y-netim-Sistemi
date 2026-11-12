"""TKYS mesaj kutularının Türkçe buton testleri."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from turkce_mesaj_kutusu import bilgi, uyari, hata, soru


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("fonksiyon", [bilgi, uyari, hata])
def test_tamam_butonu_turkce(qt_app, fonksiyon):
    olusturulan = []

    def sahte_exec(kutu):
        olusturulan.append(kutu)
        assert kutu.button(QMessageBox.Ok).text() == "Tamam"
        return QMessageBox.Ok

    with patch.object(QMessageBox, "exec", new=sahte_exec):
        sonuc = fonksiyon(None, "Bilgi", "Test mesajı")

    assert len(olusturulan) == 1
    assert sonuc == QMessageBox.Ok


@pytest.mark.parametrize("secim", [QMessageBox.Yes, QMessageBox.No])
def test_evet_hayir_butonlari_ve_sonuc(qt_app, secim):

    def sahte_exec(kutu):
        assert kutu.button(QMessageBox.Yes).text() == "Evet"
        assert kutu.button(QMessageBox.No).text() == "Hayır"
        assert kutu.defaultButton() == kutu.button(QMessageBox.No)
        return secim

    with patch.object(QMessageBox, "exec", new=sahte_exec):
        sonuc = soru(
            None,
            "Silme Onayı",
            "Silinsin mi?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

    assert sonuc == secim
