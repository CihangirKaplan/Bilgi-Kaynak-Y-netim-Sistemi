"""Oda Yönetimi "Odayı Sil": sunucu ucu (izin, oturum) ve istemci (uyarı, onay, hata metinleri)."""
import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("JWT_SECRET", "k" * 64)

from PySide6.QtWidgets import QAbstractItemView, QMessageBox, QTableWidget, QTableWidgetItem, QWidget

import client.main_window as mw
from server import oda_api
from server.yetki_baglama import Hepsi


# ------------------------------------------------------------------ sunucu
def test_silme_ucu_kayitli_ve_odayi_duzenleyen_izinlerini_ister():
    uc = next(u for u in oda_api.UCLAR if u[0] == "DELETE" and u[1] == "/api/odalar/{oda_id}")
    assert uc[2] is oda_api.oda_sil and uc[4] == Hepsi("ODA_EKLE", "ODA_DUZENLE")      # Oda Yönetimi düğmeleriyle aynı yetki


def test_silme_ucu_oturumsuz_erisime_kapali():
    from fastapi.testclient import TestClient
    from server.sunucu import app
    assert TestClient(app).delete("/api/odalar/1").status_code in (401, 403)


def test_odalar_denetim_kaydina_silinen_icerik_yazilabilir_tablolardadir():
    from server.denetim import SILINEBILIR_TABLOLAR
    assert SILINEBILIR_TABLOLAR["odalar"] == "oda_id"


# ------------------------------------------------------------------ istemci
def _pencere(secili=True, durum="Pasif"):
    tablo = QTableWidget(1, 4)
    tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
    for sutun, deger in enumerate(["7", "Gözlem Odası", "1", durum]):
        tablo.setItem(0, sutun, QTableWidgetItem(deger))
    if secili:
        tablo.selectRow(0)
    ana = QWidget()                                  # onay kutusunun ebeveyni gerçek bir pencere olmalı
    ana.oda_tablosu, ana.api_url, ana.token, ana.odalari_getir = tablo, "http://testserver", "TOKEN", MagicMock()
    return ana


def _yanit(kod, detay=None):
    y = MagicMock()
    y.status_code = kod
    y.json.return_value = {"detail": detay} if detay else {}
    y._tkys_oturum_reddedildi = False
    return y


def _sil(ana, yanit=None, onay=True):
    """Onay kutusunda "Evet, Sil" (onay=True) ya da "Vazgeç" seçilir; döndürür: (istek, bildirim, uyari)."""
    istek = MagicMock(return_value=yanit or _yanit(200))
    bildirim, uyari, bilgi = MagicMock(), MagicMock(), MagicMock()
    kutular = []

    def sec(kutu):
        kutular.append(kutu)
        rol = QMessageBox.DestructiveRole if onay else QMessageBox.RejectRole
        return next(d for d in kutu.buttons() if kutu.buttonRole(d) == rol)

    with patch.object(mw, "oturum_kontrollu_istek", istek), patch.object(mw, "basari_bildirimi", bildirim), \
            patch.object(QMessageBox, "exec", lambda self: 0), patch.object(QMessageBox, "clickedButton", sec), \
            patch.object(QMessageBox, "warning", uyari), patch.object(QMessageBox, "information", bilgi):
        mw.AnaPencere.odayi_sil(ana)
    return istek, bildirim, uyari, kutular


def test_dugme_oda_yonetimi_eylemlerinde_ve_ayni_izinle_durur():
    sayfa = next(o for grup in mw.MENU for o in grup[1] if o["ad"] == "Oda Yönetimi")
    assert (mw.ODA_SIL_ETIKETI, "Oda yönetimi") in sayfa["aksiyon"]


def test_secim_yoksa_uyarir_istek_gondermez(tkys_qapplication):
    istek, _, uyari, _ = _sil(_pencere(secili=False))
    istek.assert_not_called()
    assert "silmek istediğiniz odayı" in uyari.call_args.args[2]


