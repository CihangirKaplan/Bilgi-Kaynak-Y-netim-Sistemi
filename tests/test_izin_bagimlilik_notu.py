"""Rol & İzin Yönetimi: tek başına sekme açmayan izinler için uyarı notu.

Notlar menü tanımından otomatik üretilir; bu testler hem üretim mantığını hem de İzin Düzenle penceresi ile
matristeki görünümü doğrular. Gerçek sunucu kullanılmaz.
"""
import pytest
from PySide6.QtWidgets import QApplication

import izin_bagimliliklari as ib
import main_window as mw
import rol_izin_diyaloglari as rid
import sayfalar_rol_izin as sri


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


# ================================================================ üretim mantığı (sahte menü)
MENU = [
    ("BÖLÜM", [
        dict(ad="Ana Panel", izin=None, aksiyon=[]),
        dict(ad="Kullanıcılar", izin="Kullanıcı oluşturma",
             aksiyon=[("Oluştur", "Kullanıcı oluşturma"), ("Pasifleştir", "Kullanıcı pasifleştirme")]),
        dict(ad="Odalar", izin="Oda yönetimi", aksiyon=[]),
        dict(ad="Raporlar", izin="Rapor izni", aksiyon=[("Dışa aktar", "Aktarma izni")]),
        dict(ad="Arşiv", izin="Arşiv izni", aksiyon=[("Dışa aktar", "Aktarma izni")]),
    ]),
]
KODLAR = {
    "Kullanıcı oluşturma": ("K_OLUSTUR",), "Kullanıcı pasifleştirme": ("K_PASIF",), "Oda yönetimi": ("ODA_EKLE", "ODA_DUZENLE"),
    "Rapor izni": ("RAPOR",), "Arşiv izni": ("ARSIV",), "Aktarma izni": ("AKTAR",),
}


def test_sayfanin_kendi_izni_not_almaz_dugme_izni_not_alir():
    notlar = ib.bagimlilik_notlari(MENU, KODLAR)
    assert "K_OLUSTUR" not in notlar and "RAPOR" not in notlar and "ARSIV" not in notlar
    assert "K_PASIF" in notlar


def test_dugme_izni_notu_sayfayi_ve_gereken_izni_soyler():
    not_ = ib.bagimlilik_notlari(MENU, KODLAR)["K_PASIF"]
    assert "tek başına yeni bir sekme açmaz" in not_ and "'Kullanıcılar'" in not_ and "'Kullanıcı oluşturma'" in not_


def test_birden_cok_izin_isteyen_sayfada_her_izin_digerini_anar():
    notlar = ib.bagimlilik_notlari(MENU, KODLAR)
    assert "ODA_DUZENLE" in notlar["ODA_EKLE"] and "ODA_EKLE" in notlar["ODA_DUZENLE"]
    assert "'Odalar'" in notlar["ODA_EKLE"] and "birlikte" in notlar["ODA_EKLE"]


def test_ayni_izin_iki_sayfanin_dugmesiyse_ikisi_de_yazilir_ve_gerekenler_listelenir():
    not_ = ib.bagimlilik_notlari(MENU, KODLAR)["AKTAR"]
    assert "'Raporlar' ve 'Arşiv'" in not_ and "'Rapor izni' ve 'Arşiv izni'" in not_


def test_baska_bir_sayfayi_tek_basina_acan_izin_dugme_olsa_da_not_almaz():
    menu = [("B", [dict(ad="A", izin="X izni", aksiyon=[]), dict(ad="B", izin="Y izni", aksiyon=[("d", "X izni")])])]
    assert "X" not in ib.bagimlilik_notlari(menu, {"X izni": ("X",), "Y izni": ("Y",)})


def test_etiketler_verilirse_notlarda_matristeki_gorunen_adlar_kullanilir():
    notlar = ib.bagimlilik_notlari(MENU, KODLAR, {"K_OLUSTUR": "Yeni kullanıcı kaydı", "ODA_DUZENLE": "Oda bilgisini düzenleme"})
    assert "'Yeni kullanıcı kaydı'" in notlar["K_PASIF"] and "'Oda bilgisini düzenleme'" in notlar["ODA_EKLE"]


def test_menuye_yeni_dugme_eklenince_not_kendiliginden_olusur():
    menu = [("B", [dict(ad="Sayfa", izin="Temel", aksiyon=[("Yeni düğme", "Yeni izin")])])]
    notlar = ib.bagimlilik_notlari(menu, {"Temel": ("TEMEL",), "Yeni izin": ("YENI",)})
    assert "YENI" in notlar and "TEMEL" not in notlar


def test_sabit_notlar_menude_karsiligi_olmayan_izinler_icin_eklenir_ve_menu_notunun_ustune_yazmaz():
    notlar = ib.bagimlilik_notlari(MENU, KODLAR)
    assert notlar["IZIN_TANIMLA"] == ib.SABIT_NOTLAR["IZIN_TANIMLA"]
    ozel = ib.bagimlilik_notlari([("B", [dict(ad="S", izin="T", aksiyon=[("d", "P")])])], {"T": ("T",), "P": ("PERSONEL_TANIMLA",)})
    assert "'S'" in ozel["PERSONEL_TANIMLA"]                                  # menüden üretilen not korunur


