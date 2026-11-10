"""Ana paneldeki özet kartları: tıklanınca ilgili sayfa açılır; cihaz durum kartları envanteri o duruma göre süzer.

Gerçek API kullanılmaz; sunucu cevapları ve sayfa açma işlevleri taklit edilir.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import cihaz_ekranlari
import main_window as mw
from cihaz_ekranlari import CihazYonetimEkrani
from dashboard_ekrani import KART_HEDEFLERI, DashboardEkrani, TiklanabilirKart


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def pano_olustur(qt_app, cihaz_ozeti=True, **kw):
    with patch.object(DashboardEkrani, "_getir",
                      side_effect=lambda yol: {"/api/dashboard/ozet": {}}.get(yol, [])):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=cihaz_ozeti, **kw)
    pano.zamanlayici.stop()
    pano.resize(1300, 900)
    pano.show()
    return pano


def kart_tikla(pano, anahtar):
    kart = pano.kart_widgetleri[list(pano.kartlar).index(anahtar)]
    QTest.mouseClick(kart, Qt.LeftButton, Qt.NoModifier, kart.rect().center())
    return kart


def kapat(pano):
    pano.close()
    pano.deleteLater()


# --------------------------------------------------------------------------- hedefler
def test_her_karta_dogru_sayfa_ve_durum_filtresi_atanmis():
    assert KART_HEDEFLERI["randevu"][:2] == ("Randevu Takvimi", None)
    assert KART_HEDEFLERI["rezervasyon"][:2] == ("Cihaz Rezervasyonu", None)
    assert KART_HEDEFLERI["aktif_cihaz"][:2] == ("Cihaz Envanteri", "Kullanima_Hazir")
    assert KART_HEDEFLERI["bakimdaki_cihaz"][:2] == ("Cihaz Envanteri", "Bakimda")
    assert KART_HEDEFLERI["kalibrasyondaki_cihaz"][:2] == ("Cihaz Envanteri", "Kalibrasyonda")
    assert KART_HEDEFLERI["arizali_cihaz"][:2] == ("Cihaz Envanteri", "Arizali")


def test_her_kart_tiklaninca_kendi_hedefini_acar(qt_app):
    acilan = []
    pano = pano_olustur(qt_app, kart_ac=lambda sayfa, durum: acilan.append((sayfa, durum)))
    for anahtar in pano.kartlar:
        kart_tikla(pano, anahtar)
    assert acilan == [KART_HEDEFLERI[a][:2] for a in pano.kartlar]
    kapat(pano)


def test_kartlar_tiklanabilir_gorunur_imlec_ve_ipucu(qt_app):
    pano = pano_olustur(qt_app, kart_ac=lambda *_: None)
    for kart in pano.kart_widgetleri:
        assert isinstance(kart, TiklanabilirKart)
        assert kart.cursor().shape() == Qt.PointingHandCursor
        assert kart.toolTip()
        assert kart.property("tiklanabilir") == "true"
    kapat(pano)


# --------------------------------------------------------------------------- yetki / eski davranış
def test_kart_ac_verilmezse_kartlar_eskisi_gibi_tiklanmaz(qt_app):
    pano = pano_olustur(qt_app)
    for anahtar in pano.kartlar:
        kart = kart_tikla(pano, anahtar)
        assert kart.cursor().shape() == Qt.ArrowCursor and kart.toolTip() == ""
    kapat(pano)


def test_yetkisiz_sayfanin_karti_tiklanmaz_digerleri_tiklanir(qt_app):
    acilan = []
    pano = pano_olustur(qt_app, kart_ac=lambda sayfa, durum: acilan.append((sayfa, durum)),
                        sayfa_izinli_mi=lambda sayfa: sayfa != "Cihaz Envanteri")
    kart_tikla(pano, "arizali_cihaz")
    kart_tikla(pano, "aktif_cihaz")
    assert acilan == []                                             # envanter izni yok
    kart_tikla(pano, "randevu")
    assert acilan == [("Randevu Takvimi", None)]
    assert pano.kart_widgetleri[0].property("tiklanabilir") == "true"
    assert pano.kart_widgetleri[-1].property("tiklanabilir") == "false"
    kapat(pano)


def test_sol_tus_disindaki_ve_kartin_disinda_birakilan_tiklama_sayilmaz(qt_app):
    acilan = []
    pano = pano_olustur(qt_app, kart_ac=lambda sayfa, durum: acilan.append(sayfa))
    kart = pano.kart_widgetleri[0]
    QTest.mouseClick(kart, Qt.RightButton, Qt.NoModifier, kart.rect().center())
    assert acilan == []
    QTest.mousePress(kart, Qt.LeftButton, Qt.NoModifier, kart.rect().center())
    QTest.mouseRelease(kart, Qt.LeftButton, Qt.NoModifier, kart.rect().center() + kart.rect().bottomRight() * 3)
    assert acilan == []                                             # basılıp dışarıda bırakıldı: iptal
    kapat(pano)


def test_randevu_rolunde_yalnizca_randevu_karti_vardir_ve_tiklanir(qt_app):
    acilan = []
    pano = pano_olustur(qt_app, cihaz_ozeti=False, kart_ac=lambda sayfa, durum: acilan.append((sayfa, durum)))
    assert list(pano.kartlar) == ["randevu"]
    kart_tikla(pano, "randevu")
    assert acilan == [("Randevu Takvimi", None)]
    kapat(pano)


# --------------------------------------------------------------------------- envanter filtresi
CIHAZLAR = [
    {"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG Cihazı", "durum": "Arizali", "marka_model": "A"},
    {"cihaz_id": 2, "envanter_kodu": "E-2", "cihaz_adi": "EKG Cihazı", "durum": "Kullanima_Hazir", "marka_model": "B"},
    {"cihaz_id": 3, "envanter_kodu": "E-3", "cihaz_adi": "Biyofeedback", "durum": "Bakimda", "marka_model": "C"},
    {"cihaz_id": 4, "envanter_kodu": "E-4", "cihaz_adi": "Işık Cihazı", "durum": "Arizali", "marka_model": "D"},
]


def envanter(qt_app, cihazlar=CIHAZLAR):
    cevap = MagicMock(status_code=200)
    cevap.json.return_value = cihazlar
    cevap._tkys_oturum_reddedildi = False
    with patch.object(cihaz_ekranlari, "oturum_kontrollu_istek", return_value=cevap), \
            patch.object(cihaz_ekranlari, "oturum_hatasi_mi", return_value=False):
        e = CihazYonetimEkrani("http://x", "T", yetkili_mi=True)
    e.show()
    return e


def gorunen_kodlar(e):
    return [e.tablo.item(i, 0).text() for i in range(e.tablo.rowCount()) if not e.tablo.isRowHidden(i)]


def test_filtre_yokken_hepsi_gorunur_serit_gizli(qt_app):
    e = envanter(qt_app)
    assert gorunen_kodlar(e) == ["E-1", "E-2", "E-3", "E-4"]
    assert not e.filtre_seridi.isVisible()
    e.close()


def test_durum_filtresi_yalnizca_o_durumdaki_cihazlari_gosterir(qt_app):
    e = envanter(qt_app)
    e.durum_filtrele("Arizali")
    assert gorunen_kodlar(e) == ["E-1", "E-4"]
    assert e.filtre_seridi.isVisible() and "Arızalı" in e.lbl_filtre.text()
    e.close()


def test_filtre_aramayla_birlikte_calisir(qt_app):
    e = envanter(qt_app)
    e.durum_filtrele("Arizali")
    e.arama.setText("EEG")
    assert gorunen_kodlar(e) == ["E-1"]
    e.arama.setText("")
    assert gorunen_kodlar(e) == ["E-1", "E-4"]
    e.close()


def test_filtreyi_kaldir_dugmesi_hepsini_geri_getirir(qt_app):
    e = envanter(qt_app)
    e.durum_filtrele("Bakimda")
    QTest.mouseClick(e.btn_filtre_kaldir, Qt.LeftButton)
    assert gorunen_kodlar(e) == ["E-1", "E-2", "E-3", "E-4"]
    assert not e.filtre_seridi.isVisible() and e.durum_filtresi is None
    e.close()


def test_filtreye_uyan_cihaz_yoksa_aciklayici_mesaj_gosterilir_ve_kalkinca_tablo_geri_gelir(qt_app):
    e = envanter(qt_app)
    e.durum_filtrele("Kalibrasyonda")                              # envanterde bu durumda cihaz yok
    assert e.bos_mesaj.isVisible() and "uyan cihaz yok" in e.bos_mesaj.text() and not e.tablo.isVisible()
    e.durum_filtresini_temizle()
    assert e.tablo.isVisible() and not e.bos_mesaj.isVisible()
    e.close()


def test_yenilemede_filtre_korunur(qt_app):
    e = envanter(qt_app)
    e.durum_filtrele("Arizali")
    cevap = MagicMock(status_code=200)
    cevap.json.return_value = CIHAZLAR
    with patch.object(cihaz_ekranlari, "oturum_kontrollu_istek", return_value=cevap), \
            patch.object(cihaz_ekranlari, "oturum_hatasi_mi", return_value=False):
        e.verileri_yukle()
    assert gorunen_kodlar(e) == ["E-1", "E-4"]
    e.close()


def test_hic_cihaz_yokken_eski_bos_mesaj_korunur(qt_app):
    e = envanter(qt_app, [])
    assert e.bos_mesaj.isVisible() and e.bos_mesaj.text() == "Henüz cihaz kaydı yok."
    e.close()


# --------------------------------------------------------------------------- ana pencere
def ana_pencere_taklidi(ekran):
    ana = MagicMock()
    ana.aktif_cihaz_ekrani = ekran
    return ana


def test_kartan_envantere_gidilince_sayfa_acilir_ve_filtre_uygulanir():
    ekran = MagicMock()
    ana = ana_pencere_taklidi(ekran)
    mw.AnaPencere._karttan_sayfaya_git(ana, "Cihaz Envanteri", "Arizali")
    ana._bildirimden_sayfaya_git.assert_called_once_with("Cihaz Envanteri")
    ekran.durum_filtrele.assert_called_once_with("Arizali")


def test_kartan_baska_sayfaya_gidilince_envanter_filtresine_dokunulmaz():
    ekran = MagicMock()
    ana = ana_pencere_taklidi(ekran)
    mw.AnaPencere._karttan_sayfaya_git(ana, "Randevu Takvimi", None)
    ana._bildirimden_sayfaya_git.assert_called_once_with("Randevu Takvimi")
    ekran.durum_filtrele.assert_not_called()


def test_menuden_envantere_gelinirse_eski_filtre_temizlenir():
    ekran = MagicMock()
    ana = MagicMock()
    ana.aktif_cihaz_ekrani = ekran
    ana.sayfa_bilgi = [("Ana Kontrol Paneli", ""), ("Cihaz Envanteri", "")]
    mw.AnaPencere.sayfa_ac(ana, 1)
    ekran.durum_filtresini_temizle.assert_called_once()
    ekran.reset_mock()
    mw.AnaPencere.sayfa_ac(ana, 0)
    ekran.durum_filtresini_temizle.assert_not_called()


def test_ana_pencere_panele_kart_ac_baglar():
    kaynak = open("main_window.py", encoding="utf-8").read()
    assert "kart_ac=self._karttan_sayfaya_git" in kaynak
