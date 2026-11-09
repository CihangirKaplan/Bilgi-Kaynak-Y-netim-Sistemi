"""Ana paneldeki bildirimler: tıklanınca ilgili sayfa açılır; yetkisiz olunan sayfanın bildirimi hiç gösterilmez.

Gerçek API kullanılmaz; sunucu cevapları ve sayfa açma işlevleri taklit edilir.
"""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea

from dashboard_ekrani import DashboardEkrani


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


ISLEMLER = [
    {"cihaz_adi": "E1 - EKG", "islem_turu": "Kalibrasyon", "kalan_gun": -54, "tarih": "16.09.2026"},
    {"cihaz_adi": "E2 - EEG", "islem_turu": "Bakım", "kalan_gun": -24, "tarih": "16.10.2026"},
]


def pano_olustur(qt_app, islemler=ISLEMLER, ariza=4, **kw):
    with patch.object(DashboardEkrani, "_getir",
                      side_effect=lambda yol: {"/api/dashboard/ozet": {"acik_ariza_sayisi": ariza}}.get(yol, [])):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=True, **kw)
    pano.zamanlayici.stop()
    pano.islemler = list(islemler)
    pano.ozet = {"acik_ariza_sayisi": ariza}
    pano._bildirimleri_olustur()
    return pano


def dugmeler(pano):
    return pano.bildirim_paneli.findChildren(QPushButton)


def metinler(pano):
    return [w.text() for tur in (QLabel, QPushButton) for w in pano.bildirim_paneli.findChildren(tur)]


def kapat(pano):
    pano.close()
    pano.deleteLater()


# --------------------------------------------------------------------------- tıklama
def test_her_bildirim_tiklaninca_kendi_sayfasini_acar(qt_app):
    acilan = []
    pano = pano_olustur(qt_app, sayfa_ac=acilan.append)
    for d in dugmeler(pano):
        d.click()
    assert acilan == ["Arıza Kayıtları", "Kalibrasyon", "Bakım Kayıtları"]
    kapat(pano)


def test_bildirim_satirlari_tiklanabilir_gorunur_ve_ok_isareti_tasir(qt_app):
    pano = pano_olustur(qt_app, sayfa_ac=lambda s: None)
    for d in dugmeler(pano):
        assert d.cursor().shape() == Qt.PointingHandCursor and d.text().endswith("→")
        assert d.toolTip().endswith("sayfasına git")
    kapat(pano)


def test_gecikme_yazilari_korunur(qt_app):
    pano = pano_olustur(qt_app, sayfa_ac=lambda s: None)
    t = " | ".join(metinler(pano))
    assert "4 açık arıza kaydı çözüm bekliyor." in t
    assert "E1 - EKG  —  Kalibrasyon 54 gün gecikti (16.09.2026)" in t and "Bildirimler  (3)" in t
    kapat(pano)


def test_yonlendirme_islevi_verilmemisse_tiklamak_hata_vermez(qt_app):
    pano = pano_olustur(qt_app)
    for d in dugmeler(pano):
        d.click()
    kapat(pano)


# ----------------------------------------------------------------------- yetki
def test_yetkisiz_olunan_sayfanin_bildirimi_gosterilmez_baska_sayfaya_da_yonlenmez(qt_app):
    acilan = []
    izinli = {"Bakım Kayıtları"}                                     # Kalibrasyon ve Arıza sayfasına yetki yok
    pano = pano_olustur(qt_app, sayfa_ac=acilan.append, sayfa_izinli_mi=izinli.__contains__)
    t = " | ".join(metinler(pano))
    assert "Kalibrasyon" not in t and "açık arıza" not in t
    assert "E2 - EEG  —  Bakım 24 gün gecikti" in t and "Bildirimler  (1)" in t
    for d in dugmeler(pano):
        d.click()
    assert acilan == ["Bakım Kayıtları"]
    kapat(pano)


