"""Pasif ya da başka role geçmiş psikologun adı "Psikolog #19" yerine gerçek adıyla görünür.

- Randevu Yönetimi ve Danışanlar ekranları ad sözlüğünü /api/psikologlar?pasifler_dahil=true ile ister
- Danışanlar ekranındaki psikolog filtresinde pasif olanın yanında "(pasif)" yazar
- Randevu formundaki psikolog seçimi (parametresiz çağrı) yalnızca aktifleri göstermeye devam eder
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

import client.danisanlar_ekrani as dmodul
import client.randevu_ekranlari as modul
from client.danisanlar_ekrani import DanisanlarEkrani
from client.randevu_ekranlari import RandevuAnaEkrani


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


def zaman(gun_farki=1, saat=10):
    return ((datetime.now().replace(hour=saat, minute=0, second=0, microsecond=0)) + timedelta(days=gun_farki)).isoformat()


AKTIFLER = [{"personel_id": 3, "ad_soyad": "ayse", "kullanici_id": 13}]
HEPSI = [{"personel_id": 3, "ad_soyad": "ayse", "kullanici_id": 13, "aktif_mi": True},
         {"personel_id": 19, "ad_soyad": "eski_psikolog", "kullanici_id": 40, "aktif_mi": False}]


class Sunucu:
    """Parametreye göre gerçek uçtaki gibi yanıtlar: pasifler_dahil=true ise eski psikolog da gelir."""

    def __init__(self):
        self.psikolog_istekleri = []

    def __call__(self, yontem, url, **kwargs):
        if url.endswith("/api/psikologlar"):
            params = kwargs.get("params") or {}
            self.psikolog_istekleri.append(params)
            return cevap(HEPSI if params.get("pasifler_dahil") == "true" else AKTIFLER)
        if url.endswith("/api/randevular"):
            return cevap([{"randevu_id": 1, "danisan_kod_id": "DAN-2026-0001", "psikolog_id": 19, "oda_id": 2, "durum": "TAMAMLANDI",
                           "baslangic_zamani": zaman(-5), "bitis_zamani": zaman(-5, 11), "iptal_nedeni": None, "iptal_notu": None,
                           "gorusme_tipi": "YUZ_YUZE", "terapi_turu": None}])
        if url.endswith("/api/danisan-kodlari"):
            return cevap([{"danisan_kod_id": "DAN-2026-0001", "ucretli_mi": True, "istisna_turu": "YOK", "aktif_mi": True,
                           "olusturulma_tarihi": zaman(-30), "olusturan_psikolog_id": 19}])
        if url.endswith("/api/odalar"):
            return cevap([{"oda_id": 2, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}])
        return cevap([])


def test_randevu_yonetiminde_pasif_psikologun_gercek_adi_gorunur():
    sunucu = Sunucu()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran = RandevuAnaEkrani("http://testserver", "TOKEN", 11, "admin")
    assert {"pasifler_dahil": "true"} in sunucu.psikolog_istekleri
    adlar = [ekran.tablo.item(i, 2).text() for i in range(ekran.tablo.rowCount())]
    assert adlar == ["eski_psikolog"]                                       # "Psikolog #19" değil
    ekran.close()


def test_danisanlar_ekraninda_gercek_ad_ve_filtrede_pasif_etiketi():
    sunucu = Sunucu()
    with patch.object(dmodul, "oturum_kontrollu_istek", side_effect=sunucu), patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran = DanisanlarEkrani("http://testserver", "TOKEN", None)
    kutu = [ekran.cmb_psikolog.itemText(i) for i in range(ekran.cmb_psikolog.count())]
    assert kutu == ["Tüm psikologlar", "ayse", "eski_psikolog (pasif)"]
    assert ekran.psikolog_adlari[19] == "eski_psikolog" and ekran.pasif_psikologlar == {19}
    ekran.close()


def test_danisanlar_satirinda_eski_psikologun_adi_gorunur():
    sunucu = Sunucu()
    with patch.object(dmodul, "oturum_kontrollu_istek", side_effect=sunucu), patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran = DanisanlarEkrani("http://testserver", "TOKEN", None)
    metinler = [ekran.tablo.item(0, c).text() for c in range(ekran.tablo.columnCount()) if ekran.tablo.item(0, c)]
    assert "eski_psikolog" in metinler and not any("Psikolog #" in m for m in metinler)
    ekran.close()
