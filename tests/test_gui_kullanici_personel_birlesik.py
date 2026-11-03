"""TKYS - Kullanıcı oluşturma ve personel atama birleşik ekranı (PySide6 GUI testleri).

Gerçek API veya PostgreSQL kullanılmaz.
"""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import k_personel_ekranlari as modul
from k_personel_ekranlari import (
    KullaniciOlusturFormu,
    kullanici_adi_oner,
    musait_kullanici_adi,
    ogrenci_bilgisi_dogrula,
    personel_ata,
    personel_kodu_uret,
    telefon_bicimle,
    telefon_normalle,
)


@pytest.fixture(scope="module")
def qt_app():
    uygulama = QApplication.instance()
    if uygulama is None:
        uygulama = QApplication([])
    return uygulama


def cevap(durum, veri=None):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False  # merkezi oturum sistemi bu yanıtı "oturum bitti" saymasın
    r.status_code = durum
    r.json.return_value = veri if veri is not None else {}
    r.text = str(veri)
    return r


@pytest.fixture(autouse=True)
def istek_yonlendirici(monkeypatch):
    """Ekran ağ isteklerini merkezi `oturum_kontrollu_istek` ile yapar; testlerde bu çağrı,
    aşağıdaki testlerin yamaladığı requests.get/post'a yönlendirilir (gerçek ağ isteği atılmaz)."""
    def yonlendir(yontem, url, **kwargs):
        return getattr(modul.requests, yontem.lower())(url, **kwargs)
    monkeypatch.setattr(modul, "oturum_kontrollu_istek", yonlendir)


@pytest.fixture(autouse=True)
def sunucu_yok(monkeypatch):
    """Varsayılan: GET istekleri sunucuya ulaşamaz (gerçek ağ isteği atılmaz)."""
    monkeypatch.setattr(modul.requests, "get", MagicMock(side_effect=OSError("sunucu yok")))


@pytest.fixture
def form(qt_app):
    pencere = KullaniciOlusturFormu("http://testserver", "TOKEN")
    yield pencere
    pencere.close()


def rol_sec(form, rol_id):
    form.combo_rol.setCurrentIndex(form.combo_rol.findData(rol_id))


# ---------------------------------------------------------------- yardımcılar
def test_personel_kodu_rolun_sonraki_numarasini_uretir():
    kayitlar = [
        {"personel_kodu": "PER-OGR-001"},
        {"personel_kodu": "PER-OGR-004"},
        {"personel_kodu": "PER-PSK-009"},
        {"personel_kodu": "BOZUK-KOD"},
    ]
    with patch.object(modul.requests, "get", return_value=cevap(200, kayitlar)):
        assert personel_kodu_uret("http://x", "t", "DANISMA_OGRENCISI") == "PER-OGR-005"
        assert personel_kodu_uret("http://x", "t", "MEMUR") == "PER-MEM-001"


def test_personel_kodu_sunucuya_ulasilamazsa_ilk_numaradan_baslar():
    with patch.object(modul.requests, "get", side_effect=OSError("kapalı")):
        assert personel_kodu_uret("http://x", "t", "PSIKOLOG") == "PER-PSK-001"


def test_personel_ata_ogrenci_bilgisini_gonderir_bos_alanlari_atar():
    with patch.object(modul.requests, "post", return_value=cevap(201)) as post:
        ok, _ = personel_ata("http://x", "t", 8, "PER-OGR-001",
                             {"ad_soyad": "Veli Kaya", "ogrenci_numarasi": "2021002", "telefon": ""})
    assert ok
    assert post.call_args.kwargs["json"] == {
        "kullanici_id": 8, "personel_kodu": "PER-OGR-001",
        "ad_soyad": "Veli Kaya", "ogrenci_numarasi": "2021002",
    }