def test_hicbir_sayfaya_yetki_yoksa_bos_bildirim_mesaji_gorunur(qt_app):
    pano = pano_olustur(qt_app, sayfa_ac=lambda s: None, sayfa_izinli_mi=lambda s: False)
    assert dugmeler(pano) == [] and any("Bekleyen uyarı yok" in m for m in metinler(pano))
    kapat(pano)


def test_acik_ariza_yoksa_ariza_bildirimi_gosterilmez(qt_app):
    pano = pano_olustur(qt_app, ariza=0, sayfa_ac=lambda s: None)
    assert not any("açık arıza" in m for m in metinler(pano))
    kapat(pano)


def test_izin_sorusu_her_sayfa_icin_sorulur(qt_app):
    sorulan = []
    pano = pano_olustur(qt_app, sayfa_izinli_mi=lambda s: sorulan.append(s) or True)
    assert {"Arıza Kayıtları", "Kalibrasyon", "Bakım Kayıtları"} <= set(sorulan)
    kapat(pano)


# ------------------------------------------------------------- çok bildirim: kaydırma çubuğu
def cok_islem(n):
    return [{"cihaz_adi": f"E{i}", "islem_turu": "Bakım", "kalan_gun": -i, "tarih": "01.01.2026"} for i in range(n)]


def kaydirma_alani(pano):
    return pano.bildirim_paneli.findChild(QScrollArea, "bildirimKaydirma")


def ipucu(pano):
    return pano.bildirim_paneli.findChild(QLabel, "bildirimKaydirmaIpucu")


def test_sinira_kadar_bildirimde_kaydirma_alani_ve_ipucu_yoktur(qt_app):
    pano = pano_olustur(qt_app, islemler=cok_islem(4), ariza=1, sayfa_ac=lambda s: None)       # tam 5 satır
    assert kaydirma_alani(pano) is None and ipucu(pano) is None
    assert len(dugmeler(pano)) == 5
    kapat(pano)


def test_sinirdan_fazla_bildirimde_hepsi_kaydirma_alaninda_listelenir(qt_app):
    pano = pano_olustur(qt_app, islemler=cok_islem(10), ariza=0, sayfa_ac=lambda s: None)      # 10 bildirim
    alan = kaydirma_alani(pano)
    assert alan is not None and len(alan.findChildren(QPushButton)) == 10                       # hiçbiri kesilmez
    assert not any("bildirim daha" in m for m in metinler(pano))                                # eski "… ve N daha" satırı yok
    assert any("Bildirimler  (10)" in m for m in metinler(pano))
    kapat(pano)


def test_kaydirma_alani_en_fazla_5_satir_yukseklikte_ve_cubuk_hep_gorunur(qt_app):
    pano = pano_olustur(qt_app, islemler=cok_islem(10), ariza=0, sayfa_ac=lambda s: None)
    alan = kaydirma_alani(pano)
    satir = alan.findChildren(QPushButton)[0].sizeHint().height()
    assert alan.height() == 5 * satir + 4 * 8 + 4
    assert alan.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn
    assert alan.horizontalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
    kapat(pano)


def test_kaydirma_cubugu_buyuk_ve_renkli_stillenir():
    import dashboard_ekrani
    stil = dashboard_ekrani.KAYDIRMA_CUBUGU_STILI
    assert "width: 18px" in stil and "#2563EB" in stil and "min-height: 70px" in stil


def test_ipucu_rozeti_toplam_bildirim_sayisini_soyler(qt_app):
    pano = pano_olustur(qt_app, islemler=cok_islem(10), ariza=0, sayfa_ac=lambda s: None)
    assert ipucu(pano).text() == "⇅  10 bildirim var — kaydırarak hepsini görün"
    kapat(pano)


