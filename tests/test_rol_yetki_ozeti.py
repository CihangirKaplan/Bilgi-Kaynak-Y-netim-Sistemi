"""'Bu rol neler yapabilir?' özeti: sunucu ucu, izin gruplama ve kullanıcı oluşturma penceresindeki kart.

Gerçek API veya PostgreSQL kullanılmaz.
"""
import gc
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication, QWidget

import k_personel_ekranlari as modul
from k_personel_ekranlari import KullaniciOlusturFormu, izinleri_grupla, yetki_ozeti_getir
from sunucu import app, mevcut_kullanici_id


# ------------------------------------------------------------------ sunucu ucu
@pytest.fixture
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def sunucu_istegi(rol_id, izin_var=1, rol=(4, "DANISMA_OGRENCISI", "Danışma Öğrencisi"), izinler=()):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    sorgular = []

    def calistir(sql, params=None):
        sorgular.append((sql, params))
        if "izin_adi = %s" in sql:           # izin_kontrol sorgusu
            cursor.fetchone.return_value = (izin_var,)
        elif "FROM roller" in sql:
            cursor.fetchone.return_value = rol
        else:
            cursor.fetchall.return_value = list(izinler)

    cursor.execute.side_effect = calistir
    with patch("sunucu.psycopg2.connect", return_value=conn):
        with TestClient(app) as istemci:
            return istemci.get(f"/api/roller/{rol_id}/yetki-ozeti"), sorgular


def test_ozet_rolun_acik_izinlerini_gorunen_adlariyla_dondurur(giris_yapmis_kullanici):
    yanit, sorgular = sunucu_istegi(4, izinler=[("RANDEVU_OLUSTUR", "Randevu Oluştur"), ("ODA_EKLE", None)])
    assert yanit.status_code == 200
    assert yanit.json() == {
        "rol_id": 4, "rol_adi": "DANISMA_OGRENCISI", "gorunen_ad": "Danışma Öğrencisi",
        "izinler": [
            {"izin_adi": "RANDEVU_OLUSTUR", "gorunen_ad": "Randevu Oluştur"},
            {"izin_adi": "ODA_EKLE", "gorunen_ad": "ODA_EKLE"},   # görünen ad yoksa kod adı
        ],
    }
    izin_sorgusu = [s for s, _ in sorgular if "rol_izinleri" in s and "izin_adi = %s" not in s][0]
    assert "izin_var = 1" in izin_sorgusu          # kapalı izinler özete girmez


def test_olmayan_rol_404(giris_yapmis_kullanici):
    yanit, _ = sunucu_istegi(99, rol=None)
    assert yanit.status_code == 404


def test_kullanici_olusturma_izni_olmayan_403_alir(giris_yapmis_kullanici):
    yanit, sorgular = sunucu_istegi(4, izin_var=0)
    assert yanit.status_code == 403
    assert all("izin_adi" in s for s, _ in sorgular)   # rol verisi sorgulanmadı


def test_izin_kontrolu_kullanici_olustur_iznine_bakar(giris_yapmis_kullanici):
    _, sorgular = sunucu_istegi(4)
    assert sorgular[0][1][1] == "KULLANICI_OLUSTUR"


# --------------------------------------------------------------- izin gruplama
def izin(ad, gorunen=None):
    return {"izin_adi": ad, "gorunen_ad": gorunen or ad.title()}


def test_izinler_basliklara_ayrilir_bos_gruplar_atlanir():
    gruplar = izinleri_grupla([
        izin("CIHAZ_EKLE"), izin("RANDEVU_OLUSTUR"), izin("BAKIM_KAYITLARI_YONET"), izin("TAKVIM_GORUNTULE"),
    ])
    assert [g[0] for g in gruplar] == ["Randevu ve Takvim", "Cihazlar"]
    assert gruplar[0][2] == ["Randevu_Olustur", "Takvim_Goruntule"]
    assert len(gruplar[1][2]) == 2


def test_taninmayan_izin_diger_basligina_duser_ve_kaybolmaz():
    gruplar = izinleri_grupla([izin("YENI_BIR_IZIN", "Yeni Bir İzin")])
    assert gruplar == [("Diğer", "•", ["Yeni Bir İzin"])]


