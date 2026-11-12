"""Bakım/kalibrasyon formlarındaki 'Bağlı plan' seçimi. Gerçek API ve açılır pencere kullanılmaz."""
import turkce_mesaj_kutusu as tmk
import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QMessageBox

import cihaz_bakim_ekranlari as bakim_modulu
import cihaz_kalibrasyon_ekranlari as kalibrasyon_modulu
import plan_secimi as modul
from plan_secimi import PLAN_YOK, kalibrasyon_plani_mi


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(durum, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = veri if veri is not None else []
    return r


def plan(plan_id, tur, periyot=90, uyari=7, cihaz_id=1):
    return {"plan_id": plan_id, "cihaz_id": cihaz_id, "gorev_turu": tur, "periyot_gun": periyot,
            "uyari_suresi_gun": uyari, "sonraki_gorev_tarihi": "2027-01-01", "aktif_mi": True}


CIHAZLAR = [{"cihaz_id": 1, "envanter_kodu": "C-1", "cihaz_adi": "EEG"},
            {"cihaz_id": 2, "envanter_kodu": "C-2", "cihaz_adi": "Tens"}]


def sunucu_yaniti(planlar_by_cihaz):
    """Çağrılan adrese göre cihaz listesi ya da o cihazın planlarını döndürür."""
    def istek(yontem, adres, **kw):
        if adres.endswith("/api/cihazlar"):
            return cevap(200, CIHAZLAR)
        if "/api/bakim-planlari" in adres:
            cihaz_id = int(adres.split("cihaz_id=")[1].split("&")[0])
            return cevap(200, planlar_by_cihaz.get(cihaz_id, []))
        raise AssertionError(adres)
    return istek


def bakim_formu(qt_app, planlar):
    istek = sunucu_yaniti(planlar)
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", side_effect=istek), \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        return bakim_modulu.YeniBakimFormu("http://s", "T")


def kalibrasyon_formu(qt_app, planlar):
    istek = sunucu_yaniti(planlar)
    with patch.object(kalibrasyon_modulu, "oturum_kontrollu_istek", side_effect=istek), \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        return kalibrasyon_modulu.YeniKalibrasyonFormu("http://s", "T")


def secenekler(form):
    return [form.plan_secimi.cmb_plan.itemText(i) for i in range(form.plan_secimi.cmb_plan.count())]


# ------------------------------------------------------------------------ tür kuralı
def test_kalibrasyon_plani_turu_sunucuyla_ayni_kuralla_ayirt_edilir():
    assert kalibrasyon_plani_mi("Kalibrasyon") and kalibrasyon_plani_mi(" kalibrasyon yıllık ")
    assert not kalibrasyon_plani_mi("Genel bakım") and not kalibrasyon_plani_mi(None)


# ------------------------------------------------------------------------- bakım formu
def test_bakim_formu_yalniz_bakim_planlarini_listeler(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım"), plan(2, "Kalibrasyon", 365), plan(3, "Filtre", 60)]})
    assert secenekler(f) == [PLAN_YOK, "Genel bakım — her 90 günde bir", "Filtre — her 60 günde bir"]
    assert f.plan_secimi.plan_id() is None


def test_tek_plan_varsa_otomatik_secilir_ve_tarih_ile_bildirim_plandan_gelir(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım", periyot=90, uyari=15)]})
    assert f.plan_secimi.plan_id() == 1
    assert f.dt_sonraki_bakim.date() == f.dt_bitis.date().addDays(90)
    assert f.tekrar.uyari_suresi() == 15
    assert "plana göre" in f.plan_secimi.lbl_ipucu.text()


def test_bitis_tarihi_degisince_sonraki_tarih_plana_gore_yeniden_hesaplanir(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım", periyot=30)]})
    f.dt_bitis.setDate(QDate(2026, 12, 1))
    assert f.dt_sonraki_bakim.date() == QDate(2026, 12, 31)


def test_birden_cok_plan_varsa_kullanici_secene_kadar_plan_secilmez(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım"), plan(2, "Filtre", 60, 5)]})
    assert f.plan_secimi.plan_id() is None
    f.plan_secimi.cmb_plan.setCurrentIndex(2)
    assert f.plan_secimi.plan_id() == 2 and f.tekrar.uyari_suresi() == 5
    assert f.dt_sonraki_bakim.date() == f.dt_bitis.date().addDays(60)


def test_plan_yok_secilince_tarihi_kullanici_yonetir(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım")]})
    f.plan_secimi.cmb_plan.setCurrentIndex(0)
    assert f.plan_secimi.plan_id() is None


def test_cihaz_degisince_o_cihazin_planlari_gelir(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım")], 2: [plan(5, "Filtre", 60, cihaz_id=2)]})
    istek = sunucu_yaniti({1: [plan(1, "Genel bakım")], 2: [plan(5, "Filtre", 60, cihaz_id=2)]})
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        f.cmb_cihaz.setCurrentIndex(1)
    assert secenekler(f) == [PLAN_YOK, "Filtre — her 60 günde bir"] and f.plan_secimi.plan_id() == 5


def test_plani_olmayan_cihazda_yonlendirici_ipucu_gorunur(qt_app):
    f = bakim_formu(qt_app, {})
    assert secenekler(f) == [PLAN_YOK] and "Bakım Planları" in f.plan_secimi.lbl_ipucu.text()


def test_plan_listesi_alinamazsa_form_plansiz_calismaya_devam_eder(qt_app):
    def istek(yontem, adres, **kw):
        if adres.endswith("/api/cihazlar"):
            return cevap(200, CIHAZLAR)
        raise OSError("sunucu kapalı")
    with patch.object(bakim_modulu, "oturum_kontrollu_istek", side_effect=istek), \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=istek):
        f = bakim_modulu.YeniBakimFormu("http://s", "T")
    assert secenekler(f) == [PLAN_YOK] and f.plan_secimi.plan_id() is None


def gonderilen(modul_adi, form, **kayit_alanlari):
    """Formu doldurup Kaydet'e basar; sunucuya giden JSON gövdesini döndürür."""
    gonder = MagicMock(return_value=cevap(201, {}))
    with patch.object(modul_adi, "cakisma_cozumlu_istek", gonder), patch.object(tmk, "bilgi"), \
         patch.object(tmk, "uyari"):
        form.kaydet()
    return gonder.call_args.args[3]


def test_bakim_kaydi_secili_plan_kimligini_sunucuya_gonderir(qt_app):
    f = bakim_formu(qt_app, {1: [plan(1, "Genel bakım", periyot=90)]})
    f.txt_kisi.setText("Teknisyen")
    f.txt_islem.setPlainText("Kontrol")
    veri = gonderilen(bakim_modulu, f)
    assert veri["plan_id"] == 1 and veri["sonraki_bakim_tarihi"] == f.dt_bitis.date().addDays(90).toString("yyyy-MM-dd")


def test_plansiz_bakim_kaydi_plan_kimligi_gondermez(qt_app):
    f = bakim_formu(qt_app, {})
    f.txt_kisi.setText("Teknisyen")
    f.txt_islem.setPlainText("Kontrol")
    assert "plan_id" not in gonderilen(bakim_modulu, f)


# --------------------------------------------------------------------- kalibrasyon formu
def test_kalibrasyon_formu_yalniz_kalibrasyon_planlarini_listeler_ve_gonderir(qt_app):
    f = kalibrasyon_formu(qt_app, {1: [plan(1, "Genel bakım"), plan(2, "Kalibrasyon", 365, 30)]})
    assert secenekler(f) == [PLAN_YOK, "Kalibrasyon — her 365 günde bir"]
    assert f.plan_secimi.plan_id() == 2 and f.dt_gecerlilik.date() == f.dt_bitis.date().addDays(365)
    f.txt_kurum.setText("TSE")
    f.txt_sertifika.setText("S-1")
    veri = gonderilen(kalibrasyon_modulu, f)
    assert veri["plan_id"] == 2 and veri["gecerlilik_tarihi"] == f.dt_gecerlilik.date().toString("yyyy-MM-dd")


def test_plansiz_kalibrasyon_kaydi_plan_kimligi_gondermez(qt_app):
    f = kalibrasyon_formu(qt_app, {})
    f.txt_kurum.setText("TSE")
    f.txt_sertifika.setText("S-1")
    assert "plan_id" not in gonderilen(kalibrasyon_modulu, f)


# ---------------------------------------------------------------- ortak alan: uyarı ayarla
def test_uyari_ayarla_listede_olmayan_degeri_ekler(qt_app):
    f = bakim_formu(qt_app, {})
    f.tekrar.uyari_ayarla(21)
    assert f.tekrar.uyari_suresi() == 21
    f.tekrar.uyari_ayarla(7)
    assert f.tekrar.uyari_suresi() == 7
