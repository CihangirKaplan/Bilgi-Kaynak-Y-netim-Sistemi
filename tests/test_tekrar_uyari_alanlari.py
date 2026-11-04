"""Bakım/kalibrasyon formlarındaki 'Tekrar aralığı' ve 'Uyarı süresi' alanları."""
import datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QDateEdit, QFormLayout

import cihaz_bakim_ekranlari
import cihaz_kalibrasyon_ekranlari
from tekrar_uyari_alanlari import TekrarUyariAlanlari


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def cevap(durum, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = veri if veri is not None else []
    return r


def uyari_sec(t, gun):
    t.cmb_uyari.setCurrentIndex(t.cmb_uyari.findData(gun))


def alanlar(ay=None, uyari=30, bitis=QDate(2026, 3, 10), sonraki=QDate(2026, 9, 10)):
    dt_bitis, dt_sonraki = QDateEdit(bitis), QDateEdit(sonraki)
    return dt_bitis, dt_sonraki, TekrarUyariAlanlari(dt_bitis, dt_sonraki, "Sonraki bakım",
                                                     uyari_suresi=uyari, varsayilan_ay=ay)


def test_varsayilan_secim_sonraki_tarihi_bitisten_hesaplar(qt_app):
    bitis, sonraki, t = alanlar(ay=6)
    assert t.secili_ay() == 6
    assert sonraki.date() == QDate(2026, 9, 10)
    assert not sonraki.isEnabled()                         # ay düğmesinde tarih kilitli, yerinde görünür
    assert "10.09.2026" in t.lbl_sonuc.text() and "6 ay" in t.lbl_sonuc.text()
    bitis.setDate(QDate(2026, 4, 30))                      # bitiş değişince sonraki de kayar
    assert sonraki.date() == QDate(2026, 10, 30)


def test_dugme_secilince_hesaplanir(qt_app):
    bitis, sonraki, t = alanlar()
    t.butonlar[12].click()                                 # "1 yıl"
    assert sonraki.date() == QDate(2027, 3, 10)
    assert "1 yıl" in t.lbl_sonuc.text()
    t.butonlar[3].click()
    assert sonraki.date() == QDate(2026, 6, 10)


def test_tarih_sec_kutuyu_acar_ve_tarih_ezilmez(qt_app):
    bitis, sonraki, t = alanlar(ay=6)
    t.butonlar[None].click()                               # "Tarih seç"
    assert sonraki.isEnabled() and t.secili_ay() is None
    sonraki.setDate(QDate(2026, 12, 1))
    bitis.setDate(QDate(2026, 5, 5))                       # artık otomatik hesap yok
    assert sonraki.date() == QDate(2026, 12, 1)
    assert "kutudan seçin" in t.lbl_sonuc.text()


def test_kayitli_tarih_korunur_ve_uyari_dolar(qt_app):
    bitis, sonraki, t = alanlar(ay=None, uyari=45)
    assert t.secili_ay() is None and sonraki.isEnabled()
    assert sonraki.date() == QDate(2026, 9, 10)
    assert t.uyari_suresi() == 45                          # listede olmayan değer de gösterilir
    bitis.setDate(QDate(2026, 4, 1))
    assert sonraki.date() == QDate(2026, 9, 10)


def test_ozet_metinleri(qt_app):
    bugun = datetime.date.today()
    _, sonraki, t = alanlar(uyari=30)
    sonraki.setDate(QDate(bugun.year - 1, 1, 1))
    assert "geçmişte" in t.lbl_ozet.text()
    sonraki.setDate(QDate.currentDate().addDays(100))
    assert "(30 gün kala)" in t.lbl_ozet.text() and "bildirim düşer" in t.lbl_ozet.text()
    sonraki.setDate(QDate.currentDate().addDays(10))
    assert "bildirim şimdiden görünür" in t.lbl_ozet.text()
    uyari_sec(t, 0)
    assert "günü bildirim düşer" in t.lbl_ozet.text()


def test_satirlar_forma_eklenir(qt_app):
    _, _, t = alanlar()
    form = QFormLayout()
    t.satirlari_ekle(form)
    assert form.rowCount() == 3
    assert t.sonraki.parentWidget() is not None and len(t.butonlar) == 4


# ------------------------------------------------------------------ formlar
def formu_ac(modul, sinif, *ek):
    with patch.object(modul, "oturum_kontrollu_istek", return_value=cevap(200, [])):
        return getattr(modul, sinif)("http://x", "T", *ek)


def yukleme(modul, sinif, ek, doldur):
    form = formu_ac(modul, sinif, *ek)
    for alan, deger in (("txt_kisi", "k"), ("txt_kurum", "k"), ("txt_sertifika", "s")):
        if hasattr(form, alan):
            getattr(form, alan).setText(deger)
    if hasattr(form, "txt_islem"):
        form.txt_islem.setPlainText("i")
    doldur(form)
    with patch.object(modul, "cakisma_cozumlu_istek", return_value=None) as g:
        form.kaydet()
    form.close()
    return g.call_args.args[3]


def test_yeni_bakim_formu_varsayilan_6_ay_ve_payload(qt_app):
    modul = cihaz_bakim_ekranlari
    form = formu_ac(modul, "YeniBakimFormu")
    assert form.tekrar.secili_ay() == 6
    assert form.dt_sonraki_bakim.date() == form.dt_bitis.date().addMonths(6)
    form.close()
    veri = yukleme(modul, "YeniBakimFormu", (), lambda f: uyari_sec(f.tekrar, 15))
    assert veri["uyari_suresi_gun"] == 15


def test_yeni_kalibrasyon_formu_varsayilan_1_yil_ve_payload(qt_app):
    modul = cihaz_kalibrasyon_ekranlari
    form = formu_ac(modul, "YeniKalibrasyonFormu")
    assert form.tekrar.secili_ay() == 12
    assert form.dt_gecerlilik.date() == form.dt_bitis.date().addMonths(12)
    form.close()
    veri = yukleme(modul, "YeniKalibrasyonFormu", (), lambda f: uyari_sec(f.tekrar, 60))
    assert veri["uyari_suresi_gun"] == 60


def test_bakim_duzenle_formu_kayitli_degerleri_korur(qt_app):
    modul = cihaz_bakim_ekranlari
    kayit = {"bakim_id": 9, "cihaz_adi": "E1 - C", "bakim_baslangic_tarihi": "2026-03-01",
             "bakim_bitis_tarihi": "2026-03-02", "sonraki_bakim_tarihi": "2026-10-15",
             "uyari_suresi_gun": 45}
    form = formu_ac(modul, "BakimDuzenleFormu", kayit)
    assert form.dt_sonraki_bakim.date() == QDate(2026, 10, 15)
    assert form.tekrar.secili_ay() is None
    assert form.tekrar.uyari_suresi() == 45
    form.close()
    veri = yukleme(modul, "BakimDuzenleFormu", (kayit,), lambda f: uyari_sec(f.tekrar, 7))
    assert veri["uyari_suresi_gun"] == 7 and veri["sonraki_bakim_tarihi"] == "2026-10-15"


def test_kalibrasyon_duzenle_formu_kayitli_degerleri_korur(qt_app):
    modul = cihaz_kalibrasyon_ekranlari
    kayit = {"kalibrasyon_id": 9, "cihaz_adi": "E1 - C", "kalibrasyon_baslangic_tarihi": "2026-03-01",
             "kalibrasyon_bitis_tarihi": "2026-03-02", "gecerlilik_tarihi": "2027-03-02",
             "uyari_suresi_gun": 90}
    form = formu_ac(modul, "KalibrasyonDuzenleFormu", kayit)
    assert form.dt_gecerlilik.date() == QDate(2027, 3, 2)
    assert form.tekrar.uyari_suresi() == 90
    form.close()


def test_eski_kayitta_uyari_suresi_yoksa_30_olur(qt_app):
    kayit = {"bakim_id": 9, "cihaz_adi": "E1 - C"}
    form = formu_ac(cihaz_bakim_ekranlari, "BakimDuzenleFormu", kayit)
    assert form.tekrar.uyari_suresi() == 30
    form.close()


def test_bildirim_satiri_ve_secenek_adlari_anlasilir(qt_app):
    _, _, t = alanlar(uyari=45)                            # listede olmayan değer de aynı biçimde eklenir
    form = QFormLayout()
    t.satirlari_ekle(form)
    ogeler = [form.itemAt(i, QFormLayout.LabelRole) for i in range(form.rowCount())]
    etiketler = [o.widget().text() for o in ogeler if o is not None and o.widget() is not None and o.widget().text()]
    assert etiketler == ["Sonraki bakım:", "Bildirim ne zaman:"]
    secenekler = [t.cmb_uyari.itemText(i) for i in range(t.cmb_uyari.count())]
    assert secenekler == ["Tarihi geldiği gün", "7 gün kala", "15 gün kala", "30 gün kala",
                          "60 gün kala", "90 gün kala", "45 gün kala"]
