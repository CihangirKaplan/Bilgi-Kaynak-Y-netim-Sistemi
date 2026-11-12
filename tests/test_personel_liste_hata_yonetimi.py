"""Personel listesi API hata yönetimi regresyon testleri."""

from types import SimpleNamespace

import pytest
import requests
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

import k_personel_ekranlari as modul


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def ekran():
    tablo = QTableWidget()
    tablo.setColumnCount(6)
    tablo.setRowCount(2)  # Önceden yüklenmiş kayıtlar

    nesne = SimpleNamespace(
        api_url="http://testserver",
        token="test-token",
        tablo=tablo,
        lbl_personel_hatasi=QLabel(),
        talepleri_yukle=lambda: None,
    )
    return nesne


def yanit(kod, veri=None, oturum_hatasi=False):
    return SimpleNamespace(
        status_code=kod,
        json=lambda: veri,
        _tkys_oturum_reddedildi=oturum_hatasi,
    )


@pytest.mark.parametrize("kod,mesaj", [
    (403, "yetkiniz"),
    (500, "Sunucuda bir hata"),
])
def test_http_hatasi_gosterilir(ekran, monkeypatch, kod, mesaj):
    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(kod),
    )

    modul.KullaniciPersonelEkrani.verileri_cek(ekran)

    assert ekran.tablo.rowCount() == 0
    assert mesaj in ekran.lbl_personel_hatasi.text()
    assert not ekran.lbl_personel_hatasi.isHidden()


def test_baglanti_hatasi_gosterilir(ekran, monkeypatch):
    def hata(*args, **kwargs):
        raise requests.exceptions.ConnectionError("Bağlantı yok")

    monkeypatch.setattr(modul, "oturum_kontrollu_istek", hata)

    modul.KullaniciPersonelEkrani.verileri_cek(ekran)

    assert ekran.tablo.rowCount() == 0
    assert "bağlanılamadı" in ekran.lbl_personel_hatasi.text()


def test_bos_liste_hata_degil(ekran, monkeypatch):
    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(200, []),
    )

    modul.KullaniciPersonelEkrani.verileri_cek(ekran)

    assert ekran.tablo.rowCount() == 0
    assert ekran.lbl_personel_hatasi.isHidden()


def test_gecersiz_liste_hatasi_gosterilir(ekran, monkeypatch):
    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(200, {"beklenmeyen": "veri"}),
    )

    modul.KullaniciPersonelEkrani.verileri_cek(ekran)

    assert ekran.tablo.rowCount() == 0
    assert not ekran.lbl_personel_hatasi.isHidden()


def test_oturum_hatasi_ayrica_gosterilmez(ekran, monkeypatch):
    monkeypatch.setattr(
        modul, "oturum_kontrollu_istek",
        lambda *a, **k: yanit(401, oturum_hatasi=True),
    )

    modul.KullaniciPersonelEkrani.verileri_cek(ekran)

    assert ekran.lbl_personel_hatasi.isHidden()
