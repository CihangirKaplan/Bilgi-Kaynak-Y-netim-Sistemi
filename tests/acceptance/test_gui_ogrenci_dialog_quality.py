"""
TKYS QA-001 - PySide6 GUI testleri.
Gercek API veya PostgreSQL kullanilmaz.
"""

import os
from unittest.mock import patch

import pytest
from requests import Response
from PySide6.QtWidgets import QApplication, QDialog

from client.ogrenci_dialog import OgrenciEkleDialog


@pytest.fixture(scope="module")
def qt_app():
    uygulama = QApplication.instance()
    if uygulama is None:
        uygulama = QApplication([])
    return uygulama


@pytest.fixture
def dialog(qt_app):
    pencere = OgrenciEkleDialog(
        "http://testserver",
        "QA001_TEST_TOKEN",
    )
    yield pencere
    pencere.close()


def test_gui_zorunlu_alanlar_bos(dialog):
    with (
        patch('client.ogrenci_dialog.oturum_kontrollu_istek') as post,
        patch('client.ogrenci_dialog.QMessageBox.warning') as uyari,
    ):
        dialog.kaydet_tiklandi()

    post.assert_not_called()
    uyari.assert_called_once()


def test_gui_ogrenci_numarasi_harf_iceremez(dialog):
    dialog.le_ad_soyad.setText("QA Test")
    dialog.le_ogrenci_no.setText("123ABC")

    with (
        patch('client.ogrenci_dialog.oturum_kontrollu_istek') as post,
        patch('client.ogrenci_dialog.QMessageBox.warning') as uyari,
    ):
        dialog.kaydet_tiklandi()

    post.assert_not_called()
    uyari.assert_called_once()


def test_gui_gecerli_ogrenci_kaydi(dialog):
    dialog.le_ad_soyad.setText("QA Test")
    dialog.le_ogrenci_no.setText("20240000001")
    dialog.le_telefon.setText("05551234567")
    dialog.cb_tur.setCurrentIndex(0)

    with (
        patch('client.ogrenci_dialog.oturum_kontrollu_istek') as post,
        patch('client.ogrenci_dialog.basari_bildirimi') as bilgi,
    ):
        post.return_value = Response()
        post.return_value.status_code = 200

        dialog.kaydet_tiklandi()

    post.assert_called_once()

    args, kwargs = post.call_args

    assert args[0] == "POST"
    assert args[1] == "http://testserver/api/ogrenci-ekle"
    assert kwargs["json"]["ogrenci_numarasi"] == "20240000001"
    assert kwargs["json"]["tur"] == "GONULLU"

    assert kwargs["headers"]["Authorization"] == (
        "Bearer QA001_TEST_TOKEN"
    )

    bilgi.assert_called_once()
    assert dialog.result() == QDialog.Accepted


def test_gui_dialog_yalnizca_gonullu_ve_asistan_sunar(dialog):
    turler = [dialog.cb_tur.itemData(i) for i in range(dialog.cb_tur.count())]
    assert turler == ["GONULLU", "ASISTAN"]       # Danışma Masası öğrencisi hesap gerektirir, buradan eklenmez


@pytest.mark.parametrize("indeks,tur", [(0, "GONULLU"), (1, "ASISTAN")])
def test_gui_secilen_tur_ve_bolum_sinif_sunucuya_gider(dialog, indeks, tur):
    dialog.le_ad_soyad.setText("QA Test")
    dialog.le_ogrenci_no.setText("20240000003")
    dialog.cb_tur.setCurrentIndex(indeks)
    dialog.le_bolum.setText("Psikoloji")
    dialog.le_sinif.setText("3")
    with (
        patch('client.ogrenci_dialog.oturum_kontrollu_istek') as post,
        patch('client.ogrenci_dialog.QMessageBox.information'),
    ):
        post.return_value = Response()
        post.return_value.status_code = 200
        dialog.kaydet_tiklandi()
    gonderilen = post.call_args.kwargs["json"]
    assert gonderilen["tur"] == tur
    assert gonderilen["bolum"] == "Psikoloji" and gonderilen["sinif"] == "3"


def test_gui_dialog_danisma_masasi_icin_aciklama_gosterir_ve_dugme_yetkiye_bagli(qt_app):
    from client.ogrenci_dialog import OgrenciEkleDialog

    yetkisiz = OgrenciEkleDialog("http://testserver", "T")
    assert "Kullanıcı & Personel" in yetkisiz.lbl_bilgi.text() and "Danışma Öğrencisi" in yetkisiz.lbl_bilgi.text()
    assert yetkisiz.btn_kullanici_sayfasi.isHidden()           # sayfaya yetkisi yoksa düğme yok
    yetkisiz.close()

    yetkili = OgrenciEkleDialog("http://testserver", "T", kullanici_sayfasi_acilabilir=True)
    assert not yetkili.btn_kullanici_sayfasi.isHidden()
    # Qt düğme metninde tek & kısayol işaretidir (ekranda yok olur); && yazılırsa ekranda "&" görünür.
    assert yetkili.btn_kullanici_sayfasi.text().endswith("Kullanıcı && Personel sayfasına git")
    assert yetkili.sayfa_istendi is False
    yetkili.btn_kullanici_sayfasi.click()                       # pencereyi kapatır ve sayfa isteğini işaretler
    assert yetkili.sayfa_istendi is True and yetkili.result() == QDialog.Rejected
    yetkili.close()


