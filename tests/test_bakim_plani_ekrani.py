"""Bakım/kalibrasyon planları ekranı ve formu: görünüm verisi, form davranışı, kaydetme, silme, menü kaydı.

Gerçek API kullanılmaz; yalnızca kendi pencerelerinin olayları işlenir (genel `processEvents` yok).
"""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import bakim_plani_ekranlari as modul
from bakim_plani_ekranlari import (
    BakimPlanlariEkrani, PlanFormu, hata_metni, kalan_gun_metni, periyot_metni,
)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(durum, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = veri if veri is not None else {}
    return r


def plan(**ek):
    p = {"plan_id": 1, "cihaz_id": 1, "envanter_kodu": "CHZ-001", "cihaz_adi": "EEG Cihazı",
         "gorev_turu": "Yıllık bakım", "periyot_gun": 365, "uyari_suresi_gun": 30,
         "sonraki_gorev_tarihi": "2026-11-20", "kalan_gun": 16, "aktif_mi": True, "durum": "Yaklaşıyor"}
    p.update(ek)
    return p


PLANLAR = [
    plan(),
    plan(plan_id=2, cihaz_id=2, envanter_kodu="CHZ-002", cihaz_adi="Biyofeedback", gorev_turu="Kalibrasyon",
         periyot_gun=180, uyari_suresi_gun=14, sonraki_gorev_tarihi="2026-10-30", kalan_gun=-5, durum="Gecikmiş"),
    plan(plan_id=3, cihaz_id=3, envanter_kodu="CHZ-003", cihaz_adi="Nörofeedback", gorev_turu="Periyodik bakım",
         periyot_gun=90, uyari_suresi_gun=7, sonraki_gorev_tarihi="2027-02-01", kalan_gun=89, durum="Planlı"),
]
CIHAZLAR = [{"cihaz_id": 1, "envanter_kodu": "CHZ-001", "cihaz_adi": "EEG Cihazı"},
            {"cihaz_id": 2, "envanter_kodu": "CHZ-002", "cihaz_adi": "Biyofeedback"}]


def sunucu(planlar=None, cihazlar=None):
    def istek(yontem, url, **kwargs):
        if "bakim-planlari" in url:
            return cevap(200, PLANLAR if planlar is None else planlar)
        return cevap(200, CIHAZLAR if cihazlar is None else cihazlar)
    return istek


# ------------------------------------------------------------------------ yardımcılar
def test_hata_metni_cesitli_yanit_bicimleri():
    assert hata_metni(cevap(409, {"detail": "Aynı plan var."}), "x") == "Aynı plan var."
    pydantic = {"detail": [{"msg": "Value error, Uyarı süresi periyottan uzun olamaz."}]}
    assert hata_metni(cevap(422, pydantic), "x") == "Uyarı süresi periyottan uzun olamaz."
    assert hata_metni(cevap(500, {}), "varsayılan") == "varsayılan"
    bozuk = MagicMock()
    bozuk.json.side_effect = ValueError("json değil")
    assert hata_metni(bozuk, "varsayılan") == "varsayılan"


@pytest.mark.parametrize("kalan, durum, beklenen", [
    (-3, "Gecikmiş", "3 gün gecikti"), (0, "Yaklaşıyor", "bugün"), (16, "Yaklaşıyor", "16 gün kaldı"),
    (5, "Pasif", "Pasif"),
])
def test_kalan_gun_metni(kalan, durum, beklenen):
    assert kalan_gun_metni(kalan, durum) == beklenen


def test_periyot_metni_hazir_ve_ozel():
    assert periyot_metni(365) == "Yıllık" and periyot_metni(30) == "Aylık" and periyot_metni(45) == "45 günde bir"


# ---------------------------------------------------------------------------- form
@pytest.fixture
def yeni_form(qt_app):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu()):
        f = PlanFormu("http://x", "T")
    yield f
    f.close()
    f.deleteLater()