def test_kaydirma_alanindaki_alt_bildirim_de_tiklaninca_sayfa_acar(qt_app):
    acilan = []
    pano = pano_olustur(qt_app, islemler=cok_islem(10), ariza=0, sayfa_ac=acilan.append)
    kaydirma_alani(pano).findChildren(QPushButton)[-1].click()          # kaydırmadan görünmeyen son satır
    assert acilan == ["Bakım Kayıtları"]
    kapat(pano)


def test_bildirimler_azalinca_kaydirma_alani_ve_ipucu_kalkar(qt_app):
    pano = pano_olustur(qt_app, islemler=cok_islem(10), ariza=0, sayfa_ac=lambda s: None)
    pano.islemler = cok_islem(2)
    pano._bildirimleri_olustur()
    assert kaydirma_alani(pano) is None and ipucu(pano) is None and len(dugmeler(pano)) == 2
    kapat(pano)


# ----------------------------------------------- alttaki "Yaklaşan ve Geciken Bakım/Kalibrasyonlar" tablosu
TABLO_ISLEMLERI = [
    {"cihaz_adi": "E1 - EKG", "islem_turu": "Kalibrasyon", "kalan_gun": -54, "tarih": "16.09.2026"},
    {"cihaz_adi": "E2 - EEG", "islem_turu": "Bakım", "kalan_gun": -24, "tarih": "16.10.2026"},
    {"cihaz_adi": "E3 - Defibrilatör", "islem_turu": "Kalibrasyon", "kalan_gun": 11, "tarih": "20.11.2026"},
]


def tablo_pano(qt_app, islemler=TABLO_ISLEMLERI, **kw):
    """Sunucudan islemleri 'yaklasan-islemler' ucundan alan pano (tablo ilk yüklemede dolar)."""
    def getir(yol):
        return {"/api/dashboard/ozet": {"acik_ariza_sayisi": 0}, "/api/dashboard/yaklasan-islemler": list(islemler)}.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        pano = DashboardEkrani("http://x", "T", cihaz_ozeti=True, **kw)
    pano.zamanlayici.stop()
    return pano


def hucreye_tikla(pano, satir, kolon):
    """Gerçek fare tıklaması: hücrenin ortasına, tablonun görünür alanına tıklar."""
    from PySide6.QtTest import QTest
    tablo = pano.tablo_islem
    tablo.setVisible(True)
    tablo.resize(900, tablo.height())
    merkez = tablo.visualRect(tablo.model().index(satir, kolon)).center()
    QTest.mouseClick(tablo.viewport(), Qt.LeftButton, Qt.NoModifier, merkez)


def tablo_metni(pano, satir, kolon):
    oge = pano.tablo_islem.item(satir, kolon)
    return oge.text() if oge is not None else None


def test_tablo_satirina_tiklaninca_o_satirin_sayfasi_acilir(qt_app):
    acilan = []
    pano = tablo_pano(qt_app, sayfa_ac=acilan.append)
    hucreye_tikla(pano, 0, 0)          # Kalibrasyon satırı
    hucreye_tikla(pano, 1, 1)          # Bakım satırı (farklı hücre)
    hucreye_tikla(pano, 2, 2)          # Kalibrasyon satırı (tarih hücresi)
    assert acilan == ["Kalibrasyon", "Bakım Kayıtları", "Kalibrasyon"]
    kapat(pano)


def test_son_sutundaki_kalan_sure_hapina_tiklamak_da_sayfayi_acar(qt_app):
    """Hap, hücreye konan ayrı bir widget'tır; tıklama tabloya iletilmelidir (pencere gösterilip düzeni kurulur)."""
    from PySide6.QtTest import QTest
    acilan = []
    pano = tablo_pano(qt_app, sayfa_ac=acilan.append)
    pano.resize(1300, 900)
    pano.show()
    pano.grab()                                                       # düzeni kurar; gerçek konumlar oluşur
    tablo = pano.tablo_islem
    hap = tablo.viewport().childAt(tablo.visualRect(tablo.model().index(1, 3)).center())
    assert isinstance(hap, QLabel) and hap.text() == "24 gün gecikti"
    QTest.mouseClick(hap, Qt.LeftButton, Qt.NoModifier, hap.rect().center())
    assert acilan == ["Bakım Kayıtları"]
    kapat(pano)


