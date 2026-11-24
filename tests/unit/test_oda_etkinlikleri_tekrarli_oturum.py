"""Etkinlik formunda "Tekrarlı Ekle": tarih aralığı + haftanın günleri + saat ile düzenli oturumları tek seferde üretme."""
from datetime import date
from unittest.mock import patch

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import QDialog

import client.oda_etkinlikleri_ekrani as modul
from client.oda_etkinlikleri_ekrani import OdaEtkinlikFormu, TekrarliOturumDialog, tekrar_tarihleri

ODALAR = [{"oda_id": 1, "oda_adi": "EEG Odası"}]
PERSONELLER = [{"personel_id": 1, "kullanici_adi": "memur", "personel_kodu": "P1"}]
SAAT_BAS, SAAT_BIT = QTime(13, 0), QTime(14, 0)


def _form(kayit=None):
    return OdaEtkinlikFormu(ODALAR, PERSONELLER, kayit)


def _tarihler(form):
    return [t.date().toPython() for _, t, _, _ in form.oturum_satirlari]


def test_tekrar_tarihleri_haftanin_gunlerine_gore_uretir():
    # 2049-06-07 Pazartesi ... 2049-06-20 Pazar (iki tam hafta)
    iki_hafta = tekrar_tarihleri(date(2049, 6, 7), date(2049, 6, 20), [0, 1, 2, 3, 4])
    assert len(iki_hafta) == 10 and all(g.weekday() < 5 for g in iki_hafta)
    assert iki_hafta[0] == date(2049, 6, 7) and iki_hafta[-1] == date(2049, 6, 18)

    yalniz_carsamba = tekrar_tarihleri(date(2049, 6, 7), date(2049, 7, 4), [2])         # 4 hafta
    assert yalniz_carsamba == [date(2049, 6, 9), date(2049, 6, 16), date(2049, 6, 23), date(2049, 6, 30)]

    assert tekrar_tarihleri(date(2049, 6, 7), date(2049, 6, 7), [0]) == [date(2049, 6, 7)]  # tek gün, ikisi dahil
    assert tekrar_tarihleri(date(2049, 6, 20), date(2049, 6, 7), [0, 1]) == []              # ters aralık
    assert tekrar_tarihleri(date(2049, 6, 7), date(2049, 6, 20), []) == []                  # gün seçilmedi


def test_pencere_ilk_gunun_haftanin_gununu_secili_acar_ve_onizleme_gosterir(tkys_qapplication):
    pencere = TekrarliOturumDialog(None, QDate(2049, 6, 9))                                 # Çarşamba
    assert pencere.secili_gunler() == [2]
    assert pencere.ekle_btn.isEnabled()
    assert pencere.onizleme.text().startswith("4 oturum eklenecek")                         # varsayılan 4 hafta

    pencere.hafta_ici_sec()
    assert pencere.secili_gunler() == [0, 1, 2, 3, 4]
    assert pencere.onizleme.text().startswith("20 oturum eklenecek")
    tarihler, bas, bit = pencere.sonuc()
    assert len(tarihler) == 20 and bas == SAAT_BAS and bit == SAAT_BIT


def test_pencere_gecersiz_secimde_ekle_kapali_ve_neden_yazili(tkys_qapplication):
    pencere = TekrarliOturumDialog(None, QDate(2049, 6, 9))

    def kapali(beklenen):
        assert not pencere.ekle_btn.isEnabled() and beklenen in pencere.hata.text(), pencere.hata.text()

    pencere.bit_tarih.setDate(QDate(2049, 6, 1))
    kapali("ilk günden önce")
    pencere.bit_tarih.setDate(QDate(2050, 6, 20))                                           # 366 günden uzun
    kapali("en fazla 366 gün")
    pencere.bit_tarih.setDate(QDate(2049, 6, 10))                                           # Çarşamba..Perşembe, yalnız Pazartesi seçili
    pencere.gun_kutulari[2].setChecked(False)
    kapali("En az bir gün")
    pencere.gun_kutulari[0].setChecked(True)
    kapali("denk gelen tarih yok")

    pencere.gun_kutulari[2].setChecked(True)
    assert pencere.ekle_btn.isEnabled() and not pencere.hata.text()
    for bas, bit in ((QTime(13, 0), QTime(12, 0)), (QTime(7, 0), QTime(9, 0)), (QTime(17, 0), QTime(19, 0))):
        pencere.saat_bas.setTime(bas)
        pencere.saat_bit.setTime(bit)
        kapali("08.00–18.00")
    pencere.saat_bas.setTime(QTime(8, 0))
    pencere.saat_bit.setTime(QTime(18, 0))
    assert pencere.ekle_btn.isEnabled()