def test_onay_kutusu_kalici_ve_geri_alinamaz_oldugunu_soyler_varsayilan_vazgec(tkys_qapplication):
    ana = _pencere()                                          # onay kutusu ebeveyniyle birlikte yok olmasın
    _, _, _, kutular = _sil(ana, onay=False)
    kutu = kutular[0]
    assert "Gözlem Odası" in kutu.text() and "KALICI" in kutu.text()
    assert "geri alınamaz" in kutu.informativeText() and "pasif olarak kalır" in kutu.informativeText()
    assert kutu.defaultButton().text() == "Vazgeç"                  # yanlışlıkla Enter'a basılırsa silinmez


def test_aktif_oda_silinmez_uyarir_istek_gondermez_onay_kutusu_acilmaz(tkys_qapplication):
    ana = _pencere(durum="Aktif")
    istek, bildirim, uyari, kutular = _sil(ana)
    istek.assert_not_called()
    bildirim.assert_not_called()
    assert kutular == [] and uyari.call_args.args[1] == "Aktif Oda Silinemez" and "pasife alın" in uyari.call_args.args[2]


def _dugmeli_pencere(durum, secili=True):
    from PySide6.QtWidgets import QPushButton
    ana = _pencere(secili=secili, durum=durum)
    ana.oda_durum_butonu, ana.oda_sil_butonu = QPushButton(), QPushButton()
    mw.AnaPencere.oda_durum_butonunu_guncelle(ana)
    return ana


def test_sil_dugmesi_yalnizca_pasif_oda_secili_iken_etkindir(tkys_qapplication):
    assert _dugmeli_pencere("Pasif").oda_sil_butonu.isEnabled()
    aktif = _dugmeli_pencere("Aktif")
    assert not aktif.oda_sil_butonu.isEnabled() and "Önce odayı pasife alın" in aktif.oda_sil_butonu.toolTip()
    bos = _dugmeli_pencere("Pasif", secili=False)
    assert not bos.oda_sil_butonu.isEnabled() and "pasif bir oda seçin" in bos.oda_sil_butonu.toolTip()


def test_secim_degisince_sil_dugmesi_durumu_izler(tkys_qapplication):
    ana = _dugmeli_pencere("Pasif")
    ana.oda_tablosu.item(0, 3).setText("Aktif")                  # oda aktif edildi, liste yenilendi
    mw.AnaPencere.oda_durum_butonunu_guncelle(ana)
    assert not ana.oda_sil_butonu.isEnabled()
    ana.oda_tablosu.item(0, 3).setText("Pasif")
    mw.AnaPencere.oda_durum_butonunu_guncelle(ana)
    assert ana.oda_sil_butonu.isEnabled()


def test_vazgecilirse_hicbir_sey_yapilmaz(tkys_qapplication):
    ana = _pencere()
    istek, bildirim, _, _ = _sil(ana, onay=False)
    istek.assert_not_called()
    bildirim.assert_not_called()
    ana.odalari_getir.assert_not_called()


def test_onaylaninca_silme_istegi_gider_liste_yenilenir(tkys_qapplication):
    ana = _pencere()
    istek, bildirim, _, _ = _sil(ana)
    assert istek.call_args.args[:2] == ("DELETE", "http://testserver/api/odalar/7")
    assert "silindi" in bildirim.call_args.args[1]
    ana.odalari_getir.assert_called_once()


def test_kullanilmis_oda_409_sunucunun_aciklamasini_gosterir_liste_degismez(tkys_qapplication):
    ana = _pencere()
    detay = "Bu odayı kullanan 3 randevu kaydı var. Odayı pasife alarak kullanımdan kaldırabilirsiniz."
    _, bildirim, uyari, _ = _sil(ana, _yanit(409, detay))
    assert uyari.call_args.args[1] == "Oda Silinemedi" and detay in uyari.call_args.args[2]
    bildirim.assert_not_called()
    ana.odalari_getir.assert_not_called()


def test_baskasi_silmisse_404_bilgi_verir_ve_listeyi_yeniler(tkys_qapplication):
    ana = _pencere()
    _sil(ana, _yanit(404))
    ana.odalari_getir.assert_called_once()