def test_tablo_yetkisiz_olunan_sayfanin_satirlarini_gostermez(qt_app):
    izinli = {"Bakım Kayıtları"}                                      # Kalibrasyon sayfasına yetki yok
    acilan = []
    pano = tablo_pano(qt_app, sayfa_ac=acilan.append, sayfa_izinli_mi=izinli.__contains__)
    assert pano.tablo_islem.rowCount() == 1 and tablo_metni(pano, 0, 0) == "E2 - EEG"
    hucreye_tikla(pano, 0, 0)
    assert acilan == ["Bakım Kayıtları"]
    kapat(pano)


def test_tabloda_satir_sirasi_korunur_ve_hedefler_dogru_satira_baglanir(qt_app):
    izinli = {"Kalibrasyon"}                                          # Bakım sayfasına yetki yok -> ortadaki satır düşer
    acilan = []
    pano = tablo_pano(qt_app, sayfa_ac=acilan.append, sayfa_izinli_mi=izinli.__contains__)
    assert [tablo_metni(pano, i, 0) for i in range(pano.tablo_islem.rowCount())] == ["E1 - EKG", "E3 - Defibrilatör"]
    hucreye_tikla(pano, 1, 0)                                         # ikinci görünen satır = E3
    assert acilan == ["Kalibrasyon"]
    kapat(pano)


def test_hicbir_sayfaya_yetki_yoksa_tablo_bos_mesajini_gosterir(qt_app):
    pano = tablo_pano(qt_app, sayfa_ac=lambda s: None, sayfa_izinli_mi=lambda s: False)
    assert pano.tablo_islem.rowCount() == 0
    assert not pano.lbl_islem_bos.isHidden() and "bakım veya kalibrasyon yok" in pano.lbl_islem_bos.text()
    kapat(pano)


def test_tablo_satirlari_tiklanabilir_gorunur_ve_ipucu_tasir(qt_app):
    pano = tablo_pano(qt_app, sayfa_ac=lambda s: None)
    assert pano.tablo_islem.viewport().cursor().shape() == Qt.PointingHandCursor
    assert pano.tablo_islem.item(0, 0).toolTip() == "Kalibrasyon sayfasına git"
    assert pano.tablo_islem.item(1, 2).toolTip() == "Bakım Kayıtları sayfasına git"
    assert pano.tablo_islem.cellWidget(1, 3).toolTip() == "Bakım Kayıtları sayfasına git"
    kapat(pano)


def test_yonlendirme_islevi_yoksa_tablo_tiklanabilir_gorunmez_ve_hata_vermez(qt_app):
    pano = tablo_pano(qt_app)
    assert pano.tablo_islem.viewport().cursor().shape() != Qt.PointingHandCursor
    assert pano.tablo_islem.item(0, 0).toolTip() == ""
    hucreye_tikla(pano, 0, 0)
    kapat(pano)


def test_tablo_yenilenince_hedefler_yeni_satirlara_gore_guncellenir(qt_app):
    acilan = []
    pano = tablo_pano(qt_app, sayfa_ac=acilan.append)
    yeni = [{"cihaz_adi": "E9", "islem_turu": "Bakım", "kalan_gun": 3, "tarih": "12.11.2026"}]
    with patch.object(DashboardEkrani, "_getir", side_effect=lambda y: list(yeni)):
        pano._islemleri_yukle()
    assert pano.tablo_islem.rowCount() == 1 and tablo_metni(pano, 0, 0) == "E9"
    hucreye_tikla(pano, 0, 0)
    assert acilan == ["Bakım Kayıtları"]
    kapat(pano)


