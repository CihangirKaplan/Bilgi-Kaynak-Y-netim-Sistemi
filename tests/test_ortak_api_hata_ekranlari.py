"""Bakım, kalibrasyon ve plan formlarında cihaz yükleme hataları."""

from types import SimpleNamespace

import pytest
import requests
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QPushButton

import cihaz_bakim_ekranlari as bakim
import cihaz_kalibrasyon_ekranlari as kalibrasyon
import bakim_plani_ekranlari as plan


EKRANLAR = [
    (bakim, bakim.YeniBakimFormu, False),
    (kalibrasyon, kalibrasyon.YeniKalibrasyonFormu, False),
    (plan, plan.PlanFormu, True),
]


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(params=EKRANLAR, ids=["bakim", "kalibrasyon", "plan"])
def ekran(request, monkeypatch):
    modul, sinif, plan_mi = request.param

    # Formun tümünü açmadan yalnızca cihaz yükleme mantığını test et.
    nesne = SimpleNamespace(
        api_url="http://testserver",
        token="test-token",
        cmb_cihaz=QComboBox(),
        btn_kaydet=QPushButton("Kaydet"),
        lbl_cihaz_hatasi=QLabel(),
    )

    return modul, sinif, nesne, plan_mi, monkeypatch


def yanit_olustur(kod, veri=None, oturum_hatasi=False):
    return SimpleNamespace(
        status_code=kod,
        json=lambda: veri,
        _tkys_oturum_reddedildi=oturum_hatasi,
    )


@pytest.mark.parametrize("kod,mesaj", [
    (403, "yetkiniz"),
    (500, "Sunucuda bir hata"),
])
def test_http_hatasi_ekranda_gosterilir(ekran, kod, mesaj):
    modul, sinif, form, _, monkeypatch = ekran

    monkeypatch.setattr(
        modul,
        "oturum_kontrollu_istek",
        lambda *a, **k: yanit_olustur(kod),
    )

    sinif.cihazlari_yukle(form)

    assert mesaj in form.lbl_cihaz_hatasi.text()
    assert not form.lbl_cihaz_hatasi.isHidden()
    assert not form.btn_kaydet.isEnabled()


def test_baglanti_hatasi_gosterilir(ekran):
    modul, sinif, form, _, monkeypatch = ekran

    def baglanti_hatasi(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Baglanti kurulamadi")

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek", baglanti_hatasi
    )

    sinif.cihazlari_yukle(form)

    assert "bağlanılamadı" in form.lbl_cihaz_hatasi.text()
    assert not form.btn_kaydet.isEnabled()


def test_bos_cihaz_listesi_ayri_mesaj_verir(ekran):
    modul, sinif, form, _, monkeypatch = ekran

    monkeypatch.setattr(
        modul,
        "oturum_kontrollu_istek",
        lambda *a, **k: yanit_olustur(200, []),
    )

    sinif.cihazlari_yukle(form)

    assert "kayıtlı cihaz bulunmamaktadır" in (
        form.lbl_cihaz_hatasi.text()
    )
    assert not form.btn_kaydet.isEnabled()


def test_basarili_yukleme_kaydet_butonunu_acar(ekran):
    modul, sinif, form, plan_mi, monkeypatch = ekran

    cihazlar = [
        {"cihaz_id": 10, "envanter_kodu": "ENV-010", "cihaz_adi": "EEG"}
    ]

    monkeypatch.setattr(
        modul,
        "oturum_kontrollu_istek",
        lambda *a, **k: yanit_olustur(200, cihazlar),
    )

    sinif.cihazlari_yukle(form)

    assert form.btn_kaydet.isEnabled()
    assert form.lbl_cihaz_hatasi.isHidden()
    assert form.cmb_cihaz.count() == (2 if plan_mi else 1)
    assert form.cmb_cihaz.itemData(form.cmb_cihaz.count() - 1) == 10


def test_oturum_hatasi_mevcut_yonetimi_korur(ekran):
    modul, sinif, form, _, monkeypatch = ekran

    monkeypatch.setattr(
        modul,
        "oturum_kontrollu_istek",
        lambda *a, **k: yanit_olustur(
            401, oturum_hatasi=True
        ),
    )

    sinif.cihazlari_yukle(form)

    assert not form.btn_kaydet.isEnabled()
    assert form.lbl_cihaz_hatasi.isHidden()