def test_gui_bolum_ve_sinif_alanlari_veritabani_sinirlarina_uyar(dialog):
    assert dialog.le_bolum.maxLength() == 100     # ogrenciler.bolum VARCHAR(100)
    assert dialog.le_sinif.maxLength() == 20      # ogrenciler.sinif VARCHAR(20)


def test_gui_ogrenci_ekrani_butona_basilinca_kullanici_sayfasini_acar(qt_app):
    """Dialogda 'Kullanıcı & Personel sayfasına git' seçilirse ekran ana pencereden o sayfayı açtırır."""
    from unittest.mock import MagicMock
    import client.ogrenci_yonetim_ekrani as ekran

    for sayfa_istendi, kaydedildi, beklenen_sayfa, beklenen_yenile in (
        (True, 0, ["Kullanıcı & Personel"], 0),     # butona basıldı: sayfa açılır, liste yenilenmez
        (False, 0, [], 0),                           # vazgeçildi: hiçbir şey olmaz
        (False, 1, [], 1),                           # öğrenci kaydedildi: liste yenilenir
    ):
        sahte_dialog = MagicMock()
        sahte_dialog.exec.return_value = kaydedildi
        sahte_dialog.sayfa_istendi = sayfa_istendi
        acilan = []
        self_ = MagicMock()
        self_.api_url, self_.token = "http://x", "T"
        self_._sayfaya_git = acilan.append
        self_._kullanici_sayfasi_izinli = True
        with patch.object(ekran, "OgrenciEkleDialog", return_value=sahte_dialog) as dialog_sinifi:
            ekran.OgrenciYonetimEkrani.yeni_ogrenci_ekle(self_)
        assert dialog_sinifi.call_args.kwargs["kullanici_sayfasi_acilabilir"] is True
        assert acilan == beklenen_sayfa
        assert self_.yenile.call_count == beklenen_yenile


def test_gui_ogrenci_ekrani_yetkisiz_kullaniciya_sayfa_dugmesi_sunmaz(qt_app):
    from unittest.mock import MagicMock
    import client.ogrenci_yonetim_ekrani as ekran

    self_ = MagicMock()
    self_._sayfaya_git = lambda sayfa: None
    self_._kullanici_sayfasi_izinli = False
    with patch.object(ekran, "OgrenciEkleDialog", return_value=MagicMock(exec=MagicMock(return_value=0), sayfa_istendi=False)) as sinif:
        ekran.OgrenciYonetimEkrani.yeni_ogrenci_ekle(self_)
    assert sinif.call_args.kwargs["kullanici_sayfasi_acilabilir"] is False


def test_gui_ana_pencere_ogrenci_ekranina_sayfa_acmayi_ve_yetkiyi_verir():
    import inspect
    import client.main_window as mw

    kaynak = inspect.getsource(mw.AnaPencere)
    parca = kaynak[kaynak.index("OgrenciYonetimEkrani("):][:400]
    assert "sayfaya_git=self._bildirimden_sayfaya_git" in parca
    assert 'kullanici_sayfasi_izinli=self._sayfa_izinli_mi("Kullanıcı & Personel")' in parca


@pytest.mark.parametrize(
    "gecersiz_rol",
    ["tanimsiz", "", None, 123],
)
def test_gui_gecersiz_rol_reddedilir(qt_app, gecersiz_rol):
    from client.main_window import AnaPencere

    with pytest.raises(ValueError, match="Geçersiz kullanıcı rolü"):
        AnaPencere(aktif_rol=gecersiz_rol)


def test_gui_rol_belirtilmeden_acilamaz(qt_app):
    from client.main_window import AnaPencere

    with pytest.raises(ValueError, match="Geçersiz kullanıcı rolü"):
        AnaPencere()


def test_gui_login_beklenmeyen_hata_ayrintisi_gizlenir():
    from unittest.mock import MagicMock, patch
    import client.login_ekrani as modul

    ekran_sinifi = next(
        sinif
        for sinif in vars(modul).values()
        if isinstance(sinif, type)
        and sinif.__module__ == modul.__name__
        and "giris_yap" in vars(sinif)
    )

    ekran = MagicMock()
    ekran.kalan = 0
    ekran.kullanici_input.text.return_value = "qa_test"
    ekran.sifre_input.text.return_value = "test_parolasi"

    with patch(
        'client.login_ekrani.requests.post',
        side_effect=RuntimeError("QA001_GIZLI_TEKNIK_AYRINTI")
    ):
        ekran_sinifi.giris_yap(ekran)

    ekran.hata_goster.assert_called_once()
    mesaj = ekran.hata_goster.call_args.args[0]

    assert "QA001_GIZLI_TEKNIK_AYRINTI" not in mesaj
    assert "Giriş işlemi tamamlanamadı" in mesaj


def test_gui_login_zaman_asimi_mesaji():
    from unittest.mock import MagicMock, patch
    import requests
    import client.login_ekrani as modul

    ekran_sinifi = next(
        sinif
        for sinif in vars(modul).values()
        if isinstance(sinif, type)
        and sinif.__module__ == modul.__name__
        and "giris_yap" in vars(sinif)
    )

    ekran = MagicMock()
    ekran.kalan = 0
    ekran.kullanici_input.text.return_value = "qa_test"
    ekran.sifre_input.text.return_value = "test_parolasi"

    with patch(
        'client.login_ekrani.requests.post',
        side_effect=requests.exceptions.Timeout()
    ):
        ekran_sinifi.giris_yap(ekran)

    ekran.hata_goster.assert_called_once_with(
        "Sunucu yanıt vermedi. Lütfen tekrar deneyin."
    )
