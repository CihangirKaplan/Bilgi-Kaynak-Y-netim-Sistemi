"""Cihaz Yaşam Döngüsü denetimi: cihaz alanı temizliği, kalibrasyon tarih sırası, etkin durum ve rezervasyon iptali mesajları."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import server.sunucu as sunucu
from server.modeller import CihazGuncelleModeli, CihazOlusturModeli, KalibrasyonGuncelleModeli, KalibrasyonOlusturModeli


# ------------------------------------------------------------------ cihaz alanları
def test_cihaz_metinleri_kirpilir_bos_seri_no_null_olur():
    m = CihazOlusturModeli(envanter_kodu="  EEG-01 ", cihaz_adi="  EEG  ", marka_model="   ", seri_no="")
    assert (m.envanter_kodu, m.cihaz_adi, m.marka_model, m.seri_no) == ("EEG-01", "EEG", None, None)
    g = CihazGuncelleModeli(cihaz_adi=" Yeni ", seri_no="  ")
    assert g.cihaz_adi == "Yeni" and g.seri_no is None


@pytest.mark.parametrize("kod,ad", [("   ", "EEG"), ("E-1", "   ")])
def test_bosluktan_ibaret_zorunlu_alan_reddedilir(kod, ad):
    with pytest.raises(ValidationError):
        CihazOlusturModeli(envanter_kodu=kod, cihaz_adi=ad)


def test_cihaz_ekleme_envanter_kodunu_buyuk_kucuk_harf_ayirmadan_kontrol_eder_bos_seri_no_aramaz():
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.return_value = (1,)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            sunucu.cihaz_ekle(CihazOlusturModeli(envanter_kodu="eeg-01", cihaz_adi="EEG"), kullanici_id=1)
    assert hata.value.status_code == 409
    sorgu, parametreler = imlec.execute.call_args_list[0].args
    assert "lower(envanter_kodu) = lower(%s)" in sorgu and "%s IS NOT NULL" in sorgu
    assert parametreler == ("eeg-01", None, None)                           # seri no boşsa seri no çakışması aranmaz


# ------------------------------------------------------------------ kalibrasyon tarihleri
def _kalib(**degisim):
    veri = dict(cihaz_id=1, kalibrasyon_yapan_kurum="K", gecerlilik_tarihi=date(2027, 1, 1), sertifika_no="S",
                kalibrasyon_baslangic_tarihi=date(2026, 11, 1), kalibrasyon_bitis_tarihi=date(2026, 11, 3))
    veri.update(degisim)
    return veri


def test_kalibrasyon_gecerlilik_tarihi_bitisten_once_olamaz():
    KalibrasyonOlusturModeli(**_kalib())
    KalibrasyonOlusturModeli(**_kalib(gecerlilik_tarihi=date(2026, 11, 3)))          # aynı gün olur
    with pytest.raises(ValidationError, match="Geçerlilik tarihi"):
        KalibrasyonOlusturModeli(**_kalib(gecerlilik_tarihi=date(2026, 10, 1)))
    with pytest.raises(ValidationError, match="Geçerlilik tarihi"):
        KalibrasyonGuncelleModeli(gecerlilik_tarihi=date(2026, 10, 1), kalibrasyon_bitis_tarihi=date(2026, 11, 3))
    KalibrasyonGuncelleModeli(gecerlilik_tarihi=date(2026, 10, 1))                     # bitiş gönderilmediyse karşılaştırılmaz


# ------------------------------------------------------------------ etkin durum
def test_sunucu_etkin_durum_tanimi_panel_ve_liste_icin_ortaktir():
    assert "cihaz_bakimlari" in sunucu.ETKIN_CIHAZ_DURUMU_SQL and "cihaz_kalibrasyonlari" in sunucu.ETKIN_CIHAZ_DURUMU_SQL
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.side_effect = [[(1, "E-1", "EEG", None, None, "Kullanima_Hazir", datetime(2026, 1, 1), "Kalibrasyonda")], [("Kalibrasyonda", 1)]]
    imlec.fetchone.return_value = (0,)
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.cihazlari_listele(kullanici_id=1)
        ozet = sunucu.dashboard_ozet_getir(kullanici_id=1)
    assert ozet["kalibrasyondaki_cihaz"] == 1
    assert liste[0]["durum"] == "Kullanima_Hazir" and liste[0]["etkin_durum"] == "Kalibrasyonda"
    sorgular = [str(c.args[0]) for c in imlec.execute.call_args_list]
    assert sum("cihaz_kalibrasyonlari" in q for q in sorgular) == 2                    # liste ve panel aynı tanımı kullanır


def test_envanter_ekrani_etkin_durumu_gosterir_eski_sunucuda_kayitli_durumu():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import client.cihaz_ekranlari as m
    assert m.etkin_durum({"durum": "Kullanima_Hazir", "etkin_durum": "Kalibrasyonda"}) == "Kalibrasyonda"
    assert m.etkin_durum({"durum": "Arizali"}) == "Arizali"                             # eski sunucu: alan yok
    veri = [{"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "durum": "Kullanima_Hazir", "etkin_durum": "Kalibrasyonda", "kayit_tarihi": "2026-01-01T00:00:00"},
            {"cihaz_id": 2, "envanter_kodu": "E-2", "cihaz_adi": "TMS", "durum": "Kullanima_Hazir", "etkin_durum": "Kullanima_Hazir", "kayit_tarihi": "2026-01-01T00:00:00"}]
    yanit = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    yanit.json.return_value = veri
    with patch.object(m, "oturum_kontrollu_istek", return_value=yanit):
        ekran = m.CihazYonetimEkrani("http://x", "t", yetkili_mi=True)
    assert ekran.cip_toplam.text() == "2 cihaz"
    assert ekran.cip_hazir.text().startswith("1 ") and ekran.cip_bakimda.text().startswith("1 ")     # kalibrasyondaki cihaz 'hazır' sayılmaz
    ekran.close()


# ------------------------------------------------------------------ rezervasyon iptali
def _iptal(sonuclar):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = sonuclar
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"):
        return sunucu.rezervasyon_iptal(rezervasyon_id=5, kullanici_id=1), conn


def test_iptal_nedenine_gore_ayri_mesaj_verir():
    sonuc, conn = _iptal([(5,)])
    assert sonuc["durum"] == "basarili"
    with pytest.raises(HTTPException) as yok:
        _iptal([None, None])
    assert yok.value.status_code == 404 and "bulunamadı" in yok.value.detail
    with pytest.raises(HTTPException) as zaten:
        _iptal([None, (True, False, True)])
    assert zaten.value.status_code == 409 and "zaten iptal" in zaten.value.detail
    with pytest.raises(HTTPException) as bitmis:
        _iptal([None, (False, True, True)])
    assert bitmis.value.status_code == 409 and "Süresi dolmuş" in bitmis.value.detail
    with pytest.raises(HTTPException) as yetkisiz:
        _iptal([None, (False, False, False)])
    assert yetkisiz.value.status_code == 403 and "oluşturan kişi" in yetkisiz.value.detail
