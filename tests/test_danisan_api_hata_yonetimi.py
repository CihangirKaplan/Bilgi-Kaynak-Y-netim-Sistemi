from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from PySide6.QtWidgets import QLabel

import danisanlar_ekrani as modul


@pytest.fixture
def ekran():
    nesne = SimpleNamespace(
        api_url="http://testserver",
        token="TOKEN",
        _yukleme_hatalari={},
        lbl_yukleme_hatasi=QLabel(),
    )
    nesne._yukleme_durumu = lambda yol, mesaj=None: (
        modul.DanisanlarEkrani._yukleme_durumu(
            nesne, yol, mesaj
        )
    )
    return nesne


def yanit(durum, veri=None):
    return SimpleNamespace(
        status_code=durum,
        json=lambda: veri,
        _tkys_oturum_reddedildi=False,
    )


@pytest.mark.parametrize("durum, beklenen", [
    (403, "yetkiniz"),
    (500, "Sunucuda bir hata"),
])
def test_http_hatasi(ekran, durum, beklenen):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(durum),
    ):
        sonuc = modul.DanisanlarEkrani._api_liste_getir(
            ekran, "/api/danisan-kodlari"
        )

    assert sonuc is None
    assert beklenen in ekran.lbl_yukleme_hatasi.text()
    assert not ekran.lbl_yukleme_hatasi.isHidden()


def test_baglanti_hatasi(ekran):
    with patch.object(
        modul, "oturum_kontrollu_istek",
        side_effect=requests.exceptions.ConnectionError("gizli detay"),
    ):
        sonuc = modul.DanisanlarEkrani._api_liste_getir(
            ekran, "/api/danisan-kodlari"
        )

    assert sonuc is None
    assert "Sunucuya bağlanılamadı" in ekran.lbl_yukleme_hatasi.text()
    assert "gizli detay" not in ekran.lbl_yukleme_hatasi.text()


def test_basarili_yenilemede_hata_kalkar(ekran):
    def durum_guncelle(yol, mesaj=None):
        modul.DanisanlarEkrani._yukleme_durumu(
            ekran, yol, mesaj
        )

    ekran._yukleme_durumu = durum_guncelle

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(500),
    ):
        modul.DanisanlarEkrani._api_liste_getir(
            ekran, "/api/danisan-kodlari"
        )

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=yanit(200, []),
    ):
        sonuc = modul.DanisanlarEkrani._api_liste_getir(
            ekran, "/api/danisan-kodlari"
        )

    assert sonuc == []
    assert ekran.lbl_yukleme_hatasi.isHidden()