def test_etiketler_matristen_gorunen_adi_ve_yoksa_teknik_adi_alir():
    matris = {"izinler": [{"izin_adi": "A", "gorunen_ad": "Görünen A"}, {"izin_adi": "B", "gorunen_ad": ""}, {"izin_adi": ""}]}
    assert ib.etiketler_matristen(matris) == {"A": "Görünen A", "B": "B"}
    assert ib.etiketler_matristen(None) == {} and ib.etiketler_matristen({}) == {}


# ================================================================ uygulamanın gerçek menüsü
DUGME_IZINLERI = {
    "KULLANICI_PASIFLESTIR", "ROL_ATAMA_DEGISTIRME", "KULLANICI_PAROLA_SIFIRLA", "CIHAZ_EKLE", "RANDEVU_DUZENLE", "RANDEVU_IPTAL",
    "IZIN_DUZENLE", "ROL_OLUSTUR", "ROL_DUZENLE", "FAALIYET_BIRIMI_DUZENLE",
}
SEKME_ACAN_IZINLER = {
    "TAKVIM_GORUNTULE", "RANDEVU_OLUSTUR", "KULLANICI_OLUSTUR", "CIHAZ_ENVANTER_YONET", "ROL_IZIN_YONET", "ODA_DURUMU_GORUNTULE",
    "FAALIYET_KAYITLARI_DUZENLE", "AUDIT_KAYITLARI_INCELE", "BAKIM_KAYITLARI_YONET", "ARIZA_KAYITLARI_YONET",
}


def test_gercek_menude_dugme_izinlerinin_hepsi_not_alir():
    notlar = ib.izin_notlari()
    assert DUGME_IZINLERI <= set(notlar)
    assert all("tek başına yeni bir sekme açmaz" in notlar[k] for k in DUGME_IZINLERI)


def test_gercek_menude_kendi_basina_sekme_acan_izinler_not_almaz():
    assert not (SEKME_ACAN_IZINLER & set(ib.izin_notlari()))


def test_gercek_menude_oda_izinleri_birlikte_gerektigini_soyler_ve_menuden_cikmayanlar_sabit_not_alir():
    notlar = ib.izin_notlari()
    assert "birlikte" in notlar["ODA_EKLE"] and "birlikte" in notlar["ODA_DUZENLE"]
    assert {"PERSONEL_TANIMLA", "IZIN_TANIMLA", "CIHAZ_TAKIP_KONTROL_LISTESI"} <= set(notlar)


def test_gercek_menu_degismezi_her_dugme_izni_ya_sekme_acar_ya_not_alir():
    """Menüye bir düğme eklenip izni unutulursa bu test kırılır: kural 'ya sekme açar ya not alır'."""
    notlar = ib.izin_notlari()
    sekme_acanlar = set()
    for _, ogeler in mw.MENU:
        for oge in ogeler:
            kodlar = mw.IZIN_KODLARI.get(oge.get("izin"), ())
            if len(kodlar) == 1:
                sekme_acanlar.add(kodlar[0])
    for _, ogeler in mw.MENU:
        for oge in ogeler:
            for _, izin in oge.get("aksiyon", []):
                for kod in mw.IZIN_KODLARI.get(izin, ()):
                    assert kod in sekme_acanlar or kod in notlar, f"{kod} ({izin}) sekme de açmıyor, notu da yok"


def test_gercek_notlar_matristeki_gorunen_adla_yazilir():
    matris = {"izinler": [{"izin_adi": "KULLANICI_OLUSTUR", "gorunen_ad": "Kullanıcı oluşturma (özel ad)"}]}
    assert "'Kullanıcı oluşturma (özel ad)'" in ib.izin_notlari(matris)["KULLANICI_PASIFLESTIR"]
    assert ib.not_getir("KULLANICI_PASIFLESTIR") and ib.not_getir("TAKVIM_GORUNTULE") is None


# ================================================================ ekran: İzin Düzenle penceresi ve matris
ROLLER = [{"rol_id": 1, "rol_adi": "PSIKOLOG", "gorunen_ad": "Psikolog"}, {"rol_id": 6, "rol_adi": "ADMIN", "gorunen_ad": "Sistem Admin"}]
IZINLER = [
    {"izin_id": 1, "izin_adi": "TAKVIM_GORUNTULE", "gorunen_ad": "Randevu takvimini görüntüleme"},
    {"izin_id": 2, "izin_adi": "ROL_ATAMA_DEGISTIRME", "gorunen_ad": "Rol atama veya değiştirme"},
    {"izin_id": 3, "izin_adi": "KULLANICI_OLUSTUR", "gorunen_ad": "Kullanıcı oluşturma"},
]
MATRIS = {"roller": ROLLER, "izinler": IZINLER, "rol_izin_map": {"1": [1], "6": [1, 2, 3]}}


