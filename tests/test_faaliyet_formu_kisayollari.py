"""Faaliyet kayıt formu: 'Yeni Faaliyet Türü' ve 'Yeni Birim Ekle' kısayol düğmeleri.

Düğmeler, öğrenci düğmesi gibi ilgili yönetim penceresine gönderir; pencere kapanınca liste yenilenir ve yeni eklenen
kayıt otomatik seçilir. Birim düğmesi yalnızca birim yönetme iznine sahip kullanıcıya görünür.
Gerçek sunucu kullanılmaz; ağ istekleri taklit edilir.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QWidget

import faaliyet_dialog as modul
import main_window
from faaliyet_dialog import FaaliyetEkleDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class SahteSunucu:
    """/api/faaliyetler ve /api/faaliyet-birimleri listelerini tutar; testler listeyi değiştirebilir."""

    def __init__(self):
        self.turler = [{"id": 1, "ad": "Seminer", "puan": 10}, {"id": 2, "ad": "Rehberlik", "puan": 5}]
        self.birimler = [{"id": 1, "ad": "SAAT"}, {"id": 2, "ad": "KISI"}]
        self.oturum_dustu = False
        self.istekler = []

    def __call__(self, metot, url, **kwargs):
        self.istekler.append((metot, url))
        yanit = MagicMock()
        yanit.status_code = 200
        if url.endswith("/api/faaliyetler"):
            yanit.json.return_value = list(self.turler)
        elif url.endswith("/api/faaliyet-birimleri"):
            yanit.json.return_value = list(self.birimler)
        elif url.endswith("/api/ogrenciler-liste"):
            yanit.json.return_value = [{"id": 7, "metin": "Ayşe (1001)", "tur": "GONULLU"}]
        else:
            yanit.json.return_value = []
        return yanit


@pytest.fixture
def sunucu():
    s = SahteSunucu()
    with patch.object(modul, "oturum_kontrollu_istek", s), \
            patch.object(modul, "oturum_hatasi_mi", side_effect=lambda yanit: s.oturum_dustu):
        yield s


def form(qt_app, **kw):
    return FaaliyetEkleDialog("http://s", "t", None, **kw)


# ================================================================ görünürlük
def test_yetkili_kullanicida_uc_kisayol_da_gorunur(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    assert not f.btn_yeni_ogrenci.isHidden() and not f.btn_yeni_faaliyet_turu.isHidden() and not f.btn_yeni_birim.isHidden()
    assert f.btn_yeni_faaliyet_turu.text() == "➕ Yeni Faaliyet Türü" and f.btn_yeni_birim.text() == "➕ Yeni Birim Ekle"


def test_birim_izni_olmayanda_birim_dugmesi_gizli_tur_dugmesi_gorunur(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=False)
    assert f.btn_yeni_birim.isHidden() and not f.btn_yeni_faaliyet_turu.isHidden()


def test_izin_bilgisi_verilmezse_guvenli_varsayilan_birim_dugmesi_gizli(qt_app, sunucu):
    assert form(qt_app).btn_yeni_birim.isHidden()


def test_duzenleme_modunda_butun_kisayollar_gizli(qt_app, sunucu):
    mevcut = {"takip_id": 1, "ogrenci_adi": "Ayşe", "faaliyet_adi": "Seminer", "miktar": "2", "birim_adi": "SAAT"}
    f = form(qt_app, mevcut_veri=mevcut, birim_yonetebilir=True)
    assert f.btn_yeni_ogrenci.isHidden() and f.btn_yeni_faaliyet_turu.isHidden() and f.btn_yeni_birim.isHidden()


def test_kisayollar_ogrenci_dugmesiyle_ayni_yesil_stili_kullanir(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    assert f.btn_yeni_faaliyet_turu.objectName() == f.btn_yeni_birim.objectName() == "btnKisayol"
    assert "btnKisayol" in f.styleSheet() and "#27AE60" in f.styleSheet()


def test_acilista_listeler_dolu_ve_duzenleme_secimi_korunur(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    assert [f.cb_faaliyet.itemText(i) for i in range(f.cb_faaliyet.count())] == ["Seçiniz...", "Seminer (10 Puan)", "Rehberlik (5 Puan)"]
    assert [f.cb_birim.itemText(i) for i in range(f.cb_birim.count())] == ["Seçiniz...", "SAAT", "KISI"]
    mevcut = {"takip_id": 1, "ogrenci_adi": "Ayşe", "faaliyet_adi": "Rehberlik", "miktar": "3", "birim_adi": "KISI"}
    d = form(qt_app, mevcut_veri=mevcut)
    assert d.cb_faaliyet.currentData() == 2 and d.cb_birim.currentData() == 2 and d.sb_miktar.value() == 3


# ================================================================ faaliyet türü kısayolu
def tur_penceresi(sunucu, yeni_turler=None):
    """FaaliyetTurleriDialog yerine geçen sahte pencere; exec() çağrılınca (varsa) sunucuya yeni türler ekler."""
    sahte = MagicMock()

    def exec_():
        if yeni_turler:
            sunucu.turler.extend(yeni_turler)
    sahte.return_value.exec.side_effect = exec_
    return sahte


def test_tur_dugmesi_yonetim_penceresini_form_ebeveyn_olarak_acar(qt_app, sunucu):
    f = form(qt_app)
    sahte = tur_penceresi(sunucu)
    with patch("faaliyet_turleri_dialog.FaaliyetTurleriDialog", sahte):
        f.btn_yeni_faaliyet_turu.click()
    sahte.assert_called_once_with("http://s", "t", f)
    assert sahte.return_value.exec.called


def test_yeni_eklenen_faaliyet_turu_otomatik_secilir(qt_app, sunucu):
    f = form(qt_app)
    f.cb_faaliyet.setCurrentIndex(f.cb_faaliyet.findData(1))               # önce Seminer seçili
    with patch("faaliyet_turleri_dialog.FaaliyetTurleriDialog", tur_penceresi(sunucu, [{"id": 3, "ad": "Atölye", "puan": 20}])):
        f.btn_yeni_faaliyet_turu.click()
    assert f.cb_faaliyet.currentData() == 3 and f.cb_faaliyet.currentText() == "Atölye (20 Puan)"
    assert f.cb_faaliyet.count() == 4                                       # eski öğeler çoğalmadı


def test_birden_fazla_yeni_turde_en_son_eklenen_secilir(qt_app, sunucu):
    f = form(qt_app)
    yeniler = [{"id": 3, "ad": "A", "puan": 1}, {"id": 4, "ad": "B", "puan": 1}]
    with patch("faaliyet_turleri_dialog.FaaliyetTurleriDialog", tur_penceresi(sunucu, yeniler)):
        f.btn_yeni_faaliyet_turu.click()
    assert f.cb_faaliyet.currentData() == 4


def test_yeni_tur_eklenmeden_kapatilirsa_onceki_secim_korunur(qt_app, sunucu):
    f = form(qt_app)
    f.cb_faaliyet.setCurrentIndex(f.cb_faaliyet.findData(2))
    with patch("faaliyet_turleri_dialog.FaaliyetTurleriDialog", tur_penceresi(sunucu)):
        f.btn_yeni_faaliyet_turu.click()
    assert f.cb_faaliyet.currentData() == 2


def test_hicbir_sey_secili_degilken_yeni_eklenmediyse_secimsiz_kalir(qt_app, sunucu):
    f = form(qt_app)
    with patch("faaliyet_turleri_dialog.FaaliyetTurleriDialog", tur_penceresi(sunucu)):
        f.btn_yeni_faaliyet_turu.click()
    assert f.cb_faaliyet.currentData() is None and f.cb_faaliyet.currentText() == "Seçiniz..."


def test_tur_yonetim_penceresi_formdaki_diger_alanlari_bozmaz(qt_app, sunucu):
    f = form(qt_app)
    f.cb_birim.setCurrentIndex(f.cb_birim.findData(2))
    f.sb_miktar.setValue(7)
    f.cb_ogrenci.setCurrentIndex(f.cb_ogrenci.findData(7))
    with patch("faaliyet_turleri_dialog.FaaliyetTurleriDialog", tur_penceresi(sunucu, [{"id": 3, "ad": "Y", "puan": 1}])):
        f.btn_yeni_faaliyet_turu.click()
    assert f.cb_birim.currentData() == 2 and f.sb_miktar.value() == 7 and f.cb_ogrenci.currentData() == 7


# ================================================================ birim kısayolu
def birim_penceresi(sunucu, yeni_birimler=None):
    sahte = MagicMock()

    def exec_():
        if yeni_birimler:
            sunucu.birimler.extend(yeni_birimler)
    sahte.return_value.exec.side_effect = exec_
    return sahte


def test_birim_dugmesi_yonetim_penceresini_acar(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    sahte = birim_penceresi(sunucu)
    with patch("birim_dialog.BirimYonetimDialog", sahte):
        f.btn_yeni_birim.click()
    sahte.assert_called_once_with("http://s", "t", f)
    assert sahte.return_value.exec.called


def test_yeni_eklenen_birim_otomatik_secilir_ve_tur_secimi_korunur(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    f.cb_faaliyet.setCurrentIndex(f.cb_faaliyet.findData(2))
    with patch("birim_dialog.BirimYonetimDialog", birim_penceresi(sunucu, [{"id": 3, "ad": "GUN"}])):
        f.btn_yeni_birim.click()
    assert f.cb_birim.currentData() == 3 and f.cb_birim.currentText() == "GUN" and f.cb_faaliyet.currentData() == 2
    assert f.cb_birim.count() == 4


def test_yeni_birim_eklenmeden_kapatilirsa_onceki_secim_korunur(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    f.cb_birim.setCurrentIndex(f.cb_birim.findData(1))
    with patch("birim_dialog.BirimYonetimDialog", birim_penceresi(sunucu)):
        f.btn_yeni_birim.click()
    assert f.cb_birim.currentData() == 1


def test_oturum_dusmusse_liste_yenilenirken_hata_vermez(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    with patch("birim_dialog.BirimYonetimDialog", birim_penceresi(sunucu)):
        sunucu.oturum_dustu = True
        f.btn_yeni_birim.click()                                           # çökmemeli


def test_yonetim_penceresi_sonrasi_listeler_sunucudan_yeniden_istenir(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    onceki = len(sunucu.istekler)
    with patch("birim_dialog.BirimYonetimDialog", birim_penceresi(sunucu)):
        f.btn_yeni_birim.click()
    yeni = sunucu.istekler[onceki:]
    assert yeni == [("GET", "http://s/api/faaliyet-birimleri")]            # yalnızca birimler; gereksiz istek yok


# ================================================================ mevcut öğrenci kısayolu bozulmadı
def test_ogrenci_kisayolu_formu_kapatip_ogrenciler_sayfasini_acar(qt_app, sunucu):
    class AnaPencere(QWidget):
        def __init__(self):
            super().__init__()
            self.cagrilar = []

        def ogrenciler_sayfasina_git(self, yeni_ekle=False):
            self.cagrilar.append(yeni_ekle)

    ana = AnaPencere()
    f = FaaliyetEkleDialog("http://s", "t", ana)
    atilan = []
    with patch.object(QTimer, "singleShot", side_effect=lambda ms, fn: atilan.append(fn)):
        f.btn_yeni_ogrenci.click()
    assert len(atilan) == 1 and ana.cagrilar == []                         # sayfa geçişi form kapandıktan sonra yapılır
    atilan[0]()
    assert ana.cagrilar == [True]


# ================================================================ ana pencere bağlantısı
class SahteAna:
    api_url = "http://s"
    token = "t"
    aktif_rol = "admin"

    def faaliyet_tablosunu_guncelle(self):
        pass


@pytest.mark.parametrize("izin", [True, False])
def test_yeni_faaliyet_formu_birim_iznini_ana_pencereden_alir(izin):
    sahte_form = MagicMock()
    sahte_form.return_value.exec.return_value = False
    with patch("faaliyet_dialog.FaaliyetEkleDialog", sahte_form), patch.object(main_window, "izin_var", return_value=izin) as izin_var:
        main_window.AnaPencere.yeni_faaliyet_ekrani_ac(SahteAna())
    assert sahte_form.call_args.kwargs["birim_yonetebilir"] is izin
    izin_var.assert_called_once_with("admin", "Faaliyet birimlerini yönetme")


def test_birim_izni_sunucunun_birim_yazma_iznine_baglidir():
    assert main_window.IZIN_KODLARI["Faaliyet birimlerini yönetme"] == ("FAALIYET_BIRIMI_DUZENLE",)


def test_duzenleme_formu_birim_iznini_istemez_ve_kisayol_gostermez():
    kaynak = open(main_window.__file__, encoding="utf-8").read()
    assert "FaaliyetEkleDialog(self.api_url, self.token, self, mevcut_veri=mevcut_veri)" in kaynak


# ================================================================ hizalama
def test_uc_dugme_ayni_sabit_genislikte(qt_app, sunucu):
    f = form(qt_app, birim_yonetebilir=True)
    genislikler = {f.btn_yeni_ogrenci.width() or f.btn_yeni_ogrenci.minimumWidth(), f.btn_yeni_faaliyet_turu.minimumWidth(), f.btn_yeni_birim.minimumWidth()}
    assert {b.minimumWidth() for b in (f.btn_yeni_ogrenci, f.btn_yeni_faaliyet_turu, f.btn_yeni_birim)} == {FaaliyetEkleDialog.KISAYOL_GENISLIGI}
    assert {b.maximumWidth() for b in (f.btn_yeni_ogrenci, f.btn_yeni_faaliyet_turu, f.btn_yeni_birim)} == {FaaliyetEkleDialog.KISAYOL_GENISLIGI}
    assert genislikler


def test_yetkisizde_gizli_birim_dugmesi_yerini_korur_boylece_kutular_hizali_kalir(qt_app, sunucu):
    yetkisiz = form(qt_app, birim_yonetebilir=False)
    assert yetkisiz.btn_yeni_birim.sizePolicy().retainSizeWhenHidden()
    yetkili = form(qt_app, birim_yonetebilir=True)
    assert not yetkili.btn_yeni_birim.sizePolicy().retainSizeWhenHidden()


def test_duzenleme_modunda_yer_ayrilmaz(qt_app, sunucu):
    mevcut = {"takip_id": 1, "ogrenci_adi": "Ayşe", "faaliyet_adi": "Seminer", "miktar": "2", "birim_adi": "SAAT"}
    assert not form(qt_app, mevcut_veri=mevcut).btn_yeni_birim.sizePolicy().retainSizeWhenHidden()
