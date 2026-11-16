"""Giriş ekranı stili: onay işareti simgesinin yolu Windows'ta da geçerli bir QSS adresi olmalıdır.

QSS'te `url("C:\\Users\\...")` içindeki ters bölüler kaçış dizisi sayılır ve stil dosyasının geri kalanı (giriş düğmesi,
hata kutusu, onay işareti) sessizce uygulanmaz; bu yüzden yol her zaman ileri bölülü verilmelidir.

Not: `client.login_ekrani` içe aktarılınca genel `sys.excepthook` değişir (bir kutu açar); bu yüzden yalnızca testin içinde içe
aktarılır ve kanca sonra eski haline getirilir (tüm oturumda başka testleri kilitlemesin).
"""
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WINDOWS_YOLU = "C:\\Users\\SENA\\Documents\\Proje\\client\\assets\\tkys_checkbox_check.svg"


@pytest.fixture
def login_ekrani():
    onceki = sys.excepthook
    import client.login_ekrani as modul
    yield modul
    sys.excepthook = onceki


def test_windows_yolu_ileri_bolulu_yapilir_ve_yer_tutucu_kalmaz(login_ekrani):
    stil = login_ekrani.stil_olustur(WINDOWS_YOLU)
    assert "\\" not in stil                                                             # hiç ters bölü yok
    assert 'url("C:/Users/SENA/Documents/Proje/client/assets/tkys_checkbox_check.svg")' in stil
    assert "__TKYS_CHECK_ICON__" not in stil


def test_stil_giris_dugmesi_ve_onay_isareti_kurallarini_icerir(login_ekrani):
    stil = login_ekrani.stil_olustur("/x/tik.svg")
    for kural in ("QPushButton#giris", "QCheckBox::indicator:checked", "QLabel#hata", "QLabel#guvenlik"):
        assert kural in stil


def test_ekran_gercek_simge_dosyasiyla_acilir_ve_stil_ileri_bolulu(login_ekrani, tkys_qapplication):
    ekran = login_ekrani.LoginEkrani()
    assert "\\" not in ekran.styleSheet() and os.path.exists(login_ekrani.ONAY_ISARETI_DOSYASI)
    assert ekran.goster.text() == "Şifreyi göster" and ekran.giris_btn.objectName() == "giris"
    ekran.close()
