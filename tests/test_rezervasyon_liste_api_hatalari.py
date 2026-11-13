"""Rezervasyon listesi API hata yönetimi regresyon testleri."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from PySide6.QtWidgets import QApplication, QMessageBox

import cihaz_rezervasyon_ekranlari as modul


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def yanit(durum, veri=None):
    return SimpleNamespace(
        status_code=durum,
        json=lambda: veri,
    )


@pytest.mark.parametrize("durum, beklenen", [
    (403, "yetkiniz"),
    (500, "Sunucuda bir hata"),
])
def test_rezervasyon_listesi_http_hatasi(qt_app, durum, beklenen):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(durum),
    ), patch("cihaz_rezervasyon_ekranlari.QMessageBox.warning") as uyari:
        ekran = modul.RezervasyonYonetimEkrani(
            "http://testserver", "TOKEN"
        )

    uyari.assert_called_once()
    assert beklenen in uyari.call_args.args[2]
    ekran.close()


def test_rezervasyon_listesi_baglanti_hatasi(qt_app):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        side_effect=requests.exceptions.ConnectionError("Gizli detay"),
    ), patch("cihaz_rezervasyon_ekranlari.QMessageBox.warning") as uyari:
        ekran = modul.RezervasyonYonetimEkrani(
            "http://testserver", "TOKEN"
        )

    uyari.assert_called_once()
    assert "Sunucuya bağlanılamadı" in uyari.call_args.args[2]
    assert "Gizli detay" not in uyari.call_args.args[2]
    ekran.close()


def test_rezervasyon_listesi_bos_yanit(qt_app):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(200, []),
    ), patch("cihaz_rezervasyon_ekranlari.QMessageBox.warning") as uyari:
        ekran = modul.RezervasyonYonetimEkrani(
            "http://testserver", "TOKEN"
        )

    assert ekran.tablo.rowCount() == 0
    uyari.assert_not_called()
    ekran.close()


def test_yenileme_hatasinda_mevcut_rezervasyonlar_korunur(qt_app):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(200, []),
    ):
        ekran = modul.RezervasyonYonetimEkrani(
            "http://testserver", "TOKEN"
        )

    ekran.tablo.setRowCount(1)

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(500),
    ), patch("cihaz_rezervasyon_ekranlari.QMessageBox.warning") as uyari:
        ekran.verileri_yukle()

    assert ekran.tablo.rowCount() == 1
    uyari.assert_called_once()
    ekran.close()
