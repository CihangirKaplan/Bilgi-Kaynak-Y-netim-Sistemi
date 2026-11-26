"""Denetim kaydı ayrıntı penceresi: tek cümlelik özet, okunur hedef, önceki/yeni karşılaştırma tablosu."""

import gc
import os
import weakref
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

import client.audit_kayitlari_ekrani as modul


def _kayit(olay, **ek):
    kayit = {"denetim_id": 9, "kullanici_id": 1, "kullanici_adi": "admin", "olay_turu": olay, "hedef_tablo": None,
             "hedef_kayit_id": None, "hedef_kullanici_adi": None, "istemci_adresi": "10.0.0.5", "ayrinti": None}
    kayit.update(ek)
    return kayit


@pytest.mark.parametrize("kayit, beklenen", [
    (_kayit("LOGIN"), "admin sisteme giriş yaptı."),
    (_kayit("LOGIN_FAILED", kullanici_adi="Bilinmeyen kullanıcı", ayrinti={"kullanici_adi": "deneme"}),
     "“deneme” adıyla başarısız bir giriş denemesi yapıldı."),
    (_kayit("LOGOUT"), "admin oturumu kapattı."),
    (_kayit("PASSWORD_RESET", hedef_tablo="kullanicilar", hedef_kayit_id=4, hedef_kullanici_adi="ayse"),
     "admin, ayse kullanıcısının parolasını sıfırladı."),
    (_kayit("ROLE_CHANGE", hedef_tablo="kullanicilar", hedef_kayit_id=4, hedef_kullanici_adi="ayse"),
     "admin, ayse kullanıcısının rollerini değiştirdi."),
    (_kayit("VIEW", hedef_tablo="denetim_kayitlari"), "admin denetim kayıtlarını görüntüledi."),
    (_kayit("CREATE", hedef_tablo="randevular", hedef_kayit_id=3), "admin, yeni bir “Randevu” kaydı oluşturdu."),
    (_kayit("DELETE", hedef_tablo="cihazlar", hedef_kayit_id=3), "admin, “Cihaz” kaydını sildi."),
    (_kayit("EXPORT", ayrinti={"liste": "OGRENCI"}), "admin, “Öğrenci” listesini Excel'e aktardı."),
    (_kayit("EXPORT", ayrinti={"liste": "OGRENCI", "bicim": "PDF"}), "admin, “Öğrenci” listesini PDF olarak kaydetti."),
    (_kayit("EXPORT", ayrinti={"bicim": "PDF"}), "admin bir listeyi PDF olarak kaydetti."),
])
def test_olay_cumlesi(kayit, beklenen):
    assert modul.olay_cumlesi(kayit) == beklenen


def test_olay_cumlesi_bilinmeyen_olay_ve_kullanici_yedegi():
    assert modul.olay_cumlesi(_kayit("YENI_OLAY", kullanici_adi=None)) == "Bilinmeyen kullanıcı: YENI_OLAY"


def test_hedef_metni():
    assert modul.hedef_metni(_kayit("VIEW")) == "—"
    assert modul.hedef_metni(_kayit("UPDATE", hedef_tablo="randevular", hedef_kayit_id=12)) == "Randevu (no 12)"
    assert modul.hedef_metni(_kayit("UPDATE", hedef_tablo="odalar")) == "Oda"
    assert modul.hedef_metni(_kayit("UPDATE", hedef_tablo="kullanicilar", hedef_kayit_id=2, hedef_kullanici_adi="ali")) == "Kullanıcı: ali"
    assert "silinmiş" in modul.hedef_metni(_kayit("DELETE", hedef_tablo="kullanicilar", hedef_kayit_id=2))


@pytest.fixture(scope="module")
def qt_app():
    yield QApplication.instance() or QApplication([])


class _Ekran(modul.AuditKayitlariEkrani):
    def __init__(self):                                   # yalnızca ayrıntı penceresi denenir; sunucuya gitmez
        QWidget.__init__(self)


def _pencereyi_incele(qt_app, kayit):
    sonuc = {}

    def sahte_exec(pencere):
        sonuc["etiketler"] = [e.text() for e in pencere.findChildren(QLabel)]
        sonuc["adlar"] = {e.objectName() for e in pencere.findChildren(QLabel)}
        return 0

    ekran = _Ekran()
    with patch.object(modul.QDialog, "exec", sahte_exec):
        ekran._audit_detayini_goster(kayit, "25.11.2026 10:00:00")
    return sonuc


def test_pencere_ozet_cumlesi_ve_okunur_hedefi_gosterir(qt_app):
    sonuc = _pencereyi_incele(qt_app, _kayit("UPDATE", hedef_tablo="randevular", hedef_kayit_id=12))
    assert "admin, “Randevu” kaydını güncelledi." in sonuc["etiketler"]
    assert "Randevu (no 12)" in sonuc["etiketler"] and "Güncelleme" in sonuc["etiketler"]
    assert "admin (kullanıcı no 1)" in sonuc["etiketler"]
    assert "randevular" not in sonuc["etiketler"]                      # ham tablo adı gösterilmez


def test_pencere_onceki_yeni_karsilastirma_tablosu(qt_app):
    sonuc = _pencereyi_incele(qt_app, _kayit("UPDATE", hedef_tablo="ogrenci_faaliyet_takip", hedef_kayit_id=8,
                                              ayrinti={"onceki": {"puan": 8}, "yeni": {"puan": 12}, "neden": "Düzeltme"}))
    etiketler = sonuc["etiketler"]
    assert {"ALAN", "ÖNCEKİ", "YENİ", "Puan", "8", "12"} <= set(etiketler)
    assert "Neden" in etiketler and "Düzeltme" in etiketler           # tabloda olmayan ayrıntılar altta kalır
    assert "Önceki değer" not in etiketler                            # eski tek satırlık gösterim yok


def test_pencere_ayrintisiz_kayitta_ayrinti_basligi_yok(qt_app):
    sonuc = _pencereyi_incele(qt_app, _kayit("LOGOUT"))
    assert "Değişiklik Ayrıntısı" not in sonuc["etiketler"]


def test_sayfa_ve_pencere_bellekten_serbest_birakilir(qt_app):
    ekran = _Ekran()
    with patch.object(modul.QDialog, "exec", lambda pencere: 0):
        ekran._audit_detayini_goster(_kayit("UPDATE", ayrinti={"onceki": {"a": 1}, "yeni": {"a": 2}}), "t")
    referans = weakref.ref(ekran)
    del ekran
    gc.collect()
    assert referans() is None
