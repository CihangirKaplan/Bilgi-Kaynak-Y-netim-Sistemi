"""Cihaz Raporları süzgeç satırı: kutular 1366 px'lik ekranda komşu etiket ve düğmelerin üstüne binmez."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from client.cihaz_raporlari_ekrani import CihazRaporlariEkrani


# main_window.py'deki uygulama geneli kural (sorunu çıkaran: kutuları en az 170 px + dolgu kadar genişletir); test ana pencere açmadığı için buraya konur.
GENEL_STIL = "QComboBox { background: #EEF4FF; color: #0A1F5C; border: 1px solid #C7D9FB; border-radius: 10px; padding: 8px 14px; font-weight: 700; min-width: 170px; } QComboBox::drop-down { border: none; width: 24px; }"


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    uygulama = QApplication.instance() or QApplication([])
    onceki = uygulama.styleSheet()
    uygulama.setStyleSheet(GENEL_STIL)
    yield uygulama
    uygulama.setStyleSheet(onceki)


def _bos_istek(yontem, url, **k):
    y = MagicMock(status_code=200)
    uzun_cihaz = [{"cihaz_id": i, "envanter_kodu": f"E-{i}", "cihaz_adi": "Çok Kanallı Elektroensefalografi Kayıt ve Analiz Sistemi " * 2}
                  for i in range(3)]
    y.json.return_value = uzun_cihaz if url.endswith("/api/cihazlar") else {"bakim_ozeti": {}, "bakimlar": [], "kalibrasyonlar": [], "arizalar": [], "ozet": {}}
    return y


@pytest.mark.parametrize("sayfa_genisligi", [1022, 1100, 1500])
def test_suzgec_satiri_ogeleri_ust_uste_binmez(sayfa_genisligi):
    """1022 px, ana pencerede 1366 px ekrandaki sayfa genişliğidir (yan menü ve kenar boşlukları düşülmüş)."""
    with patch("client.cihaz_raporlari_ekrani.oturum_kontrollu_istek", _bos_istek), \
         patch("client.cihaz_raporlari_ekrani.oturum_hatasi_mi", return_value=False):
        e = CihazRaporlariEkrani("http://x", "t")
    e.resize(sayfa_genisligi, 700)
    e.show()
    QApplication.processEvents()
    # Sığmayan bir satır pencereyi büyütür (ana pencerede ise kutuları daraltıp üst üste bindirir): asgari genişlik sayfaya sığmalı.
    assert e.minimumSizeHint().width() <= sayfa_genisligi and e.width() <= sayfa_genisligi + 2
    oge = [e.donem, e.baslangic_etiketi, e.baslangic, e.bitis_etiketi, e.bitis, e.cihaz_sec, e.excel_btn]
    oge.insert(6, next(b for b in e.ust_alan.findChildren(type(e.excel_btn)) if b.text().endswith("Raporu Getir")))
    kutular = sorted((o.geometry() for o in oge), key=lambda g: g.x())
    for sol, sag in zip(kutular, kutular[1:]):
        assert sol.right() < sag.left(), (sol, sag)                                      # yan yana, üst üste değil
    assert e.donem.width() >= 120 and e.cihaz_sec.width() >= 120                         # içerik ("Tüm Cihazlar") kırpılmaz
    assert e.cihaz_sec.fontMetrics().horizontalAdvance("Tüm Cihazlar") < e.cihaz_sec.width() - 24
    e.close()
