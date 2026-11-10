"""PR 3/3: kopyalanabilir geçici parola penceresi (pano otomatik temizleme) ve yeni şifre ekranında canlı kural geri bildirimi."""
import base64
import json
import time
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import gecici_parola_dialog as gpd
from gecici_parola_dialog import GeciciParolaDialog
from parola_kurallari import guc_hesapla, kural_durumlari, tum_kurallar_saglandi_mi
from sifre_degistir_ekrani import SifreDegistirEkrani

APP = QApplication.instance() or QApplication([])


# ---------------- kurallar (saf mantık) ----------------
def test_kurallar_bos_hicbiri_saglanmaz():
    assert not any(s for _, s in kural_durumlari("", "", "eski"))


def test_kisa_sifre_reddedilir_8_karakter_kabul():
    assert not tum_kurallar_saglandi_mi("Abc123!", "Abc123!", "eski")
    assert tum_kurallar_saglandi_mi("Abc123!x", "Abc123!x", "eski")


def test_eskiyle_ayni_ve_tekrar_uyusmazligi_reddedilir():
    assert not tum_kurallar_saglandi_mi("Abc123!x", "Abc123!x", "Abc123!x")
    assert not tum_kurallar_saglandi_mi("Abc123!x", "Abc123!y", "eski")


def test_72_bayt_siniri():
    assert tum_kurallar_saglandi_mi("a" * 72, "a" * 72, "eski")
    assert not tum_kurallar_saglandi_mi("a" * 73, "a" * 73, "eski")
    assert not tum_kurallar_saglandi_mi("ş" * 37, "ş" * 37, "eski")      # 37 karakter = 74 bayt
    assert tum_kurallar_saglandi_mi("ş" * 36, "ş" * 36, "eski")          # 72 bayt


def test_guc_dereceleri():
    assert guc_hesapla("")[0] == 0
    assert guc_hesapla("abc")[1] == "Zayıf"
    assert guc_hesapla("abcdefgh")[0] == 1
    assert guc_hesapla("Abcdefgh1234")[0] == 3
    assert guc_hesapla("Abcdefg1")[0] == 2


# ---------------- geçici parola penceresi ----------------
@pytest.fixture(autouse=True)
def pano_temizle():
    APP.clipboard().clear()
    yield
    APP.clipboard().clear()


def test_pencere_parolayi_gosterir_ve_salt_okunurdur():
    d = GeciciParolaDialog("ayse", "GeciciPw-123")
    assert d.parola_kutusu.text() == "GeciciPw-123"
    assert d.parola_kutusu.isReadOnly()
    assert "ayse" in d.lbl_alt.text()
    assert "tekrar gösterilemez" in d.lbl_not.text()
    assert APP.clipboard().text() == ""                               # kendiliğinden kopyalamaz


def test_kopyala_butonu_panoya_yazar_ve_bilgi_verir():
    d = GeciciParolaDialog("ayse", "GeciciPw-123", pano_saniye=60)
    d.show()
    QTest.mouseClick(d.btn_kopyala, Qt.LeftButton)
    assert APP.clipboard().text() == "GeciciPw-123"
    assert d.kopyalandi and "60 saniye" in d.lbl_durum.text()
    d.close()


def test_pano_sure_dolunca_temizlenir_pencere_kapansa_da():
    d = GeciciParolaDialog("ayse", "GeciciPw-123", pano_saniye=0.05)
    d.kopyala()
    d.close()
    d.deleteLater()
    QTest.qWait(250)
    assert APP.clipboard().text() == ""


def test_pano_baska_metinle_degistiyse_dokunulmaz():
    d = GeciciParolaDialog("ayse", "GeciciPw-123", pano_saniye=0.05)
    d.kopyala()
    APP.clipboard().setText("kullanicinin kendi kopyaladigi metin")
    QTest.qWait(250)
    assert APP.clipboard().text() == "kullanicinin kendi kopyaladigi metin"


def test_yeni_kopyalama_eski_zamanlayiciyi_iptal_eder():
    gpd.panoya_kopyala_ve_zamanla("ayni-parola", 0.05)             # kısa süreli ilk kopyalama
    gpd.panoya_kopyala_ve_zamanla("ayni-parola", 5)                # aynı parola yeniden kopyalandı, süre yenilendi
    QTest.qWait(250)
    assert APP.clipboard().text() == "ayni-parola"                 # ilkinin kısa zamanlayıcısı silmemeli
    gpd.panoya_kopyala_ve_zamanla("x", 0.01)
    QTest.qWait(100)


