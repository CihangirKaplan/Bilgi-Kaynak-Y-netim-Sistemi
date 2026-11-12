"""Öğrenci listesi API hata mesajlarının regresyon testleri."""
import turkce_mesaj_kutusu as tmk

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from PySide6.QtWidgets import QMessageBox

import ogrenci_yonetim_ekrani as modul


@pytest.mark.parametrize("durum, beklenen", [
    (403, "yetkiniz"),
    (500, "Sunucuda bir hata"),
])
def test_ogrenci_listesi_http_hatasi(durum, beklenen):
    eski_kayitlar = [{"ogrenci_id": 1}]
    cevap = SimpleNamespace(status_code=durum)

    ekran = SimpleNamespace(
        kayitlar=eski_kayitlar,
        _istek=lambda *a, **k: cevap,
    )

    with patch.object(tmk, "uyari") as uyari:
        modul.OgrenciYonetimEkrani.yenile(ekran)

    uyari.assert_called_once()
    assert beklenen in uyari.call_args.args[2]
    assert ekran.kayitlar == eski_kayitlar


def test_ogrenci_listesi_baglanti_hatasi():
    ekran = SimpleNamespace(
        api_url="http://testserver",
        token="TOKEN",
    )

    with patch.object(
        modul, "oturum_kontrollu_istek",
        side_effect=requests.exceptions.ConnectionError("Gizli teknik detay"),
    ), patch.object(tmk, "uyari") as uyari:
        sonuc = modul.OgrenciYonetimEkrani._istek(
            ekran, "GET", "/api/ogrenciler-yonetim"
        )

    assert sonuc is None
    uyari.assert_called_once()
    assert "Sunucuya bağlanılamadı" in uyari.call_args.args[2]
    assert "Gizli teknik detay" not in uyari.call_args.args[2]