def test_personel_ata_sunucu_mesajini_dondurur():
    with patch.object(modul.requests, "post",
                      return_value=cevap(409, {"detail": "Bu öğrenci numarası başka bir öğrenci kaydında kullanılıyor."})):
        ok, mesaj = personel_ata("http://x", "t", 8, "PER-OGR-001", None)
    assert not ok and "öğrenci numarası" in mesaj


# ------------------------------------------------------------- birleşik pencere
def test_ogrenci_alanlari_yalnizca_danisma_ogrencisinde_gorunur(form):
    assert form.ogrenci_kutusu.isHidden()
    rol_sec(form, 4)
    assert not form.ogrenci_kutusu.isHidden()
    rol_sec(form, 1)
    assert form.ogrenci_kutusu.isHidden()


def test_danisma_ogrencisi_ad_ve_numarasiz_olusturulamaz(form):
    form.input_kullanici_adi.setText("yeni_ogrenci")
    rol_sec(form, 4)
    with patch.object(modul.requests, "post") as post, patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    post.assert_not_called()
    uyari.assert_called_once()


def test_olusturunca_personel_ata_bolumu_acilir_ve_form_kilitlenir(form):
    form.input_kullanici_adi.setText("doktor_x")
    rol_sec(form, 1)
    assert form.sonuc_kutusu.isHidden()
    with patch.object(modul.requests, "post",
                      return_value=cevap(201, {"kullanici_id": 30, "gecici_parola": "Abc123!x"})):
        form.kaydet()
    assert not form.sonuc_kutusu.isHidden()
    assert "Abc123!x" in form.lbl_sonuc.text()
    assert not form.btn_kaydet.isEnabled()
    assert not form.input_kullanici_adi.isEnabled()
    assert form.olusturulan_kullanici["kullanici_id"] == 30


def test_ayni_kullanici_adi_409_pencereyi_kilitlemez(form):
    form.input_kullanici_adi.setText("var_olan")
    rol_sec(form, 1)
    with patch.object(modul.requests, "post", return_value=cevap(409)), \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    uyari.assert_called_once()
    assert form.btn_kaydet.isEnabled() and form.sonuc_kutusu.isHidden()


def test_personel_ata_danisma_ogrencisi_icin_ogrenci_bilgisini_yollar(form):
    form.input_kullanici_adi.setText("ogr_yeni")
    rol_sec(form, 4)
    form.input_ad_soyad.setText("Veli Kaya")
    form.input_ogrenci_no.setText("2021002")
    form.input_telefon.setText("05551112233")
    with patch.object(modul.requests, "post",
                      return_value=cevap(201, {"kullanici_id": 31, "gecici_parola": "Pw"})):
        form.kaydet()

    atamalar = []

    def post(url, **kwargs):
        atamalar.append((url, kwargs["json"]))
        return cevap(201)

    with patch.object(modul.requests, "get", return_value=cevap(200, [])), \
            patch.object(modul.requests, "post", side_effect=post), \
            patch.object(QMessageBox, "information"):
        form.personel_ata_tiklandi()

    assert form.personel_atandi and form.result() == QDialog.Accepted
    url, govde = atamalar[0]
    assert url.endswith("/api/personel")
    assert govde == {
        "kullanici_id": 31, "personel_kodu": "PER-OGR-001",
        "ad_soyad": "Veli Kaya", "ogrenci_numarasi": "2021002", "telefon": "05551112233",
    }


def test_personel_ata_diger_rollerde_ogrenci_bilgisi_gondermez(form):
    form.input_kullanici_adi.setText("memur_yeni")
    rol_sec(form, 2)
    with patch.object(modul.requests, "post", return_value=cevap(201, {"kullanici_id": 32, "gecici_parola": "Pw"})):
        form.kaydet()
    atamalar = []
    with patch.object(modul.requests, "get", return_value=cevap(200, [])), \
            patch.object(modul.requests, "post", side_effect=lambda u, **k: (atamalar.append(k["json"]), cevap(201))[1]), \
            patch.object(QMessageBox, "information"):
        form.personel_ata_tiklandi()
    assert atamalar[0] == {"kullanici_id": 32, "personel_kodu": "PER-MEM-001"}


