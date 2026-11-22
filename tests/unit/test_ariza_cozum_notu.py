"""Arıza çözüm notu: model, sunucu davranışı ve düzenleme formu."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox
from pydantic import ValidationError

import client.cihaz_ariza_ekranlari as ariza_modulu
import server.sunucu as sunucu
from server.modeller import ArizaGuncelleModeli


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _model(**k):
    veri = dict(ariza_baslik="Ekran", ariza_aciklama="Ekran açılmıyor", aciliyet="Yüksek", cozuldu_mu=True)
    veri.update(k)
    return ArizaGuncelleModeli(**veri)


def test_cozum_notu_kirpilir_bos_ise_none_uzunsa_reddedilir():
    assert _model(cozum_notu="  Kablo değiştirildi  ").cozum_notu == "Kablo değiştirildi"
    assert _model(cozum_notu="   ").cozum_notu is None
    assert _model().cozum_notu is None                                    # eski istemci göndermez
    with pytest.raises(ValidationError):
        _model(cozum_notu="x" * 501)


def _guncelle(model):
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchone.side_effect = [(7,), ("Arizali", False)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"):
        sunucu.ariza_guncelle(5, model, kullanici_id=1)
    sorgu, parametreler = imlec.execute.call_args_list[1].args
    return sorgu, parametreler


def test_cozulunce_not_yazilir_gonderilmediyse_eskisi_korunur():
    sorgu, p = _guncelle(_model(cozum_notu="Kablo değiştirildi"))
    assert "cozum_notu = COALESCE(%s, cozum_notu)" in sorgu and "Kablo değiştirildi" in p
    sorgu, p = _guncelle(_model())
    assert "COALESCE(%s, cozum_notu)" in sorgu and None in p


def test_yeniden_acilinca_not_ve_cozum_tarihi_temizlenir():
    sorgu, p = _guncelle(_model(cozuldu_mu=False, cozum_notu="eski not"))
    assert "cozum_tarihi = NULL" in sorgu and "cozum_notu = NULL" in sorgu and "eski not" not in p


def test_liste_ucu_cozum_tarihi_ve_notunu_dondurur():
    conn = MagicMock()
    imlec = conn.cursor.return_value
    imlec.fetchall.return_value = [(1, "EEG", "Başlık", "Açıklama", "Yüksek", True, datetime(2026, 11, 1, 10), "E-1", datetime(2026, 11, 2, 9), "Kablo değişti"),
                                   (2, "TMS", "B2", "A2", "Düşük", False, datetime(2026, 11, 3, 10), "E-2", None, None)]
    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        liste = sunucu.arizalari_listele(kullanici_id=1)
    assert liste[0]["cozum_notu"] == "Kablo değişti" and liste[0]["cozum_tarihi"] == "2026-11-02T09:00:00"
    assert liste[1]["cozum_notu"] is None and liste[1]["cozum_tarihi"] is None
    assert "cozum_notu" in imlec.execute.call_args.args[0]


def test_ariza_ipucu_cozum_bilgisini_gosterir():
    acik = {"ariza_aciklama": "Ekran açılmıyor", "durum": "Açık"}
    assert ariza_modulu.ariza_ipucu(acik) == "Ekran açılmıyor"
    cozuldu = {"ariza_aciklama": "Ekran açılmıyor", "durum": "Çözüldü", "cozum_tarihi": "2026-11-02T09:00:00", "cozum_notu": "Kablo değişti"}
    metin = ariza_modulu.ariza_ipucu(cozuldu)
    assert "Çözüm tarihi: 2026-11-02 09:00" in metin and "Çözüm: Kablo değişti" in metin
    assert "not girilmemiş" in ariza_modulu.ariza_ipucu({"durum": "Çözüldü"})                    # eski kayıt


def _form(qt_app):
    ar = {"ariza_id": 5, "cihaz_adi": "EEG", "aciliyet": "Orta", "ariza_baslik": "Ekran", "ariza_aciklama": "Ekran açılmıyor", "durum": "Açık"}
    f = ariza_modulu.ArizaDuzenleFormu("http://x", "t", ar)
    f.show()
    return f


def test_form_cozum_notu_yalniz_cozuldu_secilince_gorunur(qt_app):
    f = _form(qt_app)
    assert not f.txt_cozum_notu.isVisible()
    f.cmb_durum.setCurrentIndex(1)
    assert f.txt_cozum_notu.isVisible() and f.etiket_cozum_notu.isVisible()
    f.cmb_durum.setCurrentIndex(0)
    assert not f.txt_cozum_notu.isVisible()
    f.close()


def test_form_notsuz_cozumu_gondermez_notla_gonderir(qt_app):
    f = _form(qt_app)
    f.cmb_durum.setCurrentIndex(1)
    with patch.object(ariza_modulu, "oturum_kontrollu_istek") as istek, patch.object(QMessageBox, "warning") as uyari:
        f.kaydet()
        istek.assert_not_called()
        uyari.assert_called_once()
    yanit = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    f.txt_cozum_notu.setPlainText("Kablo değiştirildi")
    with patch.object(ariza_modulu, "oturum_kontrollu_istek", return_value=yanit) as istek, patch.object(ariza_modulu, "basari_bildirimi"):
        f.kaydet()
    gonderilen = istek.call_args.kwargs["json"]
    assert gonderilen["cozuldu_mu"] is True and gonderilen["cozum_notu"] == "Kablo değiştirildi"
    f.close()
