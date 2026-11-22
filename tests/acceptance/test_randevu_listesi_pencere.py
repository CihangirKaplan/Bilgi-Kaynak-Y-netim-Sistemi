"""Randevu listesi ekranı: sunucudan yalnızca seçili dönemi ister, dönem değişince yeniden yükler, kesilmişse bunu belirtir."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import client.randevu_ekranlari as modul
from client.randevu_ekranlari import RANDEVU_LISTE_SINIRI, RandevuAnaEkrani


def _cevap(veri, basliklar=None):
    y = MagicMock()
    y.status_code = 200
    y.json.return_value = veri
    y.headers = basliklar or {}
    y._tkys_oturum_reddedildi = False
    return y


class Sunucu:
    def __init__(self, randevular, toplam=None):
        self.randevular = randevular
        self.toplam = toplam
        self.randevu_istekleri = []

    def __call__(self, yontem, url, **kwargs):
        if url.endswith("/api/randevular"):
            self.randevu_istekleri.append(kwargs.get("params"))
            basliklar = {"X-Toplam-Kayit": str(self.toplam)} if self.toplam is not None else {}
            return _cevap(self.randevular, basliklar)
        return _cevap([])


def _ac(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        return RandevuAnaEkrani("http://testserver", "TOKEN", 11, "admin")


def _kayit(no):
    z = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    return {"randevu_id": no, "danisan_kod_id": f"D-{no}", "psikolog_id": 1, "oda_id": 1, "durum": "PLANLANDI",
            "baslangic_zamani": z.isoformat(), "bitis_zamani": (z + timedelta(hours=1)).isoformat()}


def test_tum_tarihler_limitle_istenir_donem_secilince_aralikla():
    sunucu = Sunucu([_kayit(1)])
    ekran = _ac(sunucu)
    assert sunucu.randevu_istekleri[0] == {"limit": RANDEVU_LISTE_SINIRI}
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.cmb_donem.setCurrentIndex(ekran.cmb_donem.findData("ay"))
    ay = sunucu.randevu_istekleri[-1]
    assert set(ay) == {"baslangic", "bitis"} and ay["baslangic"] <= ay["bitis"]
    assert ay["baslangic"].endswith("-01")
    ekran.close()


def test_sunucu_penceresi_ayniysa_tekrar_istek_atilmaz_yalniz_suzulur():
    sunucu = Sunucu([_kayit(1)])
    ekran = _ac(sunucu)
    sayi = len(sunucu.randevu_istekleri)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        ekran.arama.setText("D-1")
        ekran.chk_iptal_gizle.setChecked(False)
        ekran.cmb_durum.setCurrentIndex(1)
    assert len(sunucu.randevu_istekleri) == sayi
    ekran.close()


def test_liste_kesildiyse_sayac_toplami_ve_ne_yapilacagini_soyler():
    sunucu = Sunucu([_kayit(1), _kayit(2)], toplam=7500)
    ekran = _ac(sunucu)
    metin = ekran.lbl_sayac.text()
    assert "2 / 2 randevu" in metin and "toplam 7500" in metin
    ekran.close()


def test_kesilmemisse_sayac_eskisi_gibi():
    ekran = _ac(Sunucu([_kayit(1)], toplam=1))
    assert ekran.lbl_sayac.text() == "1 / 1 randevu"
    ekran.close()