def test_tablo_ve_bildirim_ayni_yetki_kuralini_kullanir(qt_app):
    izinli = {"Kalibrasyon"}
    pano = tablo_pano(qt_app, sayfa_ac=lambda s: None, sayfa_izinli_mi=izinli.__contains__)
    pano._bildirimleri_olustur()
    bildirim_cihazlari = {d.text().split("—")[0].split("  ")[-1].strip() for d in dugmeler(pano)}
    tablo_cihazlari = {tablo_metni(pano, i, 0) for i in range(pano.tablo_islem.rowCount())}
    assert any("E1 - EKG" in m for m in metinler(pano)) and not any("E2 - EEG" in m for m in metinler(pano))
    assert tablo_cihazlari == {"E1 - EKG", "E3 - Defibrilatör"}
    kapat(pano)


def test_dashboard_kodunda_lambda_ile_baglanti_yoktur():
    """Döngüsel referans, kapanışta Shiboken çökmesine yol açıyordu; bağlantılar yuvaya yapılır."""
    kaynak = Path("dashboard_ekrani.py").read_text(encoding="utf-8")
    assert "connect(lambda" not in kaynak


# ---------------------------------------------------------------- ana pencere izin kuralı
@pytest.fixture
def temiz_yetkiler():
    import main_window as mw
    mw._SUNUCU_YETKILERI.clear()
    yield mw
    mw._SUNUCU_YETKILERI.clear()


def izinli_mi(mw, rol, sayfa):
    return mw.AnaPencere._sayfa_izinli_mi(SimpleNamespace(aktif_rol=rol), sayfa)


def test_sayfa_izni_menudeki_izne_gore_belirlenir(temiz_yetkiler):
    """Bakım ve Kalibrasyon sayfaları CIHAZ_ENVANTER_YONET, Arıza sayfası ARIZA_KAYITLARI_YONET ister."""
    mw = temiz_yetkiler
    sayfalar = ("Arıza Kayıtları", "Kalibrasyon", "Bakım Kayıtları")
    mw.yetkileri_ayarla("memur", ["ARIZA_KAYITLARI_YONET", "CIHAZ_ENVANTER_YONET"])
    assert all(izinli_mi(mw, "memur", s) for s in sayfalar)
    mw.yetkileri_ayarla("memur", ["CIHAZ_ENVANTER_YONET"])
    assert not izinli_mi(mw, "memur", "Arıza Kayıtları")
    assert izinli_mi(mw, "memur", "Kalibrasyon") and izinli_mi(mw, "memur", "Bakım Kayıtları")
    mw.yetkileri_ayarla("memur", ["ARIZA_KAYITLARI_YONET"])
    assert izinli_mi(mw, "memur", "Arıza Kayıtları")
    assert not izinli_mi(mw, "memur", "Kalibrasyon") and not izinli_mi(mw, "memur", "Bakım Kayıtları")


def test_sunucu_yetkisi_yokken_eski_tabloya_donulur_ve_psikolog_goremez(temiz_yetkiler):
    mw = temiz_yetkiler
    assert izinli_mi(mw, "memur", "Arıza Kayıtları")
    assert not izinli_mi(mw, "psikolog", "Arıza Kayıtları")


def test_izinsiz_menu_ogesi_ve_bilinmeyen_sayfa_icin_kural(temiz_yetkiler):
    mw = temiz_yetkiler
    assert izinli_mi(mw, "ogrenci", "Ana Kontrol Paneli") is True      # izin=None: herkese açık
    assert izinli_mi(mw, "admin", "Olmayan Sayfa") is False


def test_ana_pencere_dashboard_yonlendirme_islevlerini_baglar():
    import inspect
    import main_window as mw
    kaynak = inspect.getsource(mw.AnaPencere.sayfa_dashboard)
    for parca in ("sayfa_ac=self._bildirimden_sayfaya_git", "sayfa_izinli_mi=self._sayfa_izinli_mi"):
        assert parca in kaynak
