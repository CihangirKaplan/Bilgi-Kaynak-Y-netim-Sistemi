"""TKYS CAPTCHA giris ekrani kalite testleri."""

from unittest.mock import Mock, patch

import pytest
import requests

from PySide6.QtWidgets import QApplication

from captcha_servisi import _gorsel_uret
from login_ekrani import LoginEkrani


@pytest.fixture(scope="module")
def qapp():
    uygulama = QApplication.instance()
    if uygulama is None:
        uygulama = QApplication([])
    yield uygulama


def captcha_cevabi(kimlik):
    cevap = Mock()
    cevap.status_code = 200
    cevap.json.return_value = {
        "captcha_id": kimlik,
        "gorsel_base64": _gorsel_uret("73942"),
        "gecerlilik_saniye": 120,
    }
    return cevap


def ekran_kapat(ekran):
    ekran.captcha_sure_timer.stop()
    ekran.close()


def test_captcha_yuklenince_zamanlayici_baslar(qapp):
    with patch(
        "login_ekrani.requests.get",
        return_value=captcha_cevabi("a" * 32),
    ) as getir:

        ekran = LoginEkrani()

        try:
            qapp.processEvents()

            assert getir.call_count == 1
            assert ekran.captcha_id == "a" * 32
            assert ekran.captcha_sure_timer.isActive()
            assert ekran.captcha_sure_timer.interval() == 110000
            assert ekran.captcha_input.isEnabled()
            assert not ekran.captcha_resim.pixmap().isNull()

        finally:
            ekran_kapat(ekran)


def test_sure_dolunca_captcha_yenilenir(qapp):
    with patch(
        "login_ekrani.requests.get",
        side_effect=[
            captcha_cevabi("a" * 32),
            captcha_cevabi("b" * 32),
        ],
    ) as getir:

        ekran = LoginEkrani()

        try:
            qapp.processEvents()

            assert ekran.captcha_id == "a" * 32

            ekran.captcha_input.setText("73942")

            # 110 saniye beklemeden timer olayini tetikle.
            ekran.captcha_sure_timer.timeout.emit()

            assert getir.call_count == 2
            assert ekran.captcha_id == "b" * 32
            assert ekran.captcha_input.text() == ""
            assert ekran.captcha_sure_timer.isActive()

        finally:
            ekran_kapat(ekran)


def test_login_hiz_siniri_hesabi_kilitlemez(qapp):
    login_cevabi = Mock()
    login_cevabi.status_code = 429
    login_cevabi.headers = {
        "Retry-After": "60",
        "X-TKYS-RateLimit": "1",
    }
    login_cevabi.text = '{"detail": "Çok fazla istek."}'
    login_cevabi.json.return_value = {
        "detail": "Çok fazla istek."
    }

    with (
        patch(
            "login_ekrani.requests.get",
            return_value=captcha_cevabi("a" * 32),
        ) as getir,
        patch(
            "login_ekrani.requests.post",
            return_value=login_cevabi,
        ) as post,
    ):
        ekran = LoginEkrani()

        try:
            qapp.processEvents()
            ekran.show()
            qapp.processEvents()

            ekran.kullanici_input.setText("test_kullanici")
            ekran.sifre_input.setText("test_parola")
            ekran.captcha_input.setText("73942")

            ekran.giris_yap()

            assert post.call_count == 1
            assert ekran.kalan == 0
            assert ekran.captcha_id == "a" * 32
            assert getir.call_count == 1
            assert "Çok fazla giriş isteği" in ekran.hata_lbl.text()

            gonderilen = post.call_args.kwargs["json"]
            assert gonderilen["captcha_id"] == "a" * 32
            assert gonderilen["guvenlik_kodu"] == "73942"

        finally:
            ekran_kapat(ekran)


def test_captcha_hiz_siniri_uyarisi(qapp):
    cevap = Mock()
    cevap.status_code = 429
    cevap.headers = {"Retry-After": "45"}
    cevap.raise_for_status.side_effect = requests.HTTPError(
        response=cevap
    )

    with patch(
        "login_ekrani.requests.get",
        return_value=cevap,
    ):
        ekran = LoginEkrani()

        try:
            qapp.processEvents()

            assert ekran.captcha_id is None
            assert not ekran.giris_btn.isEnabled()
            assert not ekran.captcha_input.isEnabled()
            assert "45 saniye" in ekran.hata_lbl.text()

        finally:
            ekran_kapat(ekran)