def test_yeni_form_varsayilanlari_ve_cihaz_listesi(yeni_form):
    f = yeni_form
    assert f.cmb_cihaz.count() == 3 and f.cmb_cihaz.itemData(1) == 1       # "— seçiniz —" + 2 cihaz
    assert f.spin_periyot.value() == 365 and f.cmb_hazir.currentText().startswith("Yıllık")
    assert f.spin_uyari.value() == 7 and not f.chk_aktif.isVisibleTo(f)
    beklenen = QDate.currentDate().addDays(365)
    assert f.dt_sonraki.date() == beklenen
    assert "her 365 günde bir" in f.lbl_ozet.text() and "7 gün kala" in f.lbl_ozet.text()


def test_hazir_aralik_secilince_gun_sayisi_ve_tarih_guncellenir(yeni_form):
    f = yeni_form
    f.hazir_secildi(2)                                                   # 3 aylık (90)
    assert f.spin_periyot.value() == 90
    assert f.dt_sonraki.date() == QDate.currentDate().addDays(90)
    assert "her 90 günde bir" in f.lbl_ozet.text()


def test_gun_sayisi_elle_degisince_hazir_secim_ozele_doner_ve_hazira_geri_doner(yeni_form):
    f = yeni_form
    f.spin_periyot.setValue(45)
    assert f.cmb_hazir.currentText() == modul.OZEL_PERIYOT
    f.spin_periyot.setValue(30)
    assert f.cmb_hazir.currentText().startswith("Aylık")


def test_uyari_suresi_periyottan_uzun_secilemez(yeni_form):
    f = yeni_form
    f.spin_periyot.setValue(10)
    f.spin_uyari.setValue(200)
    assert f.spin_uyari.value() == 10                                    # üst sınır periyoda indi


def test_elle_degistirilen_tarih_periyot_degisince_ezilmez(yeni_form):
    f = yeni_form
    secilen = QDate.currentDate().addDays(12)
    f.dt_sonraki.setDate(secilen)
    f.tarih_elle_degistirildi(secilen)
    f.hazir_secildi(1)
    assert f.dt_sonraki.date() == secilen


def test_ozet_uyari_sifirsa_uyari_verilmez_der(yeni_form):
    yeni_form.spin_uyari.setValue(0)
    assert "uyarı verilmez" in yeni_form.lbl_ozet.text()


def test_dogrulama_mesajlari(yeni_form):
    f = yeni_form
    veri = {"cihaz_id": None, "gorev_turu": "Bakım", "periyot_gun": 30, "uyari_suresi_gun": 7}
    assert "cihaz" in f.dogrula(veri).lower()
    assert "en az 2" in f.dogrula({**veri, "cihaz_id": 1, "gorev_turu": "a"})
    assert "uzun olamaz" in f.dogrula({**veri, "cihaz_id": 1, "uyari_suresi_gun": 31})
    assert f.dogrula({**veri, "cihaz_id": 1}) is None


def doldur(f, cihaz_indeksi=1, tur="Kalibrasyon"):
    f.cmb_cihaz.setCurrentIndex(cihaz_indeksi)
    f.cmb_tur.setEditText(tur)


def test_yeni_plan_post_gonderir_ve_kabul_edilirse_kapanir(yeni_form):
    f = yeni_form
    doldur(f)
    f.hazir_secildi(3)
    f.spin_uyari.setValue(14)
    with patch.object(modul, "oturum_kontrollu_istek", return_value=cevap(201, {"plan_id": 9})) as istek, \
         patch.object(QMessageBox, "warning") as uyar:
        f.kaydet()
    adres = istek.call_args.args
    assert adres == ("POST", "http://x/api/bakim-planlari")
    govde = istek.call_args.kwargs["json"]
    assert govde == {"gorev_turu": "Kalibrasyon", "periyot_gun": 180, "uyari_suresi_gun": 14,
                     "sonraki_gorev_tarihi": QDate.currentDate().addDays(180).toString("yyyy-MM-dd"),
                     "cihaz_id": 1}
    assert f.result() == QDialog.Accepted
    uyar.assert_not_called()


