"""Uzun süredir pasif öğrenciyi aktifleştirirken uyarı: saklama süresi sıfırlanır (pasife alındıktan 2 yıl kuralı)."""
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import client.ogrenci_yonetim_ekrani as modul

BUGUN = date(2026, 11, 26)


def _ogrenci(pasife, tur="GONULLU", aktif=False):
    return {"ogrenci_id": 1, "ad_soyad": "Ali Veli", "ogrenci_numarasi": "23100001", "tur": tur, "tur_etiketi": "Gönüllü Öğrenci",
            "aktif_mi": aktif, "kullanici_id": None, "kullanici_adi": None, "rol_adi": None, "telefon": None,
            "olusturulma_tarihi": "2015-01-05T10:00:00", "kayit_suresi_doldu": False, "ertelemeye_kadar": None, "ertelendi_mi": False,
            "pasife_alinma_tarihi": pasife}


@pytest.mark.parametrize("pasife, beklenen", [
    ("2026-11-26T09:00:00", 0), ("2026-10-27T09:00:00", 0), ("2026-10-26T09:00:00", 1),
    ("2025-11-26T09:00:00", 12), ("2025-11-27T09:00:00", 11), ("2024-11-26T09:00:00", 24), (None, None), ("bozuk", None),
])
def test_pasif_sure_ay(pasife, beklenen):
    assert modul.pasif_sure_ay(pasife, BUGUN) == beklenen


@pytest.mark.parametrize("ay, metin", [(0, "1 aydan kısa"), (5, "5 ay"), (12, "1 yıl"), (14, "1 yıl 2 ay"), (30, "2 yıl 6 ay")])
def test_pasif_sure_metni(ay, metin):
    assert modul.pasif_sure_metni(ay) == metin


def test_bir_yildan_kisa_pasif_ogrenci_icin_ek_uyari_yok():
    assert modul.aktiflestirme_uyarisi(_ogrenci("2026-03-01T00:00:00"), BUGUN) == ""


def test_bir_yildan_uzun_pasif_ogrenci_icin_sifirlanma_uyarisi():
    metin = modul.aktiflestirme_uyarisi(_ogrenci("2025-06-15T00:00:00"), BUGUN)
    assert "1 yıl 5 ay" in metin and "15.06.2025" in metin and "sıfırlanır" in metin and "silinmeye aday" not in metin


def test_iki_yili_dolmus_pasif_ogrenci_icin_silinmeye_aday_uyarisi():
    metin = modul.aktiflestirme_uyarisi(_ogrenci("2024-01-10T00:00:00"), BUGUN)
    assert "2 yıl 10 ay" in metin and "silinmeye aday" in metin and "sıfırlanır" in metin


def test_aktif_ya_da_gonullu_olmayan_ogrenci_icin_uyari_yok():
    assert modul.aktiflestirme_uyarisi(_ogrenci("2020-01-01T00:00:00", aktif=True), BUGUN) == ""
    assert modul.aktiflestirme_uyarisi(_ogrenci("2020-01-01T00:00:00", tur="ASISTAN"), BUGUN) == ""
    assert modul.aktiflestirme_uyarisi(_ogrenci(None), BUGUN) == ""


# ------------------------------------------------------------------ ekran: onay penceresi
def _yanit(veri, kod=200):
    m = MagicMock()
    m.status_code, m.text = kod, json.dumps(veri)
    m.json.return_value = veri
    m._tkys_oturum_reddedildi = False
    return m


def _ekran_ve_onay(kayit, onay_cevabi):
    sorular = []

    def soru(ebeveyn, baslik, metin, *a, **k):
        sorular.append(metin)
        return onay_cevabi

    istekler = []

    def istek(metot, url, **k):
        istekler.append((metot, url, k.get("json")))
        return _yanit([kayit]) if metot == "GET" else _yanit({"ogrenci_id": 1})

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek), \
            patch.object(modul.QMessageBox, "information", lambda *a, **k: 0), \
            patch.object(modul.QMessageBox, "question", side_effect=soru):
        ekran = modul.OgrenciYonetimEkrani("http://x", "t")
        ekran.yenile()
        ekran.tablo.selectRow(0)
        ekran.aktiflik_duzenle()
    return sorular, istekler


def test_uzun_pasif_ogrenciyi_aktiflestirirken_onay_penceresi_uyarir(tkys_qapplication):
    bugun = date.today()
    pasife = f"{bugun.year - 1}-{bugun.month:02d}-01T00:00:00"                         # yaklaşık 1 yıldır pasif (en az 12 ay)
    sorular, istekler = _ekran_ve_onay(_ogrenci(pasife), modul.QMessageBox.Yes)
    assert len(sorular) == 1 and "emin misiniz" in sorular[0] and "sıfırlanır" in sorular[0]
    assert any(m == "PATCH" and u.endswith("/aktiflik") and j == {"aktif_mi": True} for m, u, j in istekler)


def test_uyari_penceresinde_hayir_denirse_aktiflestirilmez(tkys_qapplication):
    sorular, istekler = _ekran_ve_onay(_ogrenci("2020-01-01T00:00:00"), modul.QMessageBox.No)
    assert "silinmeye aday" in sorular[0]
    assert not any(m == "PATCH" for m, _, _ in istekler)


def test_kisa_sureli_pasif_ogrencide_eski_sade_onay_degismez(tkys_qapplication):
    bugun = date.today()
    sorular, _ = _ekran_ve_onay(_ogrenci(f"{bugun.year}-{bugun.month:02d}-01T00:00:00"), modul.QMessageBox.Yes)
    assert sorular == ["Ali Veli adlı öğrenciyi aktifleştirmek istiyor musunuz?"]