def test_personel_atanmadan_kapatirken_uyarir_ve_hayirda_kapatmaz(form):
    form.input_kullanici_adi.setText("doktor_y")
    rol_sec(form, 1)
    with patch.object(modul.requests, "post", return_value=cevap(201, {"kullanici_id": 33, "gecici_parola": "Pw"})):
        form.kaydet()
    kapandi = []
    form.rejected.connect(lambda: kapandi.append(True))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No) as soru:
        form.reject()
    soru.assert_called_once()
    assert kapandi == []
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        form.reject()
    assert kapandi == [True]


def test_hesap_olusturulmadan_kapatirken_uyari_yok(form):
    with patch.object(QMessageBox, "question") as soru:
        form.reject()
    soru.assert_not_called()


# ------------------------------------------------------------------ doğrulama
def ogr(ad="Veli Kaya", no="2021002", tel=""):
    return {"ad_soyad": ad, "ogrenci_numarasi": no, "telefon": tel}


@pytest.mark.parametrize("bilgi, beklenen", [
    (ogr(), None),
    (ogr(tel="05551234567"), None),
    (ogr(no="1" * 15), None),
    (ogr(ad=""), "zorunludur"),
    (ogr(no=""), "zorunludur"),
    (ogr(no="20A1002"), "rakam"),
    (ogr(no="1" * 16), "15 haneli"),
    (ogr(tel="055512345"), "10 haneli"),
    (ogr(tel="0555123456789"), "10 haneli"),
    (ogr(tel="15551234567"), "10 haneli"),
])
def test_ogrenci_bilgisi_dogrulama_kurallari(bilgi, beklenen):
    hata = ogrenci_bilgisi_dogrula(bilgi)
    if beklenen is None:
        assert hata is None
    else:
        assert hata is not None and beklenen in hata


def test_numara_ve_telefon_alanlarina_harf_yazilamaz_ve_uzunluk_sinirlidir(form):
    from PySide6.QtGui import QValidator
    for alan, sinir in ((form.input_ogrenci_no, 15), (form.input_telefon, 15)):
        assert alan.maxLength() == sinir
        assert alan.validator().validate("12a4", 4)[0] == QValidator.Invalid
        assert alan.validator().validate("1234", 4)[0] == QValidator.Acceptable
    # Telefonda gruplar arası boşluk yazılabilir, öğrenci numarasında yazılamaz.
    assert form.input_telefon.validator().validate("555 123", 7)[0] == QValidator.Acceptable
    assert form.input_ogrenci_no.validator().validate("555 123", 7)[0] == QValidator.Invalid


def test_yer_tutucularda_gercek_ogrenci_numarasi_gosterilmez(form):
    """Öğrenci numarası ve ad soyad yer tutucuları rakam içermemeli (kişisel numara görünmesin)."""
    for alan in (form.input_ogrenci_no, form.input_ad_soyad):
        assert not any(c.isdigit() for c in alan.placeholderText())


def test_gecersiz_telefonla_hesap_olusturulmaz(form):
    form.input_kullanici_adi.setText("ogr_yeni")
    rol_sec(form, 4)
    form.input_ad_soyad.setText("Veli Kaya")
    form.input_ogrenci_no.setText("2021002")
    form.input_telefon.setText("555 123")  # eksik hane
    with patch.object(modul.requests, "post") as post, patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    post.assert_not_called()
    assert "10 haneli" in uyari.call_args.args[2]


