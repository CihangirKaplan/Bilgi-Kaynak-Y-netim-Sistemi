"""Rezervasyon düzenleme ve sahiplik: model, sunucu kararları (taklit imleç) ve ekran davranışı. Gerçek veritabanı senaryosu
tests/integration/test_cihaz_odasi_atama_pg_quality.py içindedir."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from PySide6.QtWidgets import QApplication, QPushButton

import client.cihaz_rezervasyon_ekranlari as m
import server.sunucu as sunucu
from server.modeller import RezervasyonGuncelleModeli


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ model
def _govde(**k):
    g = datetime.now() + timedelta(days=2)
    veri = dict(bolum_id=1, kullanilacak_oda_id=2, baslangic_zamani=g, bitis_zamani=g + timedelta(hours=2), proje_turu="  ", proje_adi_aciklamasi=" not ")
    veri.update(k)
    return veri


def test_guncelleme_modeli_bos_metni_none_yapar_cihaz_alanini_kabul_etmez():
    r = RezervasyonGuncelleModeli(**_govde())
    assert r.proje_turu is None and r.proje_adi_aciklamasi == "not"
    with pytest.raises(ValidationError):
        RezervasyonGuncelleModeli(**_govde(cihaz_id=5))                       # cihaz değiştirilemez
    g = datetime.now()
    with pytest.raises(ValidationError):
        RezervasyonGuncelleModeli(**_govde(baslangic_zamani=g, bitis_zamani=g - timedelta(hours=1)))


# ------------------------------------------------------------------ sunucu kararları
def _guncelle(mevcut):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [mevcut] if mevcut is not None else [None]
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"):
        return sunucu.rezervasyon_guncelle(9, RezervasyonGuncelleModeli(**_govde()), kullanici_id=1)


def test_guncelleme_olmayan_iptal_biten_ve_yetkisiz_durumlarini_reddeder():
    simdi = datetime.now()
    gelecek = (7, False, simdi + timedelta(days=2), simdi + timedelta(days=2, hours=2), 2, True)
    with pytest.raises(HTTPException) as hata:
        _guncelle(None)
    assert hata.value.status_code == 404
    with pytest.raises(HTTPException) as hata:
        _guncelle((7, True) + gelecek[2:])
    assert hata.value.status_code == 409 and "İptal edilmiş" in hata.value.detail
    with pytest.raises(HTTPException) as hata:
        _guncelle((7, False, simdi - timedelta(days=2), simdi - timedelta(days=1), 2, True))
    assert hata.value.status_code == 409 and "Süresi dolmuş" in hata.value.detail
    with pytest.raises(HTTPException) as hata:
        _guncelle(gelecek[:5] + (False,))
    assert hata.value.status_code == 403 and "oluşturan kişi" in hata.value.detail


def test_basladiktan_sonra_baslangic_ya_da_oda_degistirilemez():
    simdi = datetime.now()
    mevcut = (7, False, simdi - timedelta(hours=1), simdi + timedelta(hours=1), 2, True)       # devam eden rezervasyon
    with pytest.raises(HTTPException) as hata:
        _guncelle(mevcut)                                                    # gönderilen başlangıç (iki gün sonra) farklı
    assert hata.value.status_code == 409 and "Başlamış rezervasyonun" in hata.value.detail


def test_liste_ucu_sahip_yonetebilir_cihaz_ve_oda_bilgisini_dondurur():
    conn = MagicMock()
    imlec = conn.cursor.return_value
    g = datetime(2026, 12, 1, 10)
    imlec.fetchall.return_value = [(1, "E-1", "EEG", g, g + timedelta(hours=1), False, "Oda A", "TÜBİTAK", "açıklama", 3, "Bölüm", "ayse", True, 11, 5)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        satir = sunucu.rezervasyonlari_listele(kullanici_id=42)[0]
    assert satir["rezerve_eden"] == "ayse" and satir["yonetebilir"] is True and satir["cihaz_numarasi"] == 11 and satir["oda_id"] == 5
    assert imlec.execute.call_args.args[1] == (42, 42, sunucu.LISTE_UST_SINIRI)      # yetki ifadesi kullanıcı kimliğiyle iki kez, sonra liste üst sınırı (LIMIT)


# ------------------------------------------------------------------ ekran
REZ = {"rezervasyon_id": 8, "cihaz_id": "E-1 - EEG", "cihaz_numarasi": 11, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "oda_id": 5, "oda_adi": "Oda A",
       "bolum_id": 3, "bolum_adi": "Bölüm", "proje_turu": "TÜBİTAK", "proje_adi_aciklamasi": "Uyku çalışması", "durum": "Aktif",
       "baslangic_zamani": (datetime.now() + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0).isoformat(),
       "bitis_zamani": (datetime.now() + timedelta(days=3)).replace(hour=12, minute=0, second=0, microsecond=0).isoformat(),
       "rezerve_eden": "ayse", "yonetebilir": True}


def _form(qt_app, rez):
    def liste(self, yol, ad):
        return {"/api/bolumler": [{"bolum_id": 3, "bolum_adi": "Bölüm"}], "/api/proje-turleri": [{"proje_turu_id": 1, "ad": "TÜBİTAK"}]}.get(yol, [])
    with patch.object(m, "oturum_kontrollu_istek", side_effect=RuntimeError("ağ yok")), patch.object(m.YeniRezervasyonFormu, "_liste_getir", liste), \
         patch.object(m.QMessageBox, "warning"):
        f = m.YeniRezervasyonFormu("http://x", "t", duzenlenecek=rez)
    f.show()
    return f


def test_duzenleme_formu_mevcut_degerleri_yazar_cihazi_kilitler(qt_app):
    f = _form(qt_app, dict(REZ))
    assert f.windowTitle() == "Rezervasyonu Düzenle" and f.btn_kaydet.text() == "Değişiklikleri Kaydet"
    assert not f.cmb_cihaz.isEnabled() and f.cmb_cihaz.currentData() == 11 and f.cmb_oda.currentData() == 5
    assert f.cmb_bolum.currentData() == 3 and f.cmb_proje_turu.currentText() == "TÜBİTAK" and f.txt_proje_aciklama.toPlainText() == "Uyku çalışması"
    assert f.cmb_baslangic_saat.currentText() == "10:00" and f.cmb_bitis_saat.currentText() == "12:00"
    assert f.dt_baslangic_tarih.isEnabled() and f.cmb_oda.isEnabled()          # başlamamış rezervasyonda her şey düzenlenebilir
    f.close()


def test_baslamis_rezervasyonda_baslangic_ve_oda_kilitli_aciklama_gorunur(qt_app):
    rez = dict(REZ, baslangic_zamani=(datetime.now() - timedelta(hours=1)).replace(microsecond=0).isoformat(),
               bitis_zamani=(datetime.now() + timedelta(hours=1)).replace(microsecond=0).isoformat())
    f = _form(qt_app, rez)
    assert not f.dt_baslangic_tarih.isEnabled() and not f.cmb_baslangic_saat.isEnabled() and not f.cmb_oda.isEnabled()
    assert f.cmb_baslangic_saat.isEnabled() is False and "başladı" in f.lbl_uyari.text()
    f.close()


def test_duzenleme_put_ile_gider_cihaz_gonderilmez(qt_app):
    f = _form(qt_app, dict(REZ))
    f.txt_proje_aciklama.setPlainText("Yeni açıklama")
    yanit = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    with patch.object(m, "cakisma_cozumlu_istek", return_value=yanit) as istek, patch.object(m, "basari_bildirimi") as toast:
        f.kaydet()
    yontem, url, veri = istek.call_args.args[1:4]
    assert yontem == "PUT" and url == "http://x/api/rezervasyonlar/8" and "cihaz_id" not in veri
    assert veri["proje_adi_aciklamasi"] == "Yeni açıklama" and veri["kullanilacak_oda_id"] == 5 and veri["bolum_id"] == 3
    toast.assert_called_once()
    f.close()


def test_detay_penceresi_duzenle_ve_iptal_dugmeleri_yetkiye_baglidir(qt_app):
    ekran_sinifi = m.RezervasyonYonetimEkrani
    with patch.object(ekran_sinifi, "verileri_yukle"):
        ekran = ekran_sinifi("http://x", "t", yetkili_mi=True)
    acilanlar = []
    with patch.object(m.RezervasyonDetayPenceresi, "exec", lambda self: acilanlar.append(self)):
        ekran.rezervasyonlar = [dict(REZ)]
        ekran.rezervasyon_detay_ac(8)
        ekran.rezervasyonlar = [dict(REZ, yonetebilir=False)]
        ekran.rezervasyon_detay_ac(8)
        ekran.rezervasyonlar = [{k: v for k, v in REZ.items() if k != "yonetebilir"}]            # eski sunucu: alan yok
        ekran.rezervasyon_detay_ac(8)
    sahibi, baskasi, eski = acilanlar
    assert sahibi.btn_duzenle is not None and sahibi.btn_iptal is not None
    assert baskasi.btn_duzenle is None and baskasi.btn_iptal is None
    assert eski.btn_duzenle is not None
    assert "ayse" in " ".join(l.text() for l in sahibi.findChildren(m.QLabel))
    ekran.close()
