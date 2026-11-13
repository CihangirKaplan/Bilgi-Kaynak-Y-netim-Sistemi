"""Parola sıfırlama talebi arayüzü: giriş penceresi, yöneticinin talepler paneli, zil ve ana panel bildirimi.

Gerçek sunucu kullanılmaz; ağ istekleri taklit edilir.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

import parola_talebi_dialog as modul
from dashboard_ekrani import DashboardEkrani
from k_personel_ekranlari import KullaniciPersonelEkrani
from parola_talebi_dialog import ParolaTalebiDialog


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def yanit(durum, veri=None):
    r = MagicMock()
    r.status_code = durum
    r.json.return_value = veri if veri is not None else {}
    return r


def kapat(p):
    p.close()
    p.deleteLater()


# ================================================================ giriş penceresi
def pencere(qt_app, ad="psikolog1"):
    return ParolaTalebiDialog("http://s", ad)


def gonder(p, sonuc=None, **kw):
    with patch.object(modul.requests, "post", **({"return_value": sonuc} if sonuc is not None else kw)) as post:
        p.talep_gonder()
    return post


def test_giriste_yazilan_kullanici_adi_hazir_gelir_ve_ilk_durum_dogrudur(qt_app):
    p = pencere(qt_app)
    assert p.txt_kullanici.text() == "psikolog1" and p.btn_gonder.text() == "Yöneticiye Bildir"
    assert p.lbl_baslik.text() == "Şifrenizi mi unuttunuz?" and p.lbl_hata.isHidden() and p.kutu_basari.isHidden()
    assert "yüz yüze" in p.lbl_not.text()
    kapat(p)


def test_bos_kullanici_adiyla_istek_gonderilmez(qt_app):
    p = pencere(qt_app, "   ")
    post = gonder(p, yanit(200))
    post.assert_not_called()
    assert not p.lbl_hata.isHidden() and "kullanıcı adınızı yazın" in p.lbl_hata.text()
    kapat(p)


def test_basarili_talep_dogru_adrese_bosluklari_atilmis_adla_gider_ve_basari_gorunur(qt_app):
    p = pencere(qt_app, "  psikolog1 ")
    post = gonder(p, yanit(200, {"mesaj": "Talebiniz alındı."}))
    post.assert_called_once_with("http://s/api/parola-sifirlama-talebi", json={"kullanici_adi": "psikolog1"},
                                 timeout=modul.ZAMAN_ASIMI_SANIYE)
    assert p.talep_gonderildi and not p.kutu_basari.isHidden() and "Talebiniz alındı." in p.lbl_basari.text()
    assert p.lbl_baslik.text() == "Talebiniz iletildi" and p.btn_vazgec.text() == "Kapat"
    assert p.btn_gonder.isHidden() and p.txt_kullanici.isHidden() and p.adimlar.isHidden()
    kapat(p)


def test_talep_gonderildikten_sonra_tekrar_gonderilmez(qt_app):
    p = pencere(qt_app)
    gonder(p, yanit(200))
    ikinci = gonder(p, yanit(200))
    ikinci.assert_not_called()
    kapat(p)


def test_enter_tusu_talebi_gonderir(qt_app):
    p = pencere(qt_app)
    with patch.object(modul.requests, "post", return_value=yanit(200)) as post:
        p.txt_kullanici.returnPressed.emit()
    post.assert_called_once()
    kapat(p)


@pytest.mark.parametrize("durum,parca", [(429, "çok fazla bekleyen talep"), (422, "geçersiz"),
                                          (500, "gönderilemedi"), (404, "gönderilemedi")])
def test_sunucu_hatalari_anlasilir_mesajla_gosterilir_ve_form_acik_kalir(qt_app, durum, parca):
    p = pencere(qt_app)
    gonder(p, yanit(durum))
    assert parca in p.lbl_hata.text() and not p.talep_gonderildi
    assert p.btn_gonder.isEnabled() and p.btn_gonder.text() == "Yöneticiye Bildir" and not p.txt_kullanici.isHidden()
    kapat(p)


def hata_yaniti(durum, kod, mesaj):
    return yanit(durum, {"detail": {"kod": kod, "mesaj": mesaj}})


@pytest.mark.parametrize("durum,kod,mesaj", [
    (404, "KULLANICI_BULUNAMADI", "Bu kullanıcı adıyla kayıtlı bir hesap bulunamadı. Yazımı kontrol edip tekrar deneyin."),
    (403, "HESAP_PASIF", "Bu hesap pasif. Lütfen yöneticinize başvurun."),
])
def test_var_olmayan_ya_da_pasif_hesapta_sunucu_mesaji_aynen_gosterilir_ve_form_acik_kalir(qt_app, durum, kod, mesaj):
    p = pencere(qt_app, "yanlis_ad")
    gonder(p, hata_yaniti(durum, kod, mesaj))
    assert not p.lbl_hata.isHidden() and mesaj in p.lbl_hata.text()
    assert not p.talep_gonderildi and p.kutu_basari.isHidden()
    assert p.btn_gonder.isEnabled() and p.btn_gonder.text() == "Yöneticiye Bildir" and not p.txt_kullanici.isHidden()
    kapat(p)


@pytest.mark.parametrize("durum,veri", [
    (404, {"detail": "Not Found"}),                                              # eski sunucu / yanlış adres
    (404, {"detail": {"kod": "BASKA_KOD", "mesaj": "x"}}),
    (403, {"detail": {"mesaj": "kodsuz"}}),
    (404, {"detail": ["liste"]}),
])
def test_tanimadigi_404_ve_403_yanitlari_icin_genel_hata_mesaji_gosterilir(qt_app, durum, veri):
    p = pencere(qt_app)
    gonder(p, yanit(durum, veri))
    assert "gönderilemedi" in p.lbl_hata.text() and not p.talep_gonderildi
    kapat(p)


def test_gecersiz_json_ile_gelen_404_genel_mesaj_gosterir(qt_app):
    p = pencere(qt_app)
    sonuc = yanit(404)
    sonuc.json.side_effect = ValueError("json degil")
    gonder(p, sonuc)
    assert "gönderilemedi" in p.lbl_hata.text()
    kapat(p)


def test_zaten_bekleyen_talepte_sunucu_mesaji_basari_olarak_gosterilir(qt_app):
    p = pencere(qt_app)
    gonder(p, yanit(200, {"durum": "zaten_var", "mesaj": "Bu hesap için zaten bekleyen bir talebiniz var. Yöneticinizin size dönmesini bekleyin."}))
    assert p.talep_gonderildi and "zaten bekleyen bir talebiniz var" in p.lbl_basari.text()
    kapat(p)


@pytest.mark.parametrize("hata,parca", [(requests.exceptions.ConnectionError(), "bağlanılamadı"),
                                         (requests.exceptions.Timeout(), "yanıt vermedi")])
def test_ag_hatalarinda_yoneticiye_dogrudan_ulasmasi_soylenir(qt_app, hata, parca):
    p = pencere(qt_app)
    gonder(p, side_effect=hata)
    assert parca in p.lbl_hata.text() and "yöneticinize doğrudan ulaşın" in p.lbl_hata.text()
    assert p.btn_gonder.isEnabled() and not p.talep_gonderildi
    kapat(p)


def test_hata_sonrasi_tekrar_denenince_hata_mesaji_temizlenir(qt_app):
    p = pencere(qt_app)
    gonder(p, side_effect=requests.exceptions.ConnectionError())
    assert not p.lbl_hata.isHidden()
    gonder(p, yanit(200))
    assert p.lbl_hata.isHidden() and p.talep_gonderildi
    kapat(p)


def test_gecersiz_json_yanitinda_varsayilan_basari_mesaji_kullanilir(qt_app):
    p = pencere(qt_app)
    r = yanit(200)
    r.json.side_effect = ValueError
    gonder(p, r)
    assert "iletildi" in p.lbl_basari.text()
    kapat(p)


def test_girisdeki_sifremi_unuttum_dugmesi_talep_penceresini_yazilan_adla_acar():
    import login_ekrani                      # ağır içe aktarma: yalnızca bu testte
    sahte = SimpleNamespace(kullanici_input=SimpleNamespace(text=lambda: "  memur  "))
    with patch.object(login_ekrani, "ParolaTalebiDialog") as dialog:
        login_ekrani.LoginEkrani.sifremi_unuttum_bilgisi(sahte)
    dialog.assert_called_once_with(login_ekrani.API_URL, "memur", sahte)
    dialog.return_value.exec.assert_called_once()


# ============================================================ yöneticinin talepler paneli
TALEPLER = [
    {"talep_id": 5, "kullanici_id": 12, "kullanici_adi": "psikolog1", "rol_adi": "PSIKOLOG", "bekleme_dakika": 5},
    {"talep_id": 6, "kullanici_id": 13, "kullanici_adi": "memur", "rol_adi": "MEMUR", "bekleme_dakika": 130},
]


def personel_ekrani(qt_app, talep_yaniti):
    def istek(yontem, adres, **kw):
        if adres.endswith("/api/parola-sifirlama-talepleri"):
            return talep_yaniti
        return yanit(200, [])
    with patch("k_personel_ekranlari.oturum_kontrollu_istek", side_effect=istek), \
         patch("k_personel_ekranlari.oturum_hatasi_mi", return_value=False):
        return KullaniciPersonelEkrani("http://s", "T")


def paneldeki_dugmeler(e, ad):
    return [d for d in e.talep_paneli.findChildren(QPushButton) if d.objectName() == ad]


def test_talep_yoksa_panel_gizlidir(qt_app):
    e = personel_ekrani(qt_app, yanit(200, []))
    assert e.talep_paneli.isHidden()
    kapat(e)


@pytest.mark.parametrize("durum", [403, 401, 500])
def test_yetki_yoksa_ya_da_hata_varsa_panel_gizli_kalir(qt_app, durum):
    e = personel_ekrani(qt_app, yanit(durum, {"detail": "x"}))
    assert e.talep_paneli.isHidden()
    kapat(e)


def test_ag_hatasinda_ekran_cokmez_ve_panel_gizli_kalir(qt_app):
    with patch("k_personel_ekranlari.oturum_kontrollu_istek", side_effect=requests.exceptions.ConnectionError()):
        e = KullaniciPersonelEkrani("http://s", "T")
    assert e.talep_paneli.isHidden()
    kapat(e)


def test_bekleyen_talepler_baslik_ve_satirlarla_gorunur(qt_app):
    e = personel_ekrani(qt_app, yanit(200, TALEPLER))
    assert not e.talep_paneli.isHidden()
    yazilar = [l.text() for l in e.talep_paneli.findChildren(QLabel)]
    assert any("Parola sıfırlama talepleri  (2)" in y for y in yazilar)
    assert any("psikolog1" in y and "PSIKOLOG" in y and "5 dk önce" in y for y in yazilar)
    assert any("memur" in y and "2 saat önce" in y for y in yazilar)
    assert len(paneldeki_dugmeler(e, "talepSifirla")) == 2 and len(paneldeki_dugmeler(e, "talepKapat")) == 2
    kapat(e)


def test_bozuk_kayitlar_atlanir_gecerli_olanlar_gorunur(qt_app):
    bozuk = [{"kullanici_adi": "x"}, "metin", None, TALEPLER[0]]
    e = personel_ekrani(qt_app, yanit(200, bozuk))
    assert len(paneldeki_dugmeler(e, "talepSifirla")) == 1
    kapat(e)


def test_hepsi_bozuksa_ya_da_liste_degilse_panel_gizli(qt_app):
    assert personel_ekrani(qt_app, yanit(200, [{"x": 1}])).talep_paneli.isHidden()
    assert personel_ekrani(qt_app, yanit(200, {"detail": "beklenmeyen"})).talep_paneli.isHidden()


def test_parola_sifirla_dugmesi_ilgili_kullanicinin_sifirlama_akisini_baslatir(qt_app):
    e = personel_ekrani(qt_app, yanit(200, TALEPLER))
    with patch.object(e, "parola_sifirla") as sifirla:
        paneldeki_dugmeler(e, "talepSifirla")[1].click()
    sifirla.assert_called_once_with(13, "memur")
    kapat(e)


@pytest.mark.parametrize("dakika,beklenen", [(0, "az önce"), (None, "az önce"), (-3, "az önce"), (1, "1 dk önce"),
                                              (59, "59 dk önce"), (60, "1 saat önce"), (130, "2 saat önce"),
                                              (1439, "23 saat önce"), (1440, "1 gün önce"), (4400, "3 gün önce")])
def test_bekleme_metni(dakika, beklenen):
    assert KullaniciPersonelEkrani.bekleme_metni(dakika) == beklenen


def kapat_istek(e, onay, cevap=None, hata=None):
    cagrilar = []
    def istek(yontem, adres, **kw):
        cagrilar.append((yontem, adres))
        if hata:
            raise hata
        return cevap if cevap is not None and yontem == "PATCH" else yanit(200, [])
    with patch("k_personel_ekranlari.oturum_kontrollu_istek", side_effect=istek), \
         patch("k_personel_ekranlari.oturum_hatasi_mi", return_value=False), \
         patch("k_personel_ekranlari.QMessageBox.question", return_value=onay), \
         patch("k_personel_ekranlari.QMessageBox.warning") as uyari, patch("k_personel_ekranlari.QMessageBox.critical") as kritik:
        paneldeki_dugmeler(e, "talepKapat")[0].click()
    return cagrilar, uyari, kritik


def test_talebi_kapat_onaylaninca_dogru_adrese_patch_atar_ve_paneli_tazeler(qt_app):
    e = personel_ekrani(qt_app, yanit(200, TALEPLER))
    cagrilar, uyari, _ = kapat_istek(e, QMessageBox.Yes, yanit(200, {"durum": "basarili"}))
    assert cagrilar[0] == ("PATCH", "http://s/api/parola-sifirlama-talepleri/5/kapat")
    assert cagrilar[1] == ("GET", "http://s/api/parola-sifirlama-talepleri")          # panel yeniden yüklendi
    assert e.talep_paneli.isHidden() and not uyari.called                              # sahte yanıtta liste boş döndü
    kapat(e)


def test_talebi_kapat_onaylanmazsa_istek_atilmaz(qt_app):
    e = personel_ekrani(qt_app, yanit(200, TALEPLER))
    cagrilar, _, _ = kapat_istek(e, QMessageBox.No)
    assert cagrilar == [] and not e.talep_paneli.isHidden()
    kapat(e)


def test_talebi_kapat_basarisizsa_sunucu_mesaji_gosterilir(qt_app):
    e = personel_ekrani(qt_app, yanit(200, TALEPLER))
    _, uyari, _ = kapat_istek(e, QMessageBox.Yes, yanit(404, {"detail": "Bekleyen talep bulunamadı."}))
    assert uyari.call_args.args[2] == "Bekleyen talep bulunamadı."
    kapat(e)


def test_talebi_kapat_ag_hatasinda_baglanti_uyarisi_verir(qt_app):
    e = personel_ekrani(qt_app, yanit(200, TALEPLER))
    _, _, kritik = kapat_istek(e, QMessageBox.Yes, hata=requests.exceptions.ConnectionError())
    kritik.assert_called_once()
    kapat(e)


# ================================================================== ana pencere ve zil
@pytest.fixture
def temiz_yetkiler():
    import main_window as mw
    mw._SUNUCU_YETKILERI.clear()
    yield mw
    mw._SUNUCU_YETKILERI.clear()


def gorebilir(mw, rol):
    sahte = SimpleNamespace(aktif_rol=rol)
    sahte._sayfa_izinli_mi = lambda sayfa: mw.AnaPencere._sayfa_izinli_mi(sahte, sayfa)
    return mw.AnaPencere._parola_talepleri_gorebilir_mi(sahte)


def test_talepleri_yalniz_sifirlama_izni_ve_sayfasi_olan_rol_gorur(temiz_yetkiler):
    mw = temiz_yetkiler
    assert {rol for rol in mw.ROLLER if gorebilir(mw, rol)} == {"admin"}                       # eski tablo: yalnızca Admin
    mw.yetkileri_ayarla("mudur", ["KULLANICI_OLUSTUR", "KULLANICI_PAROLA_SIFIRLA"])
    assert gorebilir(mw, "mudur")                                                               # izin verilirse müdür de görür
    mw.yetkileri_ayarla("memur", ["KULLANICI_PAROLA_SIFIRLA"])
    assert not gorebilir(mw, "memur")                                                           # sayfaya (Kullanıcı & Personel) yetkisi yok
    mw.yetkileri_ayarla("admin", ["KULLANICI_OLUSTUR"])
    assert not gorebilir(mw, "admin")                                                           # sıfırlama izni yok


def zil(mw, talep_yaniti, gorebilir_mi=True):
    def istek(yontem, url, **kw):
        r = MagicMock()
        r._tkys_oturum_reddedildi = False
        r.status_code = talep_yaniti[0] if url.endswith("/parola-sifirlama-talepleri") else 200
        r.json.return_value = talep_yaniti[1] if url.endswith("/parola-sifirlama-talepleri") else []
        return r
    ana = MagicMock()
    ana._oturum_kapatiliyor = False
    ana.api_url, ana.token = "http://x", "T"
    ana.nav_btnler = {}
    ana._parola_talepleri_gorebilir_mi = lambda: gorebilir_mi
    ana._bekleme_metni = mw.AnaPencere._bekleme_metni
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=istek):
        mw.AnaPencere._bildirimleri_yenile(ana)
    return ana


def test_zilde_her_talep_kullanici_ve_bekleme_suresiyle_listelenir_ve_sayfaya_gider(temiz_yetkiler):
    ana = zil(temiz_yetkiler, (200, TALEPLER))
    assert ana._bildirimler == [
        ("Parola Talepleri", "🔐 psikolog1 parola sıfırlama istedi (5 dk önce)", "Kullanıcı & Personel"),
        ("Parola Talepleri", "🔐 memur parola sıfırlama istedi (2 saat önce)", "Kullanıcı & Personel")]
    assert ana._bildirim_sayisi == 2


def test_yetkisiz_kullanicinin_zilinde_talep_yoktur_ve_sunucuya_sorulmaz(temiz_yetkiler):
    mw = temiz_yetkiler
    istekler = []
    def istek(yontem, url, **kw):
        istekler.append(url)
        r = MagicMock(); r.status_code = 200; r._tkys_oturum_reddedildi = False; r.json.return_value = TALEPLER
        return r
    ana = MagicMock()
    ana._oturum_kapatiliyor = False; ana.api_url, ana.token = "http://x", "T"; ana.nav_btnler = {}
    ana._parola_talepleri_gorebilir_mi = lambda: False
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=istek):
        mw.AnaPencere._bildirimleri_yenile(ana)
    assert ana._bildirimler == [] and not any("parola-sifirlama" in u for u in istekler)


def test_zilde_403_ya_da_bozuk_yanit_bildirim_uretmez(temiz_yetkiler):
    assert zil(temiz_yetkiler, (403, {"detail": "yok"}))._bildirimler == []
    assert zil(temiz_yetkiler, (200, {"beklenmeyen": 1}))._bildirimler == []


def test_bildirim_panelinde_parola_talepleri_kendi_basligi_altinda_gorunur(qt_app):
    from bildirim_paneli import BildirimPaneli
    acilan = []
    panel = BildirimPaneli([("Parola Talepleri", "🔐 memur parola sıfırlama istedi (az önce)", "Kullanıcı & Personel")],
                           1, False, acilan.append)
    assert any("PAROLA SIFIRLAMA TALEPLERİ" in l.text() for l in panel.findChildren(QLabel))
    [b for b in panel.findChildren(QPushButton) if b.objectName() == "bildirimSatiri"][0].click()
    assert acilan == ["Kullanıcı & Personel"]
    panel.deleteLater()


# ============================================================= ana paneldeki bildirim kutusu
def pano(qt_app, talepler=TALEPLER, goster=True, **kw):
    istekler = []
    def getir(yol):
        istekler.append(yol)
        if yol == "/api/parola-sifirlama-talepleri":
            if isinstance(talepler, Exception):
                raise talepler
            return talepler
        return {"/api/dashboard/ozet": {"acik_ariza_sayisi": 0}}.get(yol, [])
    with patch.object(DashboardEkrani, "_getir", side_effect=getir):
        p = DashboardEkrani("http://x", "T", cihaz_ozeti=True, parola_talepleri_goster=goster, **kw)
    p.zamanlayici.stop()
    p.istekler = istekler
    return p


def satirlar(p):
    return [d.text() for d in p.bildirim_paneli.findChildren(QPushButton)]


def test_ana_panelde_talepler_tiklanabilir_bildirim_olarak_en_ustte_gorunur(qt_app):
    acilan = []
    p = pano(qt_app, sayfa_ac=acilan.append)
    assert satirlar(p)[0].startswith("🔐  psikolog1 parola sıfırlama istedi (5 dk önce)")
    assert satirlar(p)[1].startswith("🔐  memur parola sıfırlama istedi (2 saat önce)")
    for d in p.bildirim_paneli.findChildren(QPushButton):
        d.click()
    assert acilan == ["Kullanıcı & Personel", "Kullanıcı & Personel"]
    kapat(p)


def test_yetkisiz_olunan_durumda_talep_istenmez_ve_gosterilmez(qt_app):
    p = pano(qt_app, goster=False)
    assert "/api/parola-sifirlama-talepleri" not in p.istekler and not any("parola" in s for s in satirlar(p))
    kapat(p)


def test_kullanici_sayfasina_yetki_yoksa_talep_gosterilmez(qt_app):
    p = pano(qt_app, sayfa_ac=lambda s: None, sayfa_izinli_mi=lambda s: s != "Kullanıcı & Personel")
    assert not any("parola" in s for s in satirlar(p))
    kapat(p)


def test_talep_yuklenemezse_ana_panel_cokmez(qt_app):
    p = pano(qt_app, talepler=requests.exceptions.ConnectionError("kapalı"))
    assert p.parola_talepleri == [] and not any("parola" in s for s in satirlar(p))
    kapat(p)


def test_talep_listesi_beklenmeyen_bicimdeyse_bos_sayilir(qt_app):
    p = pano(qt_app, talepler={"detail": "x"})
    assert p.parola_talepleri == []
    kapat(p)


def test_yonetici_hesabi_icin_sunucu_bilgisayarina_yonlendirme_notu_var():
    p = ParolaTalebiDialog("http://x", "")
    assert "sunucu bilgisayarından" in p.lbl_not.text() and "yüz yüze" in p.lbl_not.text()