def test_sunucu_hatasi_mesajini_gosterir_ve_form_acik_kalir(yeni_form):
    f = yeni_form
    doldur(f)
    with patch.object(modul, "oturum_kontrollu_istek",
                      return_value=cevap(409, {"detail": "Bu cihaz için aynı türde aktif bir plan zaten var."})), \
         patch.object(QMessageBox, "warning") as uyar:
        f.kaydet()
    assert "aynı türde aktif" in uyar.call_args.args[2]
    assert f.result() != QDialog.Accepted


def test_bag_lanti_hatasi_cokmez_ve_ayrinti_sizdirmaz(yeni_form):
    f = yeni_form
    doldur(f)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=OSError("GIZLI_ADRES")), \
         patch.object(QMessageBox, "critical") as kritik:
        f.kaydet()
    assert "GIZLI_ADRES" not in kritik.call_args.args[2]
    assert f.result() != QDialog.Accepted


def test_eksik_bilgiyle_istek_gonderilmez(yeni_form):
    f = yeni_form
    with patch.object(modul, "oturum_kontrollu_istek") as istek, patch.object(QMessageBox, "warning") as uyar:
        f.kaydet()                                                       # cihaz seçilmedi
    istek.assert_not_called()
    assert "cihaz" in uyar.call_args.args[2].lower()


def test_oturum_bitmisse_mesaj_gosterilmez(yeni_form):
    f = yeni_form
    doldur(f)
    bitmis = cevap(401)
    bitmis._tkys_oturum_reddedildi = True
    with patch.object(modul, "oturum_kontrollu_istek", return_value=bitmis), \
         patch.object(QMessageBox, "warning") as uyar:
        f.kaydet()
    uyar.assert_not_called()


@pytest.fixture
def duzenle_formu(qt_app):
    f = PlanFormu("http://x", "T", plan(plan_id=7, aktif_mi=False))
    yield f
    f.close()
    f.deleteLater()


def test_duzenleme_formu_mevcut_degerleri_gosterir_ve_tarihi_kaydirmaz(duzenle_formu):
    f = duzenle_formu
    assert f.cmb_cihaz is None and "CHZ-001 - EEG Cihazı" in f.lbl_cihaz.text() and f.lbl_cihaz.isReadOnly()
    assert f.cmb_tur.currentText() == "Yıllık bakım" and f.spin_periyot.value() == 365
    assert f.spin_uyari.value() == 30
    assert f.dt_sonraki.date() == QDate(2026, 11, 20)
    assert f.chk_aktif.isVisibleTo(f) and not f.chk_aktif.isChecked()
    f.hazir_secildi(0)                                                   # periyot değişse de tarih kalır
    assert f.dt_sonraki.date() == QDate(2026, 11, 20)


def test_duzenleme_put_gonderir_cihaz_alani_yok_aktiflik_var(duzenle_formu):
    f = duzenle_formu
    f.chk_aktif.setChecked(True)
    with patch.object(modul, "oturum_kontrollu_istek", return_value=cevap(200)) as istek:
        f.kaydet()
    assert istek.call_args.args == ("PUT", "http://x/api/bakim-planlari/7")
    govde = istek.call_args.kwargs["json"]
    assert "cihaz_id" not in govde and govde["aktif_mi"] is True
    assert govde["sonraki_gorev_tarihi"] == "2026-11-20"
    assert f.result() == QDialog.Accepted


# --------------------------------------------------------------------------- ekran
@pytest.fixture
def ekran(qt_app):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu()):
        e = BakimPlanlariEkrani("http://x", "T")
    yield e
    e.close()
    e.deleteLater()


