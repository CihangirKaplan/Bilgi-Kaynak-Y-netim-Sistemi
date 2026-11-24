"""Sistem Durumu ekranı: son girişler tablosu tüm genişliği doldurur (yazılar kesilmez); bağlantı hatası mesajı sonraki başarılı yenilemede silinir."""
from unittest.mock import MagicMock, patch

import requests
from PySide6.QtWidgets import QHeaderView

import client.sistem_durumu_ekrani as modul

VERI = {
    "surum": "1.0.0", "sema_surumu": "f4c8a2e6b917", "veritabani_boyutu_mb": 10.1, "oturum_suresi_dk": 45,
    "yedek": {"var": True, "tarih": "2026-11-24T11:47:34", "gecen_saat": 2.0, "eski": False, "adet": 11, "boyut_mb": 0.11},
    "son_girisler": [{"kullanici_adi": "admin", "rol": "Sistem Admin", "zaman": "2026-11-24T14:20:00"}],
    "basarisiz_giris_24s": 0, "sayilar": {"aktif_kullanici": 1, "randevu": 0, "danisan_kodu": 0},
}


def _yanit(veri):
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = veri
    m._tkys_oturum_reddedildi = False
    return m


def _ekran(tkys_qapplication):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(VERI)):
        return modul.SistemDurumuEkrani("http://x", "t")


def test_son_girisler_tablosu_tum_genisligi_doldurur_zaman_kesilmez(tkys_qapplication):
    ekran = _ekran(tkys_qapplication)
    baslik = ekran.tablo.horizontalHeader()
    assert baslik.sectionResizeMode(0) == QHeaderView.Stretch and baslik.sectionResizeMode(1) == QHeaderView.Stretch
    assert baslik.sectionResizeMode(2) == QHeaderView.ResizeToContents
    ekran.resize(1400, 700)
    ekran.show()
    tkys_qapplication.processEvents()
    toplam = sum(baslik.sectionSize(i) for i in range(3))
    assert toplam >= ekran.tablo.viewport().width() - 4                         # yanda boş gri alan kalmaz
    zaman_hucresi = ekran.tablo.item(0, 2)
    assert baslik.sectionSize(2) >= ekran.tablo.fontMetrics().horizontalAdvance(zaman_hucresi.text())   # "24.11.2026 14:20" kesilmez


def test_baglanti_hatasi_mesaji_sonraki_basarili_yenilemede_silinir(tkys_qapplication):
    ekran = _ekran(tkys_qapplication)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=requests.ConnectionError("yok")):
        ekran.yenile()
    assert "ulaşılamadı" in ekran.alt_baslik.text()
    with patch.object(modul, "oturum_kontrollu_istek", return_value=_yanit(VERI)):
        ekran.yenile()
    assert ekran.alt_baslik.text() == modul.ALT_BASLIK
