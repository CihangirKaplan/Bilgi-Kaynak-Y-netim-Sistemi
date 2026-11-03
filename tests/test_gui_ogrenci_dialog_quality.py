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


@pytest.mark.parametrize(
    "gecersiz_rol",
    ["tanimsiz", "", None, 123],
)
def test_gui_gecersiz_rol_reddedilir(qt_app, gecersiz_rol):
    from main_window import AnaPencere

    with pytest.raises(ValueError, match="Geçersiz kullanıcı rolü"):
        AnaPencere(aktif_rol=gecersiz_rol)


def test_gui_rol_belirtilmeden_acilamaz(qt_app):
    from main_window import AnaPencere

    with pytest.raises(ValueError, match="Geçersiz kullanıcı rolü"):
        AnaPencere()


def test_gui_login_beklenmeyen_hata_ayrintisi_gizlenir():
    from unittest.mock import MagicMock, patch
    import login_ekrani as modul

    ekran_sinifi = next(
        sinif
        for sinif in vars(modul).values()
        if isinstance(sinif, type)
        and sinif.__module__ == modul.__name__
        and "giris_yap" in vars(sinif)
    )

    ekran = MagicMock()
    ekran.kalan = 0
    ekran.kullanici_input.text.return_value = "qa_test"
    ekran.sifre_input.text.return_value = "test_parolasi"

    with patch(
        "login_ekrani.requests.post",
        side_effect=RuntimeError("QA001_GIZLI_TEKNIK_AYRINTI")
    ):
        ekran_sinifi.giris_yap(ekran)

    ekran.hata_goster.assert_called_once()
    mesaj = ekran.hata_goster.call_args.args[0]

    assert "QA001_GIZLI_TEKNIK_AYRINTI" not in mesaj
    assert "Giriş işlemi tamamlanamadı" in mesaj


def test_gui_login_zaman_asimi_mesaji():
    from unittest.mock import MagicMock, patch
    import requests
    import login_ekrani as modul

    ekran_sinifi = next(
        sinif
        for sinif in vars(modul).values()
        if isinstance(sinif, type)
        and sinif.__module__ == modul.__name__
        and "giris_yap" in vars(sinif)
    )

    ekran = MagicMock()
    ekran.kalan = 0
    ekran.kullanici_input.text.return_value = "qa_test"
    ekran.sifre_input.text.return_value = "test_parolasi"

    with patch(
        "login_ekrani.requests.post",
        side_effect=requests.exceptions.Timeout()
    ):
        ekran_sinifi.giris_yap(ekran)

    ekran.hata_goster.assert_called_once_with(
        "Sunucu yanıt vermedi. Lütfen tekrar deneyin."
    )