def dialog(izin_id, matris=MATRIS):
    return rid.IzinDuzenleDialog("http://s", "t", izin_id, ROLLER, matris)


def test_dialog_dugme_izninde_not_kutusu_gorunur_ve_metni_dogrudur(qt_app):
    d = dialog(2)
    assert not d.lbl_bagimlilik_notu.isHidden() and d.lbl_bagimlilik_notu.text().startswith("ⓘ")
    assert "'Kullanıcı & Personel'" in d.lbl_bagimlilik_notu.text() and "'Kullanıcı oluşturma'" in d.lbl_bagimlilik_notu.text()
    assert d.bagimlilik_notu in d.lbl_bagimlilik_notu.text()


def test_dialog_sekme_acan_izinde_not_kutusu_gizli_ve_pencere_normal_boyda(qt_app):
    normal, notlu = dialog(1), dialog(2)
    assert normal.lbl_bagimlilik_notu.isHidden() and normal.bagimlilik_notu is None
    assert notlu.height() == normal.height() + rid.IzinDuzenleDialog.NOT_EK_YUKSEKLIK


def test_dialog_bilinmeyen_izinde_cokmez_ve_not_gostermez(qt_app):
    d = dialog(999)
    assert d.secilen_izin is None and d.lbl_bagimlilik_notu.isHidden()


def test_dialog_rol_kutulari_izin_durumunu_dogru_gosterir_admin_gizli_kalir(qt_app):
    notlu, normal = dialog(2), dialog(1)
    assert set(notlu.rol_checkboxlar) == {1} and notlu.rol_checkboxlar[1].isChecked() is False     # psikolog bu izne sahip değil
    assert normal.rol_checkboxlar[1].isChecked() is True                                          # psikolog takvimi görüyor


def matris_sayfasi(qt_app, matris=MATRIS):
    s = sri.RolIzinSayfasi(token="t", api_url="http://s")
    s._ilk_yukleme_yapildi = True
    s.matris_tablosunu_doldur(matris)
    return s


def test_matriste_notlu_izinler_bilgi_isaretiyle_ve_ipucuyla_gosterilir(qt_app):
    s = matris_sayfasi(qt_app)
    normal, notlu = s.tablo.item(0, 0), s.tablo.item(1, 0)
    assert not normal.text().endswith("ⓘ") and normal.toolTip() == "TAKVIM_GORUNTULE"
    assert notlu.text() == "Rol atama veya değiştirme  ⓘ"
    assert notlu.toolTip().startswith("ROL_ATAMA_DEGISTIRME\n\n") and "tek başına yeni bir sekme açmaz" in notlu.toolTip()


def test_matriste_secili_satirin_izin_kimligi_isaretten_etkilenmez(qt_app):
    s = matris_sayfasi(qt_app)
    s.tablo.selectRow(1)
    assert s.secili_izin_id() == 2


def test_matriste_aciklama_satiri_yalnizca_notlu_izin_varsa_gorunur(qt_app):
    assert not matris_sayfasi(qt_app).lbl_aciklama.isHidden()
    sadece_sekme_acan = {**MATRIS, "izinler": [IZINLER[0], IZINLER[2]]}
    assert matris_sayfasi(qt_app, sadece_sekme_acan).lbl_aciklama.isHidden()


def test_matris_yeniden_dolunca_isaretler_cogalmaz(qt_app):
    s = matris_sayfasi(qt_app)
    s.matris_tablosunu_doldur(MATRIS)
    assert s.tablo.item(1, 0).text().count("ⓘ") == 1 and s.tablo.rowCount() == 3


# ================================================================ görünen adların matristen geldiğini doğrulayan testler
OZEL_MATRIS = {**MATRIS, "izinler": [
    IZINLER[0], IZINLER[1], {"izin_id": 3, "izin_adi": "KULLANICI_OLUSTUR", "gorunen_ad": "Yeni kullanıcı kaydı açma"}]}


def test_not_getir_matristeki_gorunen_adi_kullanir():
    assert "'Yeni kullanıcı kaydı açma'" in ib.not_getir("ROL_ATAMA_DEGISTIRME", OZEL_MATRIS)
    assert "'Kullanıcı oluşturma'" in ib.not_getir("ROL_ATAMA_DEGISTIRME")                    # matris verilmezse menü adı


def test_dialog_notta_matristeki_gorunen_adi_kullanir(qt_app):
    d = dialog(2, OZEL_MATRIS)
    assert "'Yeni kullanıcı kaydı açma'" in d.lbl_bagimlilik_notu.text()


def test_matris_sayfasi_notlarda_ayni_gorunen_adi_kullanir(qt_app):
    s = matris_sayfasi(qt_app, OZEL_MATRIS)
    assert "'Yeni kullanıcı kaydı açma'" in s.tablo.item(1, 0).toolTip()