def test_bos_izin_listesi_bos_dondurur():
    assert izinleri_grupla([]) == []


# ------------------------------------------------------------------ istemci
def cevap(durum, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = veri or {}
    return r


@pytest.mark.parametrize("durum, beklenen", [
    (403, "yetkiniz yok"),
    (404, "yeniden başlatın"),            # sunucu eski sürümde: uç yok
    (500, "sunucu yanıtı: 500"),
    (422, "sunucu yanıtı: 422"),
])
def test_istemci_hata_durumlarinda_anlasilir_mesaj_verir(monkeypatch, durum, beklenen):
    monkeypatch.setattr(modul, "oturum_kontrollu_istek", lambda *a, **k: cevap(durum))
    veri, mesaj = yetki_ozeti_getir("http://x", "t", 1)
    assert veri is None and beklenen in mesaj


def test_istemci_sunucuya_ulasilamazsa_cokmez(monkeypatch):
    def patla(*a, **k):
        raise OSError("sunucu yok")
    monkeypatch.setattr(modul, "oturum_kontrollu_istek", patla)
    veri, mesaj = yetki_ozeti_getir("http://x", "t", 1)
    assert veri is None and "ulaşılamadı" in mesaj


def test_istemci_dogru_adrese_sorar(monkeypatch):
    istek = MagicMock(return_value=cevap(200, {"izinler": []}))
    monkeypatch.setattr(modul, "oturum_kontrollu_istek", istek)
    veri, hata = yetki_ozeti_getir("http://x", "TOKEN", 4)
    assert hata is None and veri == {"izinler": []}
    assert istek.call_args.args == ("GET", "http://x/api/roller/4/yetki-ozeti")
    assert istek.call_args.kwargs["headers"] == {"Authorization": "Bearer TOKEN"}


# --------------------------------------------------------------------- pencere
@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def form(qt_app):
    pencere = KullaniciOlusturFormu("http://testserver", "TOKEN")
    yield pencere
    pencere.close()
    # Qt nesnesi hemen ve ana iş parçacığında silinsin: sahipsiz kalıp sonradan başka bir
    # iş parçacığında (TestClient) çöp toplayıcıyla silinirse süreç segfault ile çöker.
    pencere.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    # PySide6'da döngüsel referanslı pencere, çöp toplayıcı başka bir iş parçacığında
    # (TestClient) çalışınca Shiboken'ın "ana iş parçacığında sil" yolunda çöküyor.
    # Çöp toplamayı burada, ana iş parçacığında yaparak bunu önlüyoruz.
    pencere = None
    gc.collect()


def rol_sec(form, rol_id):
    form.combo_rol.setCurrentIndex(form.combo_rol.findData(rol_id))


def ozet(rol_adi, izinler):
    return {"rol_id": 1, "rol_adi": rol_adi, "gorunen_ad": rol_adi.title(),
            "izinler": [izin(a) for a in izinler]}


def test_rol_secilmeyince_aciklayici_bos_metin_gorunur(form):
    assert form.yetki_karti.lbl_bilgi.text() == form.yetki_karti.BOS_METIN
    assert form.yetki_karti.kaydirma.isHidden()


def test_rol_secilince_ozet_sunucudan_gelir_ve_kartta_gorunur(form):
    with patch.object(modul, "yetki_ozeti_getir",
                      return_value=(ozet("MEMUR", ["RANDEVU_OLUSTUR", "ODA_EKLE"]), None)) as al:
        rol_sec(form, 2)
    al.assert_called_once_with("http://testserver", "TOKEN", 2)
    kart = form.yetki_karti
    assert kart.lbl_baslik.text() == "Memur"
    assert kart.lbl_rozet.text() == "2 yetki"
    assert not kart.kaydirma.isHidden()
    assert kart.lbl_uyari.isHidden()                       # Memur geniş yetkili sayılmaz


@pytest.mark.parametrize("rol_adi", ["ADMIN", "MUDUR"])
def test_genis_yetkili_rol_uyari_gosterir(form, rol_adi):
    with patch.object(modul, "yetki_ozeti_getir", return_value=(ozet(rol_adi, ["ROL_OLUSTUR"]), None)):
        rol_sec(form, 6)
    assert not form.yetki_karti.lbl_uyari.isHidden()


def test_ayni_rol_ikinci_kez_secilince_sunucuya_tekrar_sorulmaz(form):
    with patch.object(modul, "yetki_ozeti_getir",
                      return_value=(ozet("MEMUR", ["ODA_EKLE"]), None)) as al:
        rol_sec(form, 2)
        rol_sec(form, 3)
        rol_sec(form, 2)
    assert [c.args[2] for c in al.call_args_list] == [2, 3]


def test_alinamayan_ozet_hata_metni_gosterir_pencere_calismaya_devam_eder(form):
    with patch.object(modul, "yetki_ozeti_getir", return_value=(None, "Sunucuya ulaşılamadı.")):
        rol_sec(form, 2)
    assert "Sunucuya ulaşılamadı." in form.yetki_karti.lbl_bilgi.text()
    assert form.btn_kaydet.isEnabled()


def test_hata_onbellege_alinmaz_rol_yeniden_secilince_tekrar_denenir(form):
    sonuclar = [(None, "Hata"), (ozet("MUDUR", ["ODA_EKLE"]), None), (ozet("MEMUR", ["ODA_EKLE"]), None)]
    with patch.object(modul, "yetki_ozeti_getir", side_effect=sonuclar) as al:
        rol_sec(form, 2)
        assert "Hata" in form.yetki_karti.lbl_bilgi.text()
        rol_sec(form, 3)
        rol_sec(form, 2)
    assert al.call_count == 3
    assert form.yetki_karti.lbl_baslik.text() == "Memur"


def test_rol_degisince_eski_roller_listesi_kartta_kalmaz(form):
    sonuclar = [(ozet("ADMIN", ["ODA_EKLE", "CIHAZ_EKLE", "ROL_OLUSTUR"]), None),
                (ozet("MEMUR", ["ODA_EKLE"]), None)]
    with patch.object(modul, "yetki_ozeti_getir", side_effect=sonuclar):
        rol_sec(form, 6)
        rol_sec(form, 2)
    assert form.yetki_karti.icerik_lay.count() == 3   # 1 grup başlığı + 1 liste + esneme boşluğu


def test_rol_secimi_kaldirilinca_bos_metne_donulur(form):
    with patch.object(modul, "yetki_ozeti_getir", return_value=(ozet("MEMUR", ["ODA_EKLE"]), None)):
        rol_sec(form, 2)
    form.combo_rol.setCurrentIndex(0)
    assert form.yetki_karti.lbl_bilgi.text() == form.yetki_karti.BOS_METIN


# ------------------------------------------------- liste gerçekten görünüyor mu (yükseklik)
@pytest.fixture
def gorunen_form(qt_app):
    pencere = KullaniciOlusturFormu("http://testserver", "TOKEN")
    pencere.show()
    yerlesimi_tamamla(pencere)
    yield pencere
    pencere.close()
    pencere.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    gc.collect()


def yerlesimi_tamamla(form):
    """Yalnızca bu pencerenin (ve çocuklarının) bekleyen olaylarını işler. Genel `processEvents`
    kullanılmaz: önceki testlerden kalmış pencereler ağ isteği başlatabilir ve testi bekletir."""
    for _ in range(4):
        for parca in [form, *form.findChildren(QWidget)]:
            QApplication.sendPostedEvents(parca, 0)


def rol_sec_ve_bekle(qt_app, form, izin_adlari, rol_id=5):
    with patch.object(modul, "yetki_ozeti_getir", return_value=(ozet("PROJE_ASISTANI", izin_adlari), None)):
        rol_sec(form, rol_id)
    form._boyut_zamanlayici.stop()               # ertelenmiş adjustSize'ı olay döngüsü yerine elle çalıştırırız
    yerlesimi_tamamla(form)
    form.adjustSize()
    yerlesimi_tamamla(form)


KISA_LISTE = ["RANDEVU_OLUSTUR", "TAKVIM_GORUNTULE", "ODA_DURUMU_GORUNTULE",
              "CIHAZ_UYGUNLUK_GORUNTULE", "CIHAZ_REZERVASYON"]


def test_yetki_listesi_gorunur_yukseklikte_cikar_ve_kesilmez(qt_app, gorunen_form):
    """Eskiden liste, yükseklik henüz yerleşmemiş etiketlerden hesaplandığı için ~0 piksel çıkıyor ve
    kullanıcı yalnızca 'N yetki' rozetini görüyordu."""
    rol_sec_ve_bekle(qt_app, gorunen_form, KISA_LISTE)
    kart = gorunen_form.yetki_karti
    kaydirma = kart.kaydirma
    assert kaydirma.isVisibleTo(gorunen_form)
    gereken = sum(p.sizeHint().height() for p in kart.icerik.findChildren(type(kart.lbl_bilgi)) if p.parent() is kart.icerik)
    assert kaydirma.height() >= 100
    assert kaydirma.height() >= gereken                 # kısa liste kaydırmaya gerek kalmadan sığar
    assert kaydirma.verticalScrollBar().maximum() == 0
    # Her etiket kaydırma alanının içinde ve ölçüsü sıfır değil
    for etiket in kart.icerik.findChildren(type(kart.lbl_bilgi)):
        assert etiket.height() > 0
        assert etiket.geometry().bottom() <= kart.icerik.height()


def test_pencere_icerige_gore_buyur_ve_kart_pencerenin_icinde_kalir(qt_app, gorunen_form):
    onceki = gorunen_form.height()
    rol_sec_ve_bekle(qt_app, gorunen_form, KISA_LISTE)
    assert gorunen_form.height() > onceki               # liste için pencere büyüdü
    kart = gorunen_form.yetki_karti
    assert kart.geometry().bottom() <= gorunen_form.height()
    assert gorunen_form.btn_kaydet.geometry().bottom() <= gorunen_form.height()
    assert gorunen_form.width() >= 460


def test_cok_uzun_liste_sinirli_yukseklikte_kaydirilir(qt_app, gorunen_form):
    uzun = [f"IZIN_{i}" for i in range(40)]
    rol_sec_ve_bekle(qt_app, gorunen_form, uzun)
    kaydirma = gorunen_form.yetki_karti.kaydirma
    assert kaydirma.height() == 230
    assert kaydirma.verticalScrollBar().maximum() > 0   # taşan kısım kaydırılabilir


def test_rol_degisince_pencere_ve_liste_boyutu_yeniden_hesaplanir(qt_app, gorunen_form):
    rol_sec_ve_bekle(qt_app, gorunen_form, KISA_LISTE)
    uzun_yukseklik = gorunen_form.yetki_karti.kaydirma.height()
    rol_sec_ve_bekle(qt_app, gorunen_form, ["ODA_EKLE"], rol_id=2)
    assert gorunen_form.yetki_karti.kaydirma.height() < uzun_yukseklik


# ------------------------------------------- pencere kapanınca bekleyen boyutlandırma hata vermez
def test_pencere_silinince_bekleyen_boyutlandirma_hata_pencereleri_acmaz(qt_app):
    """Kullanıcı bir rol seçip pencereyi hemen kapatırsa, ertelenmiş 'boyutlandır' çağrısı silinmiş
    pencereye ulaşıp 'already deleted' hatası (uygulamada "Beklenmeyen Hata" penceresi) üretmemeli.
    Zamanlayıcı pencerenin çocuğu olduğu için pencereyle birlikte silinir."""
    hatalar = []
    eski = sys.excepthook
    sys.excepthook = lambda tip, deger, tb: hatalar.append(deger)
    try:
        pencere = KullaniciOlusturFormu("http://testserver", "TOKEN")
        with patch.object(modul, "yetki_ozeti_getir", return_value=(ozet("MEMUR", ["ODA_EKLE"]), None)):
            rol_sec(pencere, 2)                    # boyutlandırma zamanlayıcısı başladı
        assert pencere._boyut_zamanlayici.isActive()
        zamanlayici = pencere._boyut_zamanlayici
        pencere.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        pencere = None
        gc.collect()
        for _ in range(3):
            QApplication.sendPostedEvents(None, 0)
        with pytest.raises(RuntimeError):          # zamanlayıcı da pencereyle birlikte silindi
            zamanlayici.isActive()
    finally:
        sys.excepthook = eski
    assert hatalar == []