def test_form_tekrarli_oturumlari_ekler_ve_ilk_bos_satiri_degistirir(tkys_qapplication):
    form = _form()
    assert len(form.oturum_satirlari) == 1 and form._varsayilan_satir_mi(form.oturum_satirlari[0])

    gunler = tekrar_tarihleri(date(2049, 6, 7), date(2049, 6, 20), [0, 2])                  # 4 oturum
    assert form.tekrarli_oturumlari_ekle(gunler, SAAT_BAS, SAAT_BIT) == 4
    assert _tarihler(form) == gunler                                                        # kendiliğinden gelen "bugün" satırı kalmadı

    form.ad.setText("Düzenli eğitim")
    veri = form.veri()
    assert [g["baslangic_zamani"] for g in veri["gunler"]][0] == "2049-06-07T13:00:00"
    assert all(g["bitis_zamani"].endswith("T14:00:00") for g in veri["gunler"])
    form.kaydet()
    assert form.result() == QDialog.Accepted                                                # üretilen oturumlar formun denetiminden geçer


def test_degistirilmis_ilk_satir_korunur(tkys_qapplication):
    form = _form()
    form.oturum_satirlari[0][1].setDate(QDate(2049, 5, 3))                                  # kullanıcı ilk satırı kendisi ayarlamış
    form.tekrarli_oturumlari_ekle([date(2049, 6, 7)], SAAT_BAS, SAAT_BIT)
    assert _tarihler(form) == [date(2049, 5, 3), date(2049, 6, 7)]


def test_ayni_gun_ve_saatteki_oturum_tekrar_eklenmez(tkys_qapplication):
    form = _form()
    form.tekrarli_oturumlari_ekle([date(2049, 6, 7), date(2049, 6, 9)], SAAT_BAS, SAAT_BIT)

    with patch.object(modul.QMessageBox, "information") as bilgi:
        assert form.tekrarli_oturumlari_ekle([date(2049, 6, 7), date(2049, 6, 9)], SAAT_BAS, SAAT_BIT) == 0
    bilgi.assert_called_once()
    assert len(form.oturum_satirlari) == 2

    assert form.tekrarli_oturumlari_ekle([date(2049, 6, 9), date(2049, 6, 14)], SAAT_BAS, SAAT_BIT) == 1   # yalnız yenisi
    assert _tarihler(form) == [date(2049, 6, 7), date(2049, 6, 9), date(2049, 6, 14)]

    assert form.tekrarli_oturumlari_ekle([date(2049, 6, 7)], QTime(9, 0), QTime(10, 0)) == 1               # aynı gün, farklı saat serbest


def test_oturum_sinirini_asan_secim_hicbir_sey_eklemez(tkys_qapplication):
    form = _form()
    gunler = tekrar_tarihleri(date(2049, 1, 1), date(2049, 12, 31), range(7))               # 365 gün
    assert form.tekrarli_oturumlari_ekle(gunler, SAAT_BAS, SAAT_BIT) == 365
    with patch.object(modul.QMessageBox, "warning") as uyari:
        assert form.tekrarli_oturumlari_ekle([date(2050, 1, 1), date(2050, 1, 2)], SAAT_BAS, SAAT_BIT) == 0
    uyari.assert_called_once()
    assert len(form.oturum_satirlari) == 365                                                # kısmen eklenmez, hepsi ya da hiçbiri


def test_duzenleme_modunda_mevcut_oturumlar_silinmez(tkys_qapplication):
    kayit = {
        "oda_id": 1, "organize_eden_personel_id": 1, "etkinlik_adi": "Eski", "katilimci_sayisi": None,
        "oda_adi": "EEG Odası", "duzenleyen_adi": "memur",
        "gunler": [{"baslangic_zamani": "2049-06-07T13:00:00", "bitis_zamani": "2049-06-07T14:00:00"}],
    }
    form = _form(kayit)
    assert form.kayit_modu and len(form.oturum_satirlari) == 1
    form.tekrarli_oturumlari_ekle([date(2049, 6, 9)], SAAT_BAS, SAAT_BIT)
    assert _tarihler(form) == [date(2049, 6, 7), date(2049, 6, 9)]


def test_dugmeler_formda_var_ve_pencereyi_acar(tkys_qapplication):
    form = _form()
    assert form.tekrarli_btn.text().endswith("Tekrarlı Ekle…") and form.gun_ekle_btn.text().endswith("Gün / Saat Ekle")
    with patch.object(modul, "TekrarliOturumDialog") as sinif:
        sinif.return_value.exec.return_value = QDialog.Rejected
        form.tekrarli_btn.click()
    sinif.assert_called_once()
    assert len(form.oturum_satirlari) == 1                                                  # vazgeçilince hiçbir şey eklenmez
    form.gun_ekle_btn.click()
    assert len(form.oturum_satirlari) == 2
