"""Liste hızı: sunucu `limit` parametresi, istemcide kademeli yükleme ("daha fazla yükle") ve hızlı tablo doldurma."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QTableWidget

import client.cihaz_ariza_ekranlari as ariza_modulu
import client.cihaz_bakim_ekranlari as bakim_modulu
import client.cihaz_kalibrasyon_ekranlari as kalib_modulu
import client.cihaz_rezervasyon_ekranlari as rez_modulu
from client.liste_siniri import ADIM, ILK_YUKLEME, SUNUCU_EN_COK, ListeSiniri, daha_fazla_guncelle
from client.tablo_tasarimi import daha_fazla_dugmesi, hizli_doldur
from server.sunucu import LISTE_UST_SINIRI, liste_siniri_coz, liste_toplamini_bildir


@pytest.fixture(scope="module", autouse=True)
def qt_app():
    return QApplication.instance() or QApplication([])


def test_istemci_ve_sunucu_ust_sinirlari_ayni():
    assert SUNUCU_EN_COK == LISTE_UST_SINIRI == 5000 and ILK_YUKLEME == ADIM == 300


@pytest.mark.parametrize("gelen,beklenen", [(None, 5000), (300, 300), (1, 1), (5000, 5000), (0, 5000), (-5, 5000),
                                             (5001, 5000), (True, 5000), ("300", 5000)])
def test_sunucu_limit_cozumleme(gelen, beklenen):
    assert liste_siniri_coz(gelen) == beklenen


def test_sunucu_toplam_basligi_istenen_limite_gore_yazilir():
    cur = MagicMock(); cur.fetchone.return_value = (1234,)
    yanit = MagicMock(); yanit.headers = {}
    liste_toplamini_bildir(cur, yanit, 299, "SELECT COUNT(*) FROM t", 300)           # sınırın altı: kesilmedi, sayım yok
    assert yanit.headers == {} and not cur.execute.called
    liste_toplamini_bildir(cur, yanit, 300, "SELECT COUNT(*) FROM t", 300)           # sınıra ulaştı: toplam bildirilir
    assert yanit.headers and cur.execute.called


def test_liste_siniri_artis_ve_ust_sinir():
    s = ListeSiniri()
    assert s.parametreler() == {"limit": 300} and s.artirilabilir_mi(300, 301) and not s.artirilabilir_mi(300, 300)
    for _ in range(40):
        s.artir()
    assert s.limit == SUNUCU_EN_COK and not s.artirilabilir_mi(5000, 9000)           # sunucu üst sınırından öteye gidilmez


def test_daha_fazla_dugmesi_gorunurluk_ve_metin():
    d = daha_fazla_dugmesi(lambda: None); s = ListeSiniri()
    d.setParent(None)
    daha_fazla_guncelle(d, s, 300, 1000)
    assert not d.isHidden() and "300" in d.text()
    daha_fazla_guncelle(d, s, 300, 350)
    assert "50" in d.text()                                                          # kalan kayıttan fazlası yazılmaz
    daha_fazla_guncelle(d, s, 300, 300)
    assert d.isHidden()


def test_hizli_doldur_tabloyu_geri_gosterir_hata_olsa_bile():
    t = QTableWidget(); t.show(); QApplication.processEvents()
    with hizli_doldur(t):
        assert t.isHidden() and not t.updatesEnabled()
    assert t.isVisible() and t.updatesEnabled()
    with pytest.raises(RuntimeError):
        with hizli_doldur(t):
            raise RuntimeError("x")
    assert t.isVisible() and t.updatesEnabled()
    t.hide()
    with hizli_doldur(t):
        pass
    assert t.isHidden()                                                              # zaten gizliyse gösterilmez


def _yanit(veri, toplam=None):
    y = MagicMock(status_code=200, _tkys_oturum_reddedildi=False)
    y.json.return_value = veri
    y.headers = {"X-Toplam-Kayit": str(toplam)} if toplam else {}
    return y


EKRANLAR = [
    (bakim_modulu, "BakimYonetimEkrani", "oturum_kontrollu_istek", lambda i: {"bakim_id": i, "cihaz_adi": f"C{i}", "bakim_yapan_kisi": "x", "yapilan_islem": "y"}),
    (kalib_modulu, "KalibrasyonYonetimEkrani", "oturum_kontrollu_istek", lambda i: {"kalibrasyon_id": i, "cihaz_adi": f"C{i}"}),
    (ariza_modulu, "ArizaYonetimEkrani", "oturum_kontrollu_istek", lambda i: {"ariza_id": i, "cihaz_adi": f"C{i}", "durum": "Açık", "aciliyet": "Orta", "sorun_basligi": "s"}),
    (rez_modulu, "RezervasyonYonetimEkrani", "oturum_kontrollu_istek", lambda i: {"rezervasyon_id": i, "cihaz_adi": f"C{i}", "durum": "Aktif"}),
]


@pytest.mark.parametrize("modul,sinif,istek,satir", EKRANLAR)
def test_ekran_limit_gonderir_ve_daha_fazla_yukler(modul, sinif, istek, satir):
    cagrilar = []

    def sahte(yontem, adres, **k):
        cagrilar.append(k.get("params"))
        n = (k.get("params") or {}).get("limit", 5000)
        return _yanit([satir(i) for i in range(1, min(n, 700) + 1)], toplam=700)

    with patch.object(modul, istek, side_effect=sahte):
        e = getattr(modul, sinif)("http://x", "t")
        e.show(); QApplication.processEvents()
        assert cagrilar[-1] == {"limit": 300}
        assert e.tablo.rowCount() == 300 and not e.dahafazla_btn.isHidden()
        e.dahafazla_btn.click(); QApplication.processEvents()
        assert cagrilar[-1] == {"limit": 600} and e.tablo.rowCount() == 600
        e.dahafazla_btn.click(); QApplication.processEvents()
        assert e.tablo.rowCount() == 700 and e.dahafazla_btn.isHidden()              # hepsi yüklendi: düğme kaybolur
        assert e.tablo.isVisible()
    e.close()
