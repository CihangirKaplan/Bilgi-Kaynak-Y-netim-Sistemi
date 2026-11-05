"""Cihaz Uygunluğu sayfasının ana pencereye bağlanması, izinleri ve rezervasyon formuna geçişi."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QWidget

import cihaz_rezervasyon_ekranlari as rez
import main_window as mw


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def temiz_yetkiler():
    mw._SUNUCU_YETKILERI.clear()                       # sunucu izni yok -> elle yazılmış tablo (IZIN_LISTESI) geçerli
    yield
    mw._SUNUCU_YETKILERI.clear()


def oge():
    return next(o for _, og in mw.MENU for o in og if o["ad"] == "Cihaz Uygunluğu")


# ------------------------------------------------------------------------------ menü
def test_menu_ogesi_goruntuleme_iznine_bagli_ve_islem_butonlari_ayri_izinlere_bagli():
    """Sayfa başlığındaki 'SALT OKUNUR' rozeti, kullanıcının gerçekten işlem yetkisi yoksa görünmeli."""
    o = oge()
    assert o["izin"] == "Cihaz uygunluğunu görüntüleme"
    assert [izin for _, izin in o["aksiyon"]] == ["Cihaz rezervasyonu yapma", "Arıza kayıtlarını yönetme"]
    assert "haftalık" in o["aciklama"]
    assert mw.IZIN_KODLARI["Cihaz uygunluğunu görüntüleme"] == ("CIHAZ_UYGUNLUK_GORUNTULE",)


@pytest.mark.parametrize("rol, gorur", [("psikolog", True), ("memur", True), ("mudur", True), ("asistan", True),
                                        ("admin", True), ("ogrenci", False)])
def test_hangi_rol_sayfayi_gorur(rol, gorur):
    assert mw.izin_var(rol, oge()["izin"]) is gorur


# ------------------------------------------------------------- sayfa içeriği ve izinler
class SahteEkran(QWidget):
    """Gerçek ağ isteği atmadan, kendisine verilen argümanları kaydeden Qt bileşeni."""
    verilenler = None

    def __init__(self, **kwargs):
        super().__init__()
        SahteEkran.verilenler = kwargs


def sayfa_olustur(rol):
    ana = MagicMock()
    ana.aktif_rol = rol
    ana.api_url, ana.token = "http://x", "T"
    SahteEkran.verilenler = None
    with patch.object(mw, "CihazUygunlukEkrani", SahteEkran):
        mw.AnaPencere.sayfa_modul(ana, oge())
    return ana, SahteEkran.verilenler


@pytest.mark.parametrize("rol, beklenen", [
    ("memur", dict(rezervasyon=True, ariza=True, bakim=True, kalibrasyon=True)),
    ("admin", dict(rezervasyon=True, ariza=True, bakim=True, kalibrasyon=True)),
    ("mudur", dict(rezervasyon=False, ariza=True, bakim=True, kalibrasyon=True)),       # müdür rezervasyon yapamaz
    ("asistan", dict(rezervasyon=True, ariza=False, bakim=False, kalibrasyon=False)),   # asistan yalnızca rezervasyon
    ("psikolog", dict(rezervasyon=False, ariza=False, bakim=False, kalibrasyon=False))])  # salt okur
def test_ekrana_rolun_izinleri_gecirilir(qt_app, rol, beklenen):
    ana, kw = sayfa_olustur(rol)
    assert kw["yetkiler"] == beklenen
    assert (kw["api_url"], kw["token"]) == ("http://x", "T")
    assert kw["sayfaya_git"] == ana._bildirimden_sayfaya_git and kw["rezervasyon_ac"] == ana._uygunluktan_rezervasyon_ac
    assert isinstance(ana.aktif_uygunluk_ekrani, SahteEkran)


def test_sunucudan_gelen_izinler_elle_yazilmis_tablodan_onceliklidir(qt_app):
    mw.yetkileri_ayarla("memur", ["CIHAZ_UYGUNLUK_GORUNTULE"])                       # yönetici memurun izinlerini kısmış
    _, kw = sayfa_olustur("memur")
    assert kw["yetkiler"] == dict(rezervasyon=False, ariza=False, bakim=False, kalibrasyon=False)


def test_yer_tutucu_metin_artik_gosterilmez():
    kaynak = open("main_window.py", encoding="utf-8").read()
    assert 'oge["ad"] == "Cihaz Uygunluğu"' in kaynak                                  # özel dal var, genel 'else' yer tutucusuna düşmez


# ------------------------------------------------------------------- sayfaya girince yenileme
def test_sayfaya_gecince_uygunluk_ekrani_yenilenir():
    assert mw.AnaPencere.SAYFA_YENILEME["Cihaz Uygunluğu"] == ("aktif_uygunluk_ekrani", "verileri_yukle")
    ekran = MagicMock()
    ana = MagicMock()
    ana.SAYFA_YENILEME = mw.AnaPencere.SAYFA_YENILEME
    ana.SAYFA_YENILEME_ARALIGI = mw.AnaPencere.SAYFA_YENILEME_ARALIGI
    ana.aktif_uygunluk_ekrani, ana._sayfa_son_yenileme = ekran, {}
    mw.AnaPencere._sayfayi_yenile(ana, "Cihaz Uygunluğu")
    ekran.verileri_yukle.assert_called_once()


# --------------------------------------------------------------- rezervasyona geçiş (ana pencere)
def test_takvimden_rezervasyon_formu_cihaz_gun_ve_saatle_acilir():
    ana = MagicMock()
    ana.nav_btnler = {"Cihaz Rezervasyonu": object()}
    gun = date(2026, 11, 10)
    mw.AnaPencere._uygunluktan_rezervasyon_ac(ana, 7, gun, "14:00", "15:00")
    ana._bildirimden_sayfaya_git.assert_called_once_with("Cihaz Rezervasyonu")
    ana.aktif_rezervasyon_ekrani.yeni_rezervasyon_olustur.assert_called_once_with(
        cihaz_id=7, tarih=gun, baslangic_saati="14:00", bitis_saati="15:00")


def test_rezervasyon_sayfasi_yoksa_hicbir_sey_acilmaz():
    ana = MagicMock()
    ana.nav_btnler = {}                                                                # kullanıcının rezervasyon izni yok
    mw.AnaPencere._uygunluktan_rezervasyon_ac(ana, 7, date(2026, 11, 10), "14:00", "15:00")
    ana._bildirimden_sayfaya_git.assert_not_called()
    ana.aktif_rezervasyon_ekrani.yeni_rezervasyon_olustur.assert_not_called()


# -------------------------------------------------------------- rezervasyon formu ön değerleri
def cevap(veri):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = 200
    r.json.return_value = veri
    return r


def form_ac(**kw):
    cihazlar = [{"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "durum": "Kullanima_Hazir"},
                {"cihaz_id": 2, "envanter_kodu": "E-2", "cihaz_adi": "Işık", "durum": "Kullanima_Hazir"}]
    odalar = [{"oda_id": 5, "oda_adi": "Oda A", "aktif_mi": True}]
    istek = lambda yontem, url, **k: cevap(cihazlar if url.endswith("/api/cihazlar") else odalar)
    with patch.object(rez, "oturum_kontrollu_istek", side_effect=istek):
        return rez.YeniRezervasyonFormu("http://x", "T", **kw)


def test_form_on_degerleri_cihaz_tarih_ve_saati_secer(qt_app):
    gun = date.today() + timedelta(days=3)
    f = form_ac(cihaz_id=2, tarih=gun, baslangic_saati="14:00", bitis_saati="15:30")
    assert f.cmb_cihaz.currentData() == 2
    assert f.dt_baslangic_tarih.date() == QDate(gun.year, gun.month, gun.day) == f.dt_bitis_tarih.date()
    assert (f.cmb_baslangic_saat.currentText(), f.cmb_bitis_saat.currentText()) == ("14:00", "15:30")
    f.close()


def test_form_on_deger_verilmezse_eski_varsayilanlar_korunur(qt_app):
    f = form_ac()
    varsayilan_tarih, bas, bit = rez.varsayilan_rezervasyon_zamanlari()
    assert f.cmb_cihaz.currentData() == 1 and f.dt_baslangic_tarih.date() == varsayilan_tarih
    assert (f.cmb_baslangic_saat.currentText(), f.cmb_bitis_saat.currentText()) == (bas, bit)
    f.close()


def test_form_olmayan_cihaz_ve_gecersiz_saati_yok_sayar(qt_app):
    f = form_ac(cihaz_id=99, baslangic_saati="25:61", bitis_saati="")
    _, bas, bit = rez.varsayilan_rezervasyon_zamanlari()
    assert f.cmb_cihaz.currentData() == 1                                              # listede yok: ilk cihaz kalır
    assert (f.cmb_baslangic_saat.currentText(), f.cmb_bitis_saat.currentText()) == (bas, bit)
    f.close()


def test_yonetim_ekrani_on_degerleri_forma_aktarir(qt_app):
    with patch.object(rez, "oturum_kontrollu_istek", return_value=cevap([])):
        ekran = rez.RezervasyonYonetimEkrani("http://x", "T")
    with patch.object(rez, "YeniRezervasyonFormu") as form:
        form.return_value.exec.return_value = 0
        ekran.yeni_rezervasyon_olustur(cihaz_id=3, tarih=date(2026, 11, 10), baslangic_saati="10:00", bitis_saati="11:00")
        form.assert_called_with("http://x", "T", cihaz_id=3, tarih=date(2026, 11, 10),
                                baslangic_saati="10:00", bitis_saati="11:00")
        form.reset_mock()
        ekran.yeni_rezervasyon_olustur()                                               # eski kullanım değişmedi
        form.assert_called_with("http://x", "T")
