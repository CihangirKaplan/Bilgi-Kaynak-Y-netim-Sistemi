"""
Sayfa başlığı üst çubukta ("TKYS › Sayfa adı"); sayfalarda büyük başlık kartı yok, işlem düğmeleri ince satırda.

Gerçek ana pencere açılır, ağ istekleri taklit edilir.
"""
import base64
import json
import time
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

import main_window as mw
from main_window import AnaPencere


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def yetki_tablosunu_koru():
    onceki = dict(mw._SUNUCU_YETKILERI)
    yield
    mw._SUNUCU_YETKILERI.clear()
    mw._SUNUCU_YETKILERI.update(onceki)


class Esnek(list):
    """Liste de sözlük de gibi davranır; bu testte sayfa içerikleri önemli değil."""
    def get(self, anahtar, varsayilan=None):
        return varsayilan

    def __getitem__(self, anahtar):
        return Esnek() if isinstance(anahtar, str) else super().__getitem__(anahtar)


class Yanit:
    def __init__(self, veri=None, durum=200):
        self._veri, self.status_code, self.text, self.headers = veri, durum, "{}", {}

    def json(self):
        return self._veri

    def raise_for_status(self):
        pass


def sahte_token():
    yuk = base64.urlsafe_b64encode(json.dumps({"exp": int(time.time()) + 99999}).encode()).decode().rstrip("=")
    return f"a.{yuk}.c"


@pytest.fixture
def pencere_ac(qt_app):
    acik = []

    def ac(izinler):
        durum = {"rol_adi": "MEMUR", "izinler": izinler}

        def sahte(self, method=None, url=None, *a, **k):
            return Yanit(durum if str(url).endswith("/api/yetkilerim") else Esnek())

        yama = patch("requests.sessions.Session.request", sahte)
        yama.start()
        acik.append(yama)
        ana = AnaPencere(aktif_rol="memur", kullanici_adi="m", token=sahte_token(), kullanici_id=2)
        acik.append(ana)
        ana.resize(1366, 700)
        ana.show()
        return ana

    with patch.object(QMessageBox, "information"), patch.object(QMessageBox, "warning"), \
            patch.object(QMessageBox, "critical"):
        yield ac
    for oge in acik:
        if hasattr(oge, "_yetki_zamanlayici"):
            oge._yetki_zamanlayici.stop()
            oge._oturum_zamanlayici.stop()
            oge.deleteLater()
        else:
            oge.stop()


def sayfaya_git(ana, ad):
    ana.nav_btnler[ad].click()
    QApplication.processEvents()


def test_ust_cubuk_acilan_sayfanin_adini_gosterir(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE", "ODA_DURUMU_GORUNTULE"])
    assert ana.ust_baslik.text() == "TKYS"
    sayfaya_git(ana, "Randevu Yönetimi")
    assert ana.ust_sayfa.text().endswith("Randevu Yönetimi")
    assert ana.ust_sayfa.toolTip() == ""                                  # sayfa adında ipucu kutusu yok
    sayfaya_git(ana, "Oda Kullanımı")
    assert ana.ust_sayfa.text().endswith("Oda Kullanımı")


def test_sayfalarda_buyuk_baslik_karti_yok(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE", "ODA_DURUMU_GORUNTULE", "RANDEVU_OLUSTUR"])
    sayfaya_git(ana, "Randevu Yönetimi")
    adlar = {w.objectName() for w in ana.stack.currentWidget().findChildren(QLabel)}
    assert not adlar & {"modulBaslik", "modulAlt", "modulIkon", "rozetYetki", "rozetOkunur"}


def test_salt_okunur_etiketi_yok_islem_yetkisi_olmayan_sayfada_dugme_cikmaz(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE"])                    # görüntüleyebilir, işlem yetkisi yok
    sayfaya_git(ana, "Randevu Yönetimi")
    assert not hasattr(ana, "ust_salt_okunur")                # üst çubukta "salt okunur" etiketi hiçbir sayfada yok
    assert not ana.stack.currentWidget().findChildren(QPushButton, "aksiyon")


def test_islem_yetkisi_olan_sayfada_dugmeler_var(pencere_ac):
    ana = pencere_ac(["TAKVIM_GORUNTULE", "RANDEVU_OLUSTUR"])
    sayfaya_git(ana, "Randevu Yönetimi")
    etiketler = [b.text() for b in ana.stack.currentWidget().findChildren(QPushButton, "aksiyon")]
    assert any("Yeni Randevu" in e for e in etiketler)


def test_islem_dugmeleri_kucuk_ve_sag_yaslidir(pencere_ac):
    assert "padding: 7px 16px" in mw.STIL and "font-size: 12px" in mw.STIL.split("QPushButton#aksiyon {")[1].split("}")[0]
    ana = pencere_ac(["TAKVIM_GORUNTULE", "RANDEVU_OLUSTUR", "RANDEVU_DUZENLE", "RANDEVU_IPTAL"])
    sayfaya_git(ana, "Randevu Yönetimi")
    sayfa = ana.stack.currentWidget()
    dugmeler = sayfa.findChildren(QPushButton, "aksiyon")
    assert len(dugmeler) == 3            # Yeni Randevu, Düzenle, İptal Et (Tamamlandı/Gelmedi durum rozetinden)
    sag = max(d.mapTo(sayfa, d.rect().topRight()).x() for d in dugmeler)
    sol = min(d.mapTo(sayfa, d.rect().topLeft()).x() for d in dugmeler)
    assert sag > sayfa.width() - 60 and sag <= sayfa.width()          # sağa yaslı: son düğme sayfanın sağ kenarında
