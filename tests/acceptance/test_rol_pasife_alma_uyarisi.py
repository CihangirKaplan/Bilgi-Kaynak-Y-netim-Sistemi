"""Rol Düzenle penceresi: rolü pasife alırken kaç kullanıcının girişinin engelleneceği söylenir ve onay istenir."""
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import client.rol_izin_diyaloglari as modul


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


ROLLER = [
    {"rol_id": 3, "rol_adi": "MEMUR", "gorunen_ad": "Memur", "aktif_mi": True, "aktif_kullanici_sayisi": 3},
    {"rol_id": 4, "rol_adi": "BOS", "gorunen_ad": "Boş Rol", "aktif_mi": True, "aktif_kullanici_sayisi": 0},
]


def pencere(qt_app, secili_rol_id):
    p = modul.RolDuzenleDialog("http://localhost:8000", "t", [dict(r) for r in ROLLER], {})
    p.combo_roller.setCurrentIndex(p.combo_roller.findData(secili_rol_id))
    p.rol_secildi()
    return p


def kaydet(p, aktif, cevap=None):
    p.switch_aktif.setChecked(aktif)
    with patch.object(modul, "oturum_kontrollu_istek") as put, patch.object(QMessageBox, "question", return_value=cevap or QMessageBox.Yes) as soru, \
            patch.object(QMessageBox, "warning") as uyari:
        put.return_value.status_code = 200
        p.rol_kaydet()
    return put, soru, uyari


def test_kullanicisi_olan_rol_pasife_alinirken_sayi_soylenir(qt_app):
    put, soru, _ = kaydet(pencere(qt_app, 3), aktif=False)
    soru.assert_called_once()
    metin = soru.call_args.args[2]
    assert "3 aktif kullanıcı" in metin and "girişi engellenecek" in metin
    assert put.call_args.kwargs["json"]["aktif_mi"] is False


def test_onay_verilmezse_rol_pasife_alinmaz(qt_app):
    put, soru, _ = kaydet(pencere(qt_app, 3), aktif=False, cevap=QMessageBox.No)
    soru.assert_called_once()
    put.assert_not_called()


def test_kullanicisiz_rol_icin_de_onay_istenir_ama_engelleme_denmez(qt_app):
    _, soru, _ = kaydet(pencere(qt_app, 4), aktif=False)
    metin = soru.call_args.args[2]
    assert "aktif kullanıcı yok" in metin and "engellenecek" not in metin


def test_aktif_kalan_rolde_uyari_cikmaz(qt_app):
    put, soru, _ = kaydet(pencere(qt_app, 3), aktif=True)
    soru.assert_not_called()
    put.assert_called_once()


def test_sunucu_reddederse_sunucunun_mesaji_gosterilir(qt_app):
    p = pencere(qt_app, 3)
    p.switch_aktif.setChecked(False)
    with patch.object(modul, "oturum_kontrollu_istek") as put, patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), \
            patch.object(QMessageBox, "warning") as uyari:
        put.return_value.status_code = 409
        put.return_value.json.return_value = {"detail": "Kendi rolünüzü pasife alamazsınız; oturumunuz kapanırdı."}
        p.rol_kaydet()
    assert "Kendi rolünüzü" in uyari.call_args.args[2]
