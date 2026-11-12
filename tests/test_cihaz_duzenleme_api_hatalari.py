"""Cihaz düzenleme listesi API hata testleri."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

import cihaz_ekranlari as modul


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def yanit(durum, veri=None):
    return SimpleNamespace(
        status_code=durum,
        json=lambda: veri,
        _tkys_oturum_reddedildi=False,
    )


@pytest.mark.parametrize("durum,mesaj", [
    (403, "yetkiniz"),
    (500, "Sunucuda bir hata"),
])
def test_http_hatasi_ekranda_gosterilir(qt_app, durum, mesaj):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(durum),
    ):
        ekran = modul.CihazDuzenlemeListesi("http://testserver", "TOKEN")

    assert ekran.tablo.rowCount() == 0
    assert mesaj in ekran.lbl_yukleme_hatasi.text()
    assert not ekran.lbl_yukleme_hatasi.isHidden()
    ekran.close()


def test_bos_liste_hata_olarak_gosterilmez(qt_app):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(200, []),
    ):
        ekran = modul.CihazDuzenlemeListesi("http://testserver", "TOKEN")

    assert ekran.tablo.rowCount() == 0
    assert "Henüz cihaz kaydı" in ekran.lbl_yukleme_hatasi.text()
    ekran.close()


def test_gecersiz_200_yaniti_yakalanir(qt_app):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(200, {"hata": "beklenmeyen veri"}),
    ):
        ekran = modul.CihazDuzenlemeListesi("http://testserver", "TOKEN")

    assert ekran.tablo.rowCount() == 0
    assert not ekran.lbl_yukleme_hatasi.isHidden()
    ekran.close()