def test_varsayilan_pano_suresi_60_saniye():
    assert gpd.PANO_TEMIZLEME_SANIYE == 60


# ---------------- yeni şifre ekranı ----------------
def jwt(exp):
    def b(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{b({'alg': 'none'})}.{b({'exp': exp})}.x"


@pytest.fixture
def ekran():
    e = SifreDegistirEkrani(jwt(int(time.time()) + 3600))
    e.show()
    yield e
    e._sifre_basariyla_degisti = True
    e.close()


def yaz(e, eski="", yeni="", tekrar=""):
    e.eski_sifre.setText(eski)
    e.yeni_sifre.setText(yeni)
    e.yeni_sifre_tekrar.setText(tekrar)


def test_baslangicta_dugme_kapali_ve_kurallar_gorunur(ekran):
    assert not ekran.kaydet_btn.isEnabled()
    assert "En az 8 karakter" in ekran.kural_lbl.text()


def test_kurallar_saglaninca_dugme_acilir(ekran):
    yaz(ekran, "gecici", "Abc123!x", "Abc123!x")
    assert ekran.kaydet_btn.isEnabled()
    assert ekran.kural_lbl.text().count("✔") == 4


def test_tek_kural_eksikse_dugme_kapali(ekran):
    yaz(ekran, "gecici", "Abc123!", "Abc123!")                      # 7 karakter
    assert not ekran.kaydet_btn.isEnabled()
    yaz(ekran, "gecici", "Abc123!x", "Abc123!y")                    # uyuşmuyor
    assert not ekran.kaydet_btn.isEnabled()
    yaz(ekran, "", "Abc123!x", "Abc123!x")                          # mevcut şifre boş
    assert not ekran.kaydet_btn.isEnabled()
    yaz(ekran, "Abc123!x", "Abc123!x", "Abc123!x")                  # eskiyle aynı
    assert not ekran.kaydet_btn.isEnabled()


def test_guc_gostergesi_yazdikca_degisir(ekran):
    yaz(ekran, "g", "abc")
    assert "Zayıf" in ekran.guc_lbl.text()
    ekran.yeni_sifre.setText("Abcdefgh1234")
    assert "Güçlü" in ekran.guc_lbl.text()
    ekran.yeni_sifre.setText("")
    assert ekran.guc_lbl.text() == ""


def test_basarisiz_istekten_sonra_dugme_kural_durumuna_gore_kalir(ekran):
    yaz(ekran, "gecici", "Abc123!x", "Abc123!x")
    yanit = MagicMock(status_code=401)
    yanit.json.return_value = {"detail": "Eski şifre hatalı."}
    with patch("sifre_degistir_ekrani.oturum_kontrollu_istek", return_value=yanit), \
            patch("sifre_degistir_ekrani.oturum_hatasi_mi", return_value=False):
        ekran.sifre_degistir()
    assert ekran.hata_lbl.text() == "Eski şifre hatalı."
    assert ekran.kaydet_btn.isEnabled()                              # kurallar sağlanıyor, tekrar denenebilir


def test_oturum_bitince_kurallar_saglansa_da_dugme_kapali_kalir(ekran):
    yaz(ekran, "gecici", "Abc123!x", "Abc123!x")
    ekran._oturum_kapatiliyor = True
    ekran._kurallari_guncelle()
    assert not ekran.kaydet_btn.isEnabled()
    ekran._oturum_kapatiliyor = False


def test_gecerli_sifre_sunucuya_gonderilir(ekran):
    yaz(ekran, "gecici", "Abc123!x", "Abc123!x")
    yanit = MagicMock(status_code=200)
    class Sayac:
        sayi = 0

        def artir(self):
            self.sayi += 1

    sayac = Sayac()
    ekran.sifre_degistirildi.connect(sayac.artir)
    with patch("sifre_degistir_ekrani.oturum_kontrollu_istek", return_value=yanit) as api, \
            patch("sifre_degistir_ekrani.oturum_hatasi_mi", return_value=False):
        ekran.sifre_degistir()
    assert api.call_args.kwargs["json"] == {"eski_parola": "gecici", "yeni_parola": "Abc123!x", "yeni_parola_tekrar": "Abc123!x"}
    assert sayac.sayi == 1