# -------------------------------------------------------------------- telefon
@pytest.mark.parametrize("yazilan, gorunen", [
    ("5", "(5"),
    ("555", "(555"),                        # kapanış parantezi sonraki rakamla gelir
    ("5551", "(555) 1"),
    ("555123", "(555) 123"),
    ("5551234", "(555) 123 4"),
    ("55512345", "(555) 123 45"),
    ("555123456", "(555) 123 45 6"),
    ("5551234567", "(555) 123 45 67"),
    ("555123456789", "(555) 123 45 67"),    # 10 haneden fazlası kesilir
    ("05551234567", "(555) 123 45 67"),     # başa 0 yazılırsa yok sayılır
    ("(555) 123 45 67", "(555) 123 45 67"), # zaten biçimli
    ("555 123 45 67", "(555) 123 45 67"),
    ("", ""),
    ("abc", ""),
])
def test_telefon_parantezli_gorunur(yazilan, gorunen):
    assert telefon_bicimle(yazilan) == gorunen


@pytest.mark.parametrize("yazilan, beklenen", [
    ("(555) 123 45 67", "05551234567"),     # başına 0 eklenir
    ("555 123 45 67", "05551234567"),
    ("5551234567", "05551234567"),
    ("0555 123 45 67", "05551234567"),
    ("05551234567", "05551234567"),
    ("(555) 123", "555123"),                # eksik: olduğu gibi kalır, doğrulamada reddedilir
    ("", ""),
])
def test_telefon_sunucuya_11_haneli_gider(yazilan, beklenen):
    assert telefon_normalle(yazilan) == beklenen


def test_telefon_alanina_yazarken_parantezli_gruplanir(form):
    from PySide6.QtTest import QTest
    QTest.keyClicks(form.input_telefon, "5551234567")
    assert form.input_telefon.text() == "(555) 123 45 67"


