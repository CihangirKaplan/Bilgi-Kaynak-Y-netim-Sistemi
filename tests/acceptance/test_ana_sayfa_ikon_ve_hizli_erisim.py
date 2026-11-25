"""Ana sayfa: renkli zeminli çizgi ikonlar (emoji yok), kompakt Hızlı Erişim, sol menünün daralmış açılması, Çıkış Yap ikonu."""
import base64
import inspect
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QLabel

import client.main_window as mw
from client import dashboard_ekrani, ikon_kutusu
from client.tkys_sidebar_refined import PATHS


class Yanit:
    def __init__(self, veri=None):
        self._veri, self.status_code, self.text, self.headers = veri, 200, "{}", {}

    def json(self):
        return self._veri

    def raise_for_status(self):
        pass


def _token():
    yuk = base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + 99999}).encode()).decode().rstrip("=")
    return f"a.{yuk}.c"


@pytest.fixture
def pencere(tkys_qapplication):
    tum = sorted({k for v in mw.IZIN_KODLARI.values() for k in v})

    def istek(self, method=None, url=None, *a, **k):
        return Yanit({"rol_adi": "ADMIN", "izinler": tum} if str(url).endswith("/api/yetkilerim") else {})

    onceki = dict(mw._SUNUCU_YETKILERI)
    with patch("requests.sessions.Session.request", istek):
        ana = mw.AnaPencere(aktif_rol="admin", kullanici_adi="admin", token=_token(), kullanici_id=1)
        yield ana
        ana._yetki_zamanlayici.stop()
        ana._oturum_zamanlayici.stop()
        ana.deleteLater()
    mw._SUNUCU_YETKILERI.clear()
    mw._SUNUCU_YETKILERI.update(onceki)


def test_sol_menu_ilk_acilista_dar_menu_dugmesiyle_acilir(pencere):
    assert pencere._sol_menu_dar is True and pencere.sidebar.width() == 76
    pencere._sol_menu_degistir()
    assert pencere._sol_menu_dar is False and pencere.sidebar.width() == 280
    pencere._sol_menu_degistir()
    assert pencere.sidebar.width() == 76


def test_hizli_erisim_kutulari_ikonlu_kompakt_ve_tek_satira_sigar(pencere):
    izgara = pencere.hizli_erisim
    assert izgara.dugmeler and all(isinstance(d, mw.HizliErisimDugmesi) for d in izgara.dugmeler)
    assert {d.text() for d in izgara.dugmeler} <= set(ikon_kutusu.HIZLI_ERISIM_IKONLARI)
    assert all(d.height() == mw.HizliErisimDugmesi.YUKSEKLIK for d in izgara.dugmeler)
    assert izgara.kolon_sayisi(1100) == min(5, len(izgara.dugmeler))      # geniş pencerede hepsi tek satırda
    assert izgara.kolon_sayisi(300) == 1                                   # dar pencerede alt alta
    for dugme in izgara.dugmeler:
        simge = dugme.findChildren(QLabel)[0]
        assert simge.pixmap() is not None and not simge.pixmap().isNull()


def test_hizli_erisim_tiklaninca_sayfaya_gider(pencere):
    dugme = next(d for d in pencere.hizli_erisim.dugmeler if d.text() == "Randevu Yönetimi")
    dugme.click()
    assert pencere.nav_btnler["Randevu Yönetimi"].isChecked()


def test_ozet_kartlari_emoji_degil_cizgi_ikon_kullanir(tkys_qapplication):
    kaynak = inspect.getsource(dashboard_ekrani)
    for emoji in ("📅", "📌", "🛠️", "📏"):                      # ✅ ve 🔔 bildirim metinlerinde kalıyor (bu pakette dokunulmadı)
        assert emoji not in kaynak
    ekran = dashboard_ekrani.DashboardEkrani.__new__(dashboard_ekrani.DashboardEkrani)
    kart, _, _ = dashboard_ekrani.DashboardEkrani._kart(ekran, "BAŞLIK", "calendar", "#1D4ED8", "#DBEAFE")
    simge = kart.findChildren(QLabel)[0]
    assert simge.text() == "" and not simge.pixmap().isNull()


def test_ikon_kayit_defterinde_kullanilan_tum_ikonlar_var():
    for tur, _, _ in ikon_kutusu.HIZLI_ERISIM_IKONLARI.values():
        assert tur in PATHS
    for tur in ("calendar", "pin", "check-square", "wrench", "ruler", "warning", "key", "power"):
        assert tur in PATHS


def test_renkli_ikon_pixmap_boyutu_ve_cozunurlugu(tkys_qapplication):
    p = ikon_kutusu.renkli_ikon_pixmap("pin", "#15803D", "#DCFCE7", kutu=42)
    assert p.deviceIndependentSize() == QSize(42, 42) and p.devicePixelRatio() == 2
    assert ikon_kutusu.ikon_pixmap("key", "#000000", 18).deviceIndependentSize() == QSize(18, 18)


def test_hesap_menusu_cikis_ve_sifre_ikonlari_svg_olup_eski_karakter_yok():
    kaynak = inspect.getsource(mw.AnaPencere._kullanici_hesap_menusu)
    assert 'ikon_pixmap("power"' in kaynak and 'ikon_pixmap("key"' in kaynak
    assert "⏻" not in kaynak and "🔑" not in kaynak          # bazı Windows yazı tiplerinde kutu olarak görünüyordu


def test_dar_menu_baslik_dugmeleri_kaydirma_alanina_sigar_hover_zemini_kesilmez(pencere):
    assert pencere._sol_menu_dar is True
    pencere.resize(1366, 720)
    pencere.show()
    QApplication.processEvents()
    for grup in pencere._sidebar_elegant.groups.values():
        dugme = grup["header"]
        kullanilabilir = dugme.parentWidget().parentWidget().width() - pencere.nav_layout.contentsMargins().right()
        assert dugme.geometry().right() + 1 <= kullanilabilir      # sağ kenar kesilirse :hover zemini yarım görünür
