"""Parola taleplerinin yüklenmesinde hata ve boş durum kontrolleri."""

from types import SimpleNamespace

import pytest
import requests
from PySide6.QtWidgets import QApplication, QLabel

import k_personel_ekranlari as modul


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def ekran():
    gosterilen = []
    nesne = SimpleNamespace(
        api_url="http://testserver",
        token="test-token",
        lbl_talep_hatasi=QLabel(),
        talepleri_goster=lambda talepler: gosterilen.append(talepler),
    )
    return nesne, gosterilen


def yanit(kod, veri=None, oturum_hatasi=False):
    return SimpleNamespace(
        status_code=kod,
        json=lambda: veri,
        _tkys_oturum_reddedildi=oturum_hatasi,
    )


def test_talepler_basarili_yuklenir(ekran, monkeypatch):
    nesne, gosterilen = ekran
    talepler = [{"talep_id": 1, "kullanici_id": 2, "kullanici_adi": "ali"}]

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(200, talepler),
    )

    modul.KullaniciPersonelEkrani.talepleri_yukle(nesne)

    assert gosterilen == [talepler]
    assert nesne.lbl_talep_hatasi.isHidden()


def test_bos_liste_normaldir(ekran, monkeypatch):
    nesne, gosterilen = ekran

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(200, []),
    )

    modul.KullaniciPersonelEkrani.talepleri_yukle(nesne)

    assert gosterilen == [[]]
    assert nesne.lbl_talep_hatasi.isHidden()


def test_yetkisiz_panel_gizli_kalir(ekran, monkeypatch):
    nesne, gosterilen = ekran

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(403),
    )

    modul.KullaniciPersonelEkrani.talepleri_yukle(nesne)

    assert gosterilen == [[]]
    assert nesne.lbl_talep_hatasi.isHidden()


def test_sunucu_hatasi_gosterilir(ekran, monkeypatch):
    nesne, gosterilen = ekran

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(500),
    )

    modul.KullaniciPersonelEkrani.talepleri_yukle(nesne)

    assert gosterilen == [[]]
    assert "Sunucuda bir hata" in nesne.lbl_talep_hatasi.text()
    assert not nesne.lbl_talep_hatasi.isHidden()


def test_baglanti_hatasi_gosterilir(ekran, monkeypatch):
    nesne, gosterilen = ekran

    def baglanti_hatasi(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Baglanti kurulamadi")

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek", baglanti_hatasi
    )

    modul.KullaniciPersonelEkrani.talepleri_yukle(nesne)

    assert gosterilen == [[]]
    assert "bağlanılamadı" in nesne.lbl_talep_hatasi.text()
    assert not nesne.lbl_talep_hatasi.isHidden()


def test_oturum_hatasi_ayrica_gosterilmez(ekran, monkeypatch):
    nesne, gosterilen = ekran

    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(401, oturum_hatasi=True),
    )

    modul.KullaniciPersonelEkrani.talepleri_yukle(nesne)

    assert gosterilen == []
    assert nesne.lbl_talep_hatasi.isHidden()