def test_ekran_planlari_ve_ozet_cipleri_gosterir(ekran):
    e = ekran
    assert e.tablo.rowCount() == 3
    assert e.tablo.item(0, 0).text() == "CHZ-001 - EEG Cihazı" and e.tablo.item(0, 1).text() == "Yıllık bakım"
    assert e.tablo.item(0, 2).text() == "Yıllık" and e.tablo.item(0, 3).text() == "30 gün önce"
    assert e.tablo.item(0, 4).text() == "20.11.2026"
    assert e.cip_toplam.text() == "3 plan" and e.cip_yaklasan.text() == "1 yaklaşan"
    assert e.cip_gecmis.text() == "1 gecikmiş"
    assert not e.bos_mesaj.isVisibleTo(e) and e.tablo.isVisibleTo(e)


def hap_metni(ekran, satir):
    from PySide6.QtWidgets import QLabel
    return ekran.tablo.cellWidget(satir, 5).findChild(QLabel).text()


def test_durum_hapi_kalan_gunu_yazar(ekran):
    assert hap_metni(ekran, 0) == "Yaklaşıyor  ·  16 gün kaldı"
    assert hap_metni(ekran, 1) == "Gecikmiş  ·  5 gün gecikti"
    assert hap_metni(ekran, 2) == "Planlı  ·  89 gün kaldı"


def test_bos_liste_aciklayici_mesaj_gosterir(qt_app):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu(planlar=[])):
        e = BakimPlanlariEkrani("http://x", "T")
    assert e.bos_mesaj.isVisibleTo(e) and "Yeni Plan" in e.bos_mesaj.text()
    assert not e.tablo.isVisibleTo(e)
    e.deleteLater()


def test_yukleme_hatasi_anlasilir_mesaj_verir_ve_cokmez(qt_app):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=OSError("yok")):
        e = BakimPlanlariEkrani("http://x", "T")
    assert "yüklenemedi" in e.bos_mesaj.text()
    e.deleteLater()


def test_arama_cihaz_ve_plan_turune_gore_satir_gizler(ekran):
    e = ekran
    e.arama.setText("kalibr")
    assert [e.tablo.isRowHidden(i) for i in range(3)] == [True, False, True]
    e.arama.setText("chz-003")
    assert [e.tablo.isRowHidden(i) for i in range(3)] == [True, True, False]
    e.arama.setText("")
    assert not any(e.tablo.isRowHidden(i) for i in range(3))


def test_aktiflik_filtresi_sunucuya_parametre_olarak_gider(ekran):
    e = ekran
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu(planlar=[])) as istek:
        e.cmb_filtre.setCurrentIndex(2)                                  # Pasif planlar
        adres = istek.call_args.args[1]
        assert adres.endswith("/api/bakim-planlari?aktif_mi=false")
        e.cmb_filtre.setCurrentIndex(1)                                  # Tüm planlar
        assert istek.call_args.args[1].endswith("/api/bakim-planlari")
        e.cmb_filtre.setCurrentIndex(0)                                  # Aktif planlar
        assert istek.call_args.args[1].endswith("?aktif_mi=true")


def test_ilk_acilista_yalniz_aktif_planlar_istenir(qt_app):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu()) as istek:
        e = BakimPlanlariEkrani("http://x", "T")
    assert istek.call_args.args[1].endswith("?aktif_mi=true")
    e.deleteLater()


def test_silme_onaylanirsa_delete_gider_ve_liste_yenilenir(ekran):
    e = ekran
    with patch.object(modul, "sil_onayi", return_value=True) as onay, \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=[cevap(200), cevap(200, PLANLAR[:2])]) as istek:
        e.plan_sil(1)
    assert istek.call_args_list[0].args == ("DELETE", "http://x/api/bakim-planlari/1")
    assert "EEG Cihazı" in onay.call_args.args[2] and "Yıllık bakım" in onay.call_args.args[2]
    assert e.tablo.rowCount() == 2


def test_silme_reddedilirse_istek_gitmez(ekran):
    with patch.object(modul, "sil_onayi", return_value=False), \
         patch.object(modul, "oturum_kontrollu_istek") as istek:
        ekran.plan_sil(1)
    istek.assert_not_called()


