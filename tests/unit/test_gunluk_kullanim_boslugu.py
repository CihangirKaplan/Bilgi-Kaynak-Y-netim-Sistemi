"""Günlük kullanım boşlukları: çözülmüş arızanın yeniden açılması, bakımdaki cihaza arıza bildirimi, rezervasyon mesai ve süre kuralı."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from PySide6.QtWidgets import QApplication, QPushButton

import client.cihaz_ariza_ekranlari as ariza
import server.sunucu as sunucu
from server.modeller import REZERVASYON_EN_UZUN_GUN, RezervasyonGuncelleModeli, RezervasyonOlusturModeli, rezervasyon_zaman_sorunu


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def _yanit(veri):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    return y


# ------------------------------------------------------------------ arıza: yeniden açma
COZULMUS = {"ariza_id": 2, "cihaz_adi": "EKG", "envanter_kodu": "E-2", "ariza_baslik": "Ekran", "ariza_aciklama": "y", "aciliyet": "Yüksek", "durum": "Çözüldü",
            "bildirim_tarihi": "2026-11-01T10:30:00", "cozum_tarihi": "2026-11-02T09:00:00", "cozum_notu": "Kablo değişti"}


def test_cozulmus_arizada_da_duzenle_yeniden_ac_dugmesi_var_yetkisizde_yok():
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=_yanit([COZULMUS])):
        e = ariza.ArizaYonetimEkrani("http://x", "t", yetkili_mi=True)
        y = ariza.ArizaYonetimEkrani("http://x", "t", yetkili_mi=False)
    dugme = e.tablo.cellWidget(0, 6).findChildren(QPushButton)[0]
    assert dugme.text() == "↺" and "yeniden aç" in dugme.toolTip()
    assert y.tablo.cellWidget(0, 6) is None
    e.close()
    y.close()


def test_cozulmus_arizayi_acik_secince_uyari_gorunur_ve_not_gonderilmez():
    f = ariza.ArizaDuzenleFormu("http://x", "t", dict(COZULMUS))
    f.show()
    assert f.cmb_durum.currentIndex() == 1 and not f.lbl_yeniden_ac.isVisible() and f.txt_cozum_notu.toPlainText() == "Kablo değişti"
    f.cmb_durum.setCurrentIndex(0)
    assert f.lbl_yeniden_ac.isVisible() and not f.txt_cozum_notu.isVisible()
    yanit = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    with patch.object(ariza, "oturum_kontrollu_istek", return_value=yanit) as istek, patch.object(ariza, "basari_bildirimi"):
        f.kaydet()
    gonderilen = istek.call_args.kwargs["json"]
    assert gonderilen["cozuldu_mu"] is False and gonderilen["cozum_notu"] is None
    f.close()


def test_acik_arizada_yeniden_ac_uyarisi_hic_gorunmez():
    f = ariza.ArizaDuzenleFormu("http://x", "t", dict(COZULMUS, durum="Açık"))
    f.show()
    f.cmb_durum.setCurrentIndex(0)
    assert not f.lbl_yeniden_ac.isVisible()
    f.close()


def test_ariza_cihaz_notu_durumlara_gore():
    assert "'Arızalı' durumuna geçecektir" in ariza.ariza_cihaz_notu("Kullanima_Hazir") and "'Arızalı' durumuna" in ariza.ariza_cihaz_notu(None)
    assert "zaten arızalı" in ariza.ariza_cihaz_notu("Arizali")
    assert "'Kalibrasyonda'" in ariza.ariza_cihaz_notu("Kalibrasyonda") and "durumu değişmez" in ariza.ariza_cihaz_notu("Bakimda")


# ------------------------------------------------------------------ rezervasyon: mesai ve süre
G = datetime(2026, 12, 7, 0, 0)


def _z(gun, saat, dakika=0):
    return G + timedelta(days=gun, hours=saat, minutes=dakika)


@pytest.mark.parametrize("bas,bit,gecerli", [
    (_z(0, 8), _z(0, 18), True), (_z(0, 10), _z(0, 12), True), (_z(0, 17, 30), _z(0, 18), True), (_z(0, 16), _z(1, 10), True),     # gece boyu: iki ucu da mesai içinde
    (_z(0, 3), _z(0, 5), False), (_z(0, 7, 59), _z(0, 10), False), (_z(0, 17), _z(0, 18, 1), False), (_z(0, 18), _z(1, 9), False),
    (_z(0, 20), _z(0, 22), False), (_z(0, 9), _z(1, 7), False),
])
def test_rezervasyon_mesai_kurali(bas, bit, gecerli):
    assert (rezervasyon_zaman_sorunu(bas, bit) is None) is gecerli


def test_rezervasyon_en_fazla_30_gun():
    assert rezervasyon_zaman_sorunu(_z(0, 9), _z(REZERVASYON_EN_UZUN_GUN, 9)) is None
    assert "30 gün" in rezervasyon_zaman_sorunu(_z(0, 9), _z(REZERVASYON_EN_UZUN_GUN + 1, 10))


def _olustur(bas, bit):
    gelecek = lambda d: d + timedelta(days=400)
    return RezervasyonOlusturModeli(cihaz_id=1, bolum_id=1, kullanilacak_oda_id=1, baslangic_zamani=gelecek(bas), bitis_zamani=gelecek(bit))


def test_olusturma_ucu_mesai_disini_422_ile_reddeder_baglanti_acilmadan():
    with patch("server.sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            sunucu.cihaz_rezervasyonu_yap(_olustur(_z(0, 3), _z(0, 5)), kullanici_id=1)
        assert hata.value.status_code == 422 and "08:00-18:00" in hata.value.detail
        with pytest.raises(HTTPException) as hata:
            sunucu.cihaz_rezervasyonu_yap(_olustur(_z(0, 9), _z(45, 10)), kullanici_id=1)
        assert hata.value.status_code == 422 and "30 gün" in hata.value.detail
        baglan.assert_not_called()


def _guncelle(model, mevcut):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [mevcut, (1,)]                                        # ikincisi: bölüm var mı sorgusu
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"), \
         patch("server.sunucu.rezervasyon_uygunlugunu_denetle"):
        return sunucu.rezervasyon_guncelle(9, model, kullanici_id=1), imlec


def test_duzenlemede_saat_degisirse_kural_uygulanir_yalniz_aciklama_degisirse_eski_kayit_engellenmez():
    ileri = datetime.now() + timedelta(days=5)
    bas = ileri.replace(hour=3, minute=0, second=0, microsecond=0)                     # eski/ihlalli kayıt: gece 03:00
    mevcut = (7, False, bas, bas + timedelta(hours=2), 2, True)
    ayni = RezervasyonGuncelleModeli(bolum_id=1, kullanilacak_oda_id=2, baslangic_zamani=bas, bitis_zamani=bas + timedelta(hours=2), proje_adi_aciklamasi="yeni not")
    sonuc, _ = _guncelle(ayni, mevcut)                                                  # saat aynı: yalnızca not değişiyor
    assert sonuc["durum"] == "basarili"
    kaydir = RezervasyonGuncelleModeli(bolum_id=1, kullanilacak_oda_id=2, baslangic_zamani=bas + timedelta(hours=1), bitis_zamani=bas + timedelta(hours=3))
    with pytest.raises(HTTPException) as hata:
        _guncelle(kaydir, mevcut)
    assert hata.value.status_code == 422 and "08:00-18:00" in hata.value.detail
