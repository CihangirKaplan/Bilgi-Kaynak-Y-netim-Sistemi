"""Ana paneldeki 'Yaklaşan ve Geciken Bakım/Kalibrasyonlar' tablosu: çok satırda sabit yükseklik + büyük kaydırma çubuğu.

Gerçek API kullanılmaz; sunucu cevapları taklit edilir.
"""
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

import dashboard_ekrani
from dashboard_ekrani import (CUBUK_STILI, SATIR_YUKSEKLIK, TABLO_GORUNEN_SATIR, TABLO_STIL, DashboardEkrani)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def islemler(n):
    return [{"cihaz_adi": f"E{i} - Cihaz", "islem_turu": "Bakım" if i % 2 else "Kalibrasyon",
             "kalan_gun": -i, "tarih": "01.01.2026"} for i in range(n)]


def pano(qt_app, n, **kw):
    def getir(yol):
        return {"/api/dashboard/ozet": {"acik_ariza_sayisi": 0},
                "/api/dashboard/yaklasan-islemler": islemler(n)}.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=True, **kw)
    p.zamanlayici.stop()
    return p


def kapat(p):
    p.close()
    p.deleteLater()


def ipucu(p):
    return p.panel_islem.findChild(QLabel, "tabloKaydirmaIpucu")


def test_sinira_kadar_satirda_tablo_eskisi_gibi_tum_satirlari_gosterir(qt_app):
    p = pano(qt_app, TABLO_GORUNEN_SATIR)
    t = p.tablo_islem
    assert t.rowCount() == 5 and t.height() == 46 + SATIR_YUKSEKLIK * 5 + 4
    assert t.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff and ipucu(p) is None
    assert CUBUK_STILI not in t.styleSheet()
    kapat(p)


def test_sinirdan_fazla_satirda_yukseklik_sabit_kalir_tum_satirlar_tabloda_durur(qt_app):
    p = pano(qt_app, 8)
    t = p.tablo_islem
    assert t.rowCount() == 8                                                   # hiçbir satır atılmaz
    assert t.height() == 46 + SATIR_YUKSEKLIK * TABLO_GORUNEN_SATIR + 4        # yalnızca 5 satır yüksekliği
    kapat(p)


def test_cok_satirda_cubuk_hep_gorunur_ve_buyuk_renkli_stillenir(qt_app):
    p = pano(qt_app, 8)
    t = p.tablo_islem
    assert t.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn
    assert TABLO_STIL in t.styleSheet() and CUBUK_STILI in t.styleSheet()
    assert "width: 18px" in CUBUK_STILI and "#2563EB" in CUBUK_STILI
    kapat(p)


def test_bildirim_kutusu_ve_tablo_ayni_cubuk_stilini_kullanir():
    assert CUBUK_STILI in dashboard_ekrani.KAYDIRMA_CUBUGU_STILI


def test_cok_satirda_baslik_satirinda_dikkat_ceken_rozet_gorunur(qt_app):
    p = pano(qt_app, 8)
    assert ipucu(p).text() == "⇅  8 kayıt var — kaydırarak hepsini görün"
    # mevcut "uyarı süresi içinde ve geciken" rozeti yerinde ve sağda kalır
    assert p.panel_islem.rozet.text().endswith("uyarı süresi içinde ve geciken")
    assert p.panel_islem.ust.indexOf(ipucu(p)) < p.panel_islem.ust.indexOf(p.panel_islem.rozet)
    kapat(p)


def test_satir_sayisi_azalinca_cubuk_ve_rozet_kalkar_ve_tekrar_cogalinca_geri_gelir(qt_app):
    p = pano(qt_app, 8)
    for n, kaydirilabilir in ((2, False), (9, True), (5, False)):
        with patch.object(DashboardEkrani, "_getir", side_effect=lambda y, n=n: islemler(n)):
            p._islemleri_yukle()
        t = p.tablo_islem
        assert t.rowCount() == n
        assert (t.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn) is kaydirilabilir
        assert (ipucu(p) is not None) is kaydirilabilir
    kapat(p)


def test_rozet_yenilemelerde_cogalmaz(qt_app):
    p = pano(qt_app, 8)
    for _ in range(3):
        with patch.object(DashboardEkrani, "_getir", side_effect=lambda y: islemler(8)):
            p._islemleri_yukle()
    assert len(p.panel_islem.findChildren(QLabel, "tabloKaydirmaIpucu")) == 1
    kapat(p)


def test_yetkisiz_satirlar_ayiklaninca_gorunen_satir_sayisina_gore_karar_verilir(qt_app):
    # 8 işlemin yarısı (Bakım) yetkisiz sayfada: 4 satır kalır -> kaydırma gerekmez
    p = pano(qt_app, 8, sayfa_ac=lambda s: None, sayfa_izinli_mi=lambda s: s != "Bakım Kayıtları")
    assert p.tablo_islem.rowCount() == 4
    assert p.tablo_islem.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff and ipucu(p) is None
    kapat(p)


def test_kaydirilinca_alttaki_satira_tiklamak_dogru_sayfayi_acar(qt_app):
    acilan = []
    p = pano(qt_app, 8, sayfa_ac=acilan.append)                                 # E7: Bakım (7 % 2 == 1)
    p.resize(1300, 900)
    p.show()
    p.grab()                                                                    # düzen kurulur
    t = p.tablo_islem
    t.scrollToBottom()
    son = t.rowCount() - 1
    assert t.verticalScrollBar().value() == t.verticalScrollBar().maximum() > 0
    merkez = t.visualRect(t.model().index(son, 0)).center()
    assert t.viewport().rect().contains(merkez)                                 # kaydırınca son satır görünür alana gelir
    QTest.mouseClick(t.viewport(), Qt.LeftButton, Qt.NoModifier, merkez)
    assert acilan == ["Bakım Kayıtları"]
    kapat(p)


def test_diger_tablolar_degismez_tum_satirlarini_gosterir_cubuksuz(qt_app):
    p = pano(qt_app, 8)
    for tablo in (p.tablo_randevu, p.tablo_rez):
        assert tablo.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        assert CUBUK_STILI not in tablo.styleSheet()
    kapat(p)
