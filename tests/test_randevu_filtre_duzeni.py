"""
Filtre çubuğu gerçek ana pencere stiliyle (main_window.STIL) üst üste binmez.

Ana pencerenin genel stili her açılır kutuya `min-width: 170px` verir; filtre çubuğu bunu hesaba katmazsa
dar pencerede kutular birbirinin üstüne biner.
"""

import itertools

import pytest
from PySide6.QtWidgets import QVBoxLayout, QWidget

import main_window as mw
import randevu_ekranlari as modul
from randevu_ekranlari import RandevuAnaEkrani
from unittest.mock import MagicMock, patch


def cevap(veri):
    yanit = MagicMock()
    yanit.status_code = 200
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


def ekran_kur(genislik, ozel_aralik):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=lambda *a, **k: cevap([])):
        ekran = RandevuAnaEkrani("http://testserver", "TOKEN", 11, "admin")
    ev = QWidget()
    ev.setStyleSheet(mw.STIL)                      # gerçek uygulamadaki genel stil
    yerlesim = QVBoxLayout(ev)
    yerlesim.setContentsMargins(0, 0, 0, 0)
    yerlesim.addWidget(ekran)
    ev.setFixedSize(genislik, 520)                 # gerçek pencerede genişlik sabittir: içerik sığmazsa kutular sıkışır
    if ozel_aralik:
        ekran.cmb_donem.setCurrentIndex(ekran.cmb_donem.findData("ozel"))
    ev.show()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    return ev, ekran


def filtre_parcalari(ekran):
    parcalar = [ekran.arama, ekran.cmb_donem, ekran.dt_bas, ekran.lbl_tire, ekran.dt_bit,
                ekran.cmb_durum, ekran.chk_iptal_gizle, ekran.lbl_sayac, ekran.btn_yenile]
    return [p for p in parcalar if p.isVisibleTo(ekran)]


@pytest.mark.parametrize("genislik", [900, 1003, 1300])
@pytest.mark.parametrize("ozel_aralik", [False, True])
def test_filtre_kutulari_ust_uste_binmez_ve_ekrana_sigar(genislik, ozel_aralik):
    ev, ekran = ekran_kur(genislik, ozel_aralik)
    kutular = {p: p.geometry().translated(p.parentWidget().mapTo(ekran, p.parentWidget().rect().topLeft()))
               for p in filtre_parcalari(ekran)}
    for (a, ra), (b, rb) in itertools.combinations(kutular.items(), 2):
        assert not ra.intersects(rb), f"{a.__class__.__name__} ile {b.__class__.__name__} üst üste biniyor"
    for p, r in kutular.items():
        assert r.left() >= 0 and r.right() <= ekran.width(), f"{p.__class__.__name__} ekranın dışına taşıyor"
    assert ekran.arama.width() >= 180                    # arama kutusu kullanılabilir genişlikte kalır
    ev.close()