def test_silme_basarisizsa_sunucu_mesaji_gosterilir(ekran):
    with patch.object(modul, "sil_onayi", return_value=True), \
         patch.object(modul, "oturum_kontrollu_istek", return_value=cevap(404, {"detail": "Plan bulunamadı."})), \
         patch.object(QMessageBox, "warning") as uyar:
        ekran.plan_sil(1)
    assert uyar.call_args.args[2] == "Plan bulunamadı."


def test_duzenle_ve_yeni_plan_formu_acilir_ve_kayitta_liste_yenilenir(ekran):
    e = ekran
    with patch.object(modul, "PlanFormu") as form, patch.object(e, "verileri_yukle") as yukle:
        form.return_value.exec.return_value = QDialog.Accepted
        e.plan_duzenle(2)
        assert form.call_args.args[2]["plan_id"] == 2
        e.yeni_plan_ekle()
        assert form.call_args.args[2] is None
        assert yukle.call_count == 2
        form.return_value.exec.return_value = QDialog.Rejected
        e.yeni_plan_ekle()
        assert yukle.call_count == 2                                     # vazgeçilince yenilenmez


# ---------------------------------------------------------------- menü ve yetki kaydı
def test_menu_bakim_planlari_sayfasini_dogru_izinle_ve_ikonla_icerir():
    import main_window as mw
    import tkys_sidebar_refined as yan
    kategori = dict(mw.MENU)["CİHAZ YAŞAM DÖNGÜSÜ"]
    oge = next(o for o in kategori if o["ad"] == "Bakım Planları")
    assert oge["izin"] == "Bakım/kalibrasyon planlarını yönetme"
    assert ("＋  Yeni Plan", "Bakım/kalibrasyon planlarını yönetme") in oge["aksiyon"]
    assert yan.PAGE_ICONS["Bakım Planları"] in yan.PATHS
    assert mw.IZIN_KODLARI["Bakım kayıtlarını yönetme"] == ("BAKIM_KAYITLARI_YONET",)   # API izniyle aynı


def test_sayfa_yalniz_cihaz_envanteri_izni_olan_rollere_acilir():
    import main_window as mw
    mw._SUNUCU_YETKILERI.clear()
    gorunen = {rol for rol in mw.ROLLER if mw.izin_var(rol, "Bakım kayıtlarını yönetme")}
    assert gorunen == {"memur", "mudur", "admin"}                        # psikolog/öğrenci/asistan göremez
    mw.yetkileri_ayarla("memur", ["BAKIM_KAYITLARI_YONET"])
    mw.yetkileri_ayarla("psikolog", ["TAKVIM_GORUNTULE"])
    try:
        assert mw.izin_var("memur", "Bakım kayıtlarını yönetme")
        assert not mw.izin_var("psikolog", "Bakım kayıtlarını yönetme")
    finally:
        mw._SUNUCU_YETKILERI.clear()


def test_ana_pencere_yeni_plan_dugmesini_ve_sayfayi_baglar():
    kaynak = open("main_window.py", encoding="utf-8").read()
    assert 'etiket == "＋  Yeni Plan"' in kaynak and "self.yeni_bakim_plani_ac" in kaynak
    assert 'oge["ad"] == "Bakım Planları"' in kaynak and "BakimPlanlariEkrani(" in kaynak
    import main_window as mw
    assert callable(mw.AnaPencere.yeni_bakim_plani_ac)


def test_planlar_bakim_veya_kalibrasyon_izniyle_acilir():
    import main_window as mw

    mw.yetkileri_ayarla("memur", ["BAKIM_KAYITLARI_YONET"])
    mw.yetkileri_ayarla("mudur", ["KALIBRASYON_KAYITLARI_YONET"])
    mw.yetkileri_ayarla("psikolog", ["CIHAZ_ENVANTER_YONET"])

    try:
        izin = "Bakım/kalibrasyon planlarını yönetme"
        assert mw.izin_var("memur", izin)
        assert mw.izin_var("mudur", izin)
        assert not mw.izin_var("psikolog", izin)
    finally:
        mw._SUNUCU_YETKILERI.clear()