def test_telefon_alaninda_geri_silerken_bicime_takilmaz(form):
    """Parantez/boşluk silinirken imleç takılmamalı: her Backspace bir rakam siler."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    QTest.keyClicks(form.input_telefon, "5551234")
    assert form.input_telefon.text() == "(555) 123 4"
    beklenen = ["(555) 123", "(555) 12", "(555) 1", "(555", "(55", "(5", ""]
    for metin in beklenen:
        QTest.keyClick(form.input_telefon, Qt.Key_Backspace)
        assert form.input_telefon.text() == metin


def test_telefon_alani_yalnizca_rakam_bosluk_ve_parantez_kabul_eder(form):
    from PySide6.QtGui import QValidator
    dogrulayici = form.input_telefon.validator()
    assert dogrulayici.validate("(555) 123", 9)[0] == QValidator.Acceptable
    assert dogrulayici.validate("555a", 4)[0] == QValidator.Invalid
    assert dogrulayici.validate("555-123", 7)[0] == QValidator.Invalid


def test_telefon_basinda_0_olmadan_yazilan_numara_sunucuya_0li_gider(form):
    from PySide6.QtTest import QTest
    form.input_kullanici_adi.setText("ogr_yeni")
    rol_sec(form, 4)
    form.input_ad_soyad.setText("Veli Kaya")
    form.input_ogrenci_no.setText("2021002")
    QTest.keyClicks(form.input_telefon, "5551234567")
    with patch.object(modul.requests, "post",
                      return_value=cevap(201, {"kullanici_id": 40, "gecici_parola": "Pw"})):
        form.kaydet()
    atamalar = []
    with patch.object(modul.requests, "get", return_value=cevap(200, [])), \
            patch.object(modul.requests, "post",
                         side_effect=lambda u, **k: (atamalar.append(k["json"]), cevap(201))[1]), \
            patch.object(QMessageBox, "information"):
        form.personel_ata_tiklandi()
    assert atamalar[0]["telefon"] == "05551234567"


# ----------------------------------------------------- kullanıcı adı önerisi
@pytest.mark.parametrize("ad, beklenen", [
    ("Veli Kaya", "veli.kaya"),
    ("Şule Çağlar Öztürk", "sule.caglar.ozturk"),
    ("İpek Ğümüş", "ipek.gumus"),
    ("  Ali   Veli  ", "ali.veli"),
    ("Ayşe-Nur D'Arc", "ayse.nur.d.arc"),
    ("", ""),
])
def test_kullanici_adi_oner(ad, beklenen):
    assert kullanici_adi_oner(ad) == beklenen


def test_danisma_ogrencisinde_kullanici_adi_ad_soyaddan_otomatik_dolar(form):
    """Sunucu doğrulayana kadar alan boş bekler; doğrulayınca (ulaşılamazsa yerel öneriyle) dolar."""
    rol_sec(form, 4)
    form.input_ad_soyad.setText("Şule Çağlar")
    assert form.input_kullanici_adi.text() == "" and form._netlestirme_zamanlayici.isActive()
    form._kullanici_adini_netlestir()
    assert form.input_kullanici_adi.text() == "sule.caglar"
    form.input_ad_soyad.setText("Şule Çağlar Öztürk")
    form._kullanici_adini_netlestir()
    assert form.input_kullanici_adi.text() == "sule.caglar.ozturk"


def test_kullanici_adi_elle_degistirilirse_otomatik_yazim_durur(form):
    rol_sec(form, 4)
    form.input_ad_soyad.setText("Veli Kaya")
    form.input_kullanici_adi.textEdited.emit("veli_k")  # kullanıcı elle yazdı
    form.input_kullanici_adi.setText("veli_k")
    form.input_ad_soyad.setText("Veli Kaya Demir")
    assert form.input_kullanici_adi.text() == "veli_k"


def test_diger_rollerde_kullanici_adi_otomatik_dolmaz(form):
    rol_sec(form, 1)
    form.input_ad_soyad.setText("Veli Kaya")
    assert form.input_kullanici_adi.text() == ""


def test_alan_sirasi_rol_ogrenci_bilgileri_sonra_kullanici_adi(form):
    """Kullanıcı adı, ad soyaddan türediği için en altta (düğmelerin hemen üstünde) durur."""
    duzen = form.layout()
    sira = lambda parca: duzen.indexOf(parca)
    assert sira(form.combo_rol) < sira(form.ogrenci_kutusu) < sira(form.input_kullanici_adi)
    assert sira(form.input_kullanici_adi) < sira(form.sonuc_kutusu)


# ------------------------------------------------ boş kullanıcı adı (çakışma önleme)
def test_ad_soyad_bitince_sunucudan_bos_kullanici_adi_alinir(form):
    rol_sec(form, 4)
    form.input_ad_soyad.setText("Cihangir Kaplan")
    assert form.input_kullanici_adi.text() == ""                     # doğrulanana kadar boş
    cagrilar = []

    def get(url, **kwargs):
        cagrilar.append((url, kwargs["params"]))
        return cevap(200, {"kullanici_adi": "cihangir.kaplan2"})

    with patch.object(modul.requests, "get", side_effect=get):
        form.input_ad_soyad.editingFinished.emit()
    assert form.input_kullanici_adi.text() == "cihangir.kaplan2"
    assert cagrilar == [("http://testserver/api/kullanicilar/musait-kullanici-adi", {"temel": "cihangir.kaplan"})]


def test_elle_yazilan_kullanici_adi_icin_sunucuya_sorulmaz(form):
    rol_sec(form, 4)
    form.input_kullanici_adi.textEdited.emit("ozel_ad")
    form.input_kullanici_adi.setText("ozel_ad")
    form.input_ad_soyad.setText("Cihangir Kaplan")
    with patch.object(modul.requests, "get") as get:
        form.input_ad_soyad.editingFinished.emit()
    get.assert_not_called()
    assert form.input_kullanici_adi.text() == "ozel_ad"


def test_sunucuya_ulasilamazsa_yerel_oneri_kalir():
    assert musait_kullanici_adi("http://x", "t", "cihangir.kaplan") == "cihangir.kaplan"
    assert musait_kullanici_adi("http://x", "t", "") == ""


def hazirla_danisma(form, ad="Cihangir Kaplan"):
    rol_sec(form, 4)
    form.input_ad_soyad.setText(ad)
    form.input_ogrenci_no.setText("2021002")


def test_olusturmadan_once_kullanici_adi_son_kez_dogrulanir(form):
    hazirla_danisma(form)
    gonderilen = []

    def post(url, **kwargs):
        gonderilen.append(kwargs["json"])
        return cevap(201, {"kullanici_id": 50, "gecici_parola": "Pw"})

    with patch.object(modul.requests, "get", return_value=cevap(200, {"kullanici_adi": "cihangir.kaplan3"})), \
            patch.object(modul.requests, "post", side_effect=post):
        form.kaydet()
    assert gonderilen == [{"kullanici_adi": "cihangir.kaplan3", "rol_id": 4}]
    assert form.input_kullanici_adi.text() == "cihangir.kaplan3"


def test_olusturma_sirasinda_ad_alinirsa_bir_kez_yeniden_denenir(form):
    hazirla_danisma(form)
    yanitlar = [cevap(409), cevap(201, {"kullanici_id": 51, "gecici_parola": "Pw"})]
    gonderilen = []
    oneriler = iter(["cihangir.kaplan", "cihangir.kaplan2"])

    def post(url, **kwargs):
        gonderilen.append(kwargs["json"]["kullanici_adi"])
        return yanitlar.pop(0)

    with patch.object(modul.requests, "get",
                      side_effect=lambda *a, **k: cevap(200, {"kullanici_adi": next(oneriler)})), \
            patch.object(modul.requests, "post", side_effect=post):
        form.kaydet()
    assert gonderilen == ["cihangir.kaplan", "cihangir.kaplan2"]
    assert form.olusturulan_kullanici["kullanici_adi"] == "cihangir.kaplan2"


def test_elle_yazilan_ad_409_alirsa_yeniden_denenmez_uyari_verir(form):
    hazirla_danisma(form)
    form.input_kullanici_adi.textEdited.emit("var_olan")
    form.input_kullanici_adi.setText("var_olan")
    with patch.object(modul.requests, "post", return_value=cevap(409)) as post, \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    assert post.call_count == 1
    uyari.assert_called_once()
    assert form.btn_kaydet.isEnabled()


def test_diger_rollerde_kullanici_adi_icin_sunucuya_sorulmaz(form):
    form.input_kullanici_adi.setText("memur_yeni")
    rol_sec(form, 2)
    with patch.object(modul.requests, "get") as get, \
            patch.object(modul.requests, "post",
                         return_value=cevap(201, {"kullanici_id": 52, "gecici_parola": "Pw"})):
        form.kaydet()
    get.assert_not_called()


# ------------------------------------------------ merkezi oturum yönetimi (token süresi dolması)
def oturum_bitti_yaniti():
    r = cevap(401, {"detail": "Token süresi dolmuş."})
    r._tkys_oturum_reddedildi = True  # merkezi sistemin işaretlediği yanıt
    return r


def test_personel_ata_oturum_bittiyse_none_doner(form):
    with patch.object(modul.requests, "post", return_value=oturum_bitti_yaniti()):
        assert personel_ata("http://x", "t", 8, "PER-OGR-001", None) == (None, "")


def test_hesap_olustururken_oturum_biterse_form_degismez_ve_uyari_cikmaz(form):
    form.input_kullanici_adi.setText("doktor_z")
    rol_sec(form, 1)
    with patch.object(modul.requests, "post", return_value=oturum_bitti_yaniti()), \
            patch.object(QMessageBox, "warning") as uyari, patch.object(QMessageBox, "critical") as hata:
        form.kaydet()
    uyari.assert_not_called()
    hata.assert_not_called()
    assert form.olusturulan_kullanici is None and form.btn_kaydet.isEnabled()


def test_personel_atarken_oturum_biterse_pencere_acik_kalir_ve_uyari_cikmaz(form):
    form.input_kullanici_adi.setText("doktor_w")
    rol_sec(form, 1)
    with patch.object(modul.requests, "post",
                      return_value=cevap(201, {"kullanici_id": 60, "gecici_parola": "Pw"})):
        form.kaydet()
    with patch.object(modul.requests, "get", return_value=cevap(200, [])), \
            patch.object(modul.requests, "post", return_value=oturum_bitti_yaniti()), \
            patch.object(QMessageBox, "warning") as uyari, patch.object(QMessageBox, "information") as bilgi:
        form.personel_ata_tiklandi()
    uyari.assert_not_called()
    bilgi.assert_not_called()
    assert not form.personel_atandi


def test_bos_kullanici_adi_sorgusunda_oturum_biterse_yerel_oneri_kalir():
    with patch.object(modul.requests, "get", return_value=oturum_bitti_yaniti()):
        assert musait_kullanici_adi("http://x", "t", "cihangir.kaplan") == "cihangir.kaplan"


def test_dolu_kullanici_adi_yazarken_hic_gosterilmez(form):
    """Ad soyad harf harf yazılırken alan boş kalır; sunucu 'cihangir.kaplan dolu' dedikten sonra
    yalnızca boş olan ad ('cihangir.kaplan2') görünür. 'cihangir.kaplan' bir an bile görünmez."""
    rol_sec(form, 4)
    gorunenler = []
    form.input_kullanici_adi.textChanged.connect(gorunenler.append)
    for uzunluk in range(1, len("Cihangir Kaplan") + 1):
        form.input_ad_soyad.setText("Cihangir Kaplan"[:uzunluk])
    with patch.object(modul.requests, "get", return_value=cevap(200, {"kullanici_adi": "cihangir.kaplan2"})):
        form._kullanici_adini_netlestir()
    assert "cihangir.kaplan" not in gorunenler
    assert form.input_kullanici_adi.text() == "cihangir.kaplan2"


def test_kontrol_zamanlayicisi_ad_yazildikca_yeniden_baslar_ve_bitince_sorar(form):
    rol_sec(form, 4)
    sorgular = []

    def get(url, **kwargs):
        sorgular.append(kwargs["params"]["temel"])
        return cevap(200, {"kullanici_adi": kwargs["params"]["temel"]})

    with patch.object(modul.requests, "get", side_effect=get):
        form.input_ad_soyad.setText("Cihangir")
        form.input_ad_soyad.setText("Cihangir Kaplan")
        assert form._netlestirme_zamanlayici.isActive() and sorgular == []   # henüz sorulmadı
        form._netlestirme_zamanlayici.timeout.emit()                          # bekleme doldu
        assert sorgular == ["cihangir.kaplan"]
        form.input_ad_soyad.editingFinished.emit()                            # alandan çıkış: aynı ad tekrar sorulmaz
        assert sorgular == ["cihangir.kaplan"]
    assert form.input_kullanici_adi.text() == "cihangir.kaplan"


def test_olustur_hemen_basilirsa_bos_kullanici_adi_uyarisi_cikmaz_ad_turetilir(form):
    """Kullanıcı ad soyadı yazıp bekleme dolmadan 'Oluştur'a basarsa ad kendiliğinden türetilir."""
    hazirla_danisma(form)
    assert form.input_kullanici_adi.text() == ""
    gonderilen = []
    with patch.object(modul.requests, "get", return_value=cevap(200, {"kullanici_adi": "cihangir.kaplan2"})), \
            patch.object(modul.requests, "post",
                         side_effect=lambda u, **k: (gonderilen.append(k["json"]),
                                                     cevap(201, {"kullanici_id": 70, "gecici_parola": "Pw"}))[1]), \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()
    uyari.assert_not_called()
    assert gonderilen == [{"kullanici_adi": "cihangir.kaplan2", "rol_id": 4}]
    assert not form._netlestirme_zamanlayici.isActive()
