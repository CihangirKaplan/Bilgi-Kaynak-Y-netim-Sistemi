"""Rol & İzin Yönetimi: tek başına sekme açmayan izinler için uyarı notu.

Notlar menü tanımından otomatik üretilir; bu testler hem üretim mantığını hem de İzin Düzenle penceresi ile
matristeki görünümü doğrular. Gerçek sunucu kullanılmaz.
"""
import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton

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


def test_matriste_notlu_izinlerin_yaninda_bilgi_dugmesi_ve_ipucu_vardir(qt_app):
    s = matris_sayfasi(qt_app)
    normal, notlu = s.tablo.item(0, 0), s.tablo.item(1, 0)
    assert normal.text() == "Randevu takvimini görüntüleme" and normal.toolTip() == "TAKVIM_GORUNTULE"
    assert notlu.text() == "Rol atama veya değiştirme"                              # ad metni değişmez; işaret düğmedir
    assert notlu.toolTip().startswith("ROL_ATAMA_DEGISTIRME\n\n") and "tek başına yeni bir sekme açmaz" in notlu.toolTip()
    assert s.tablo.cellWidget(0, 0) is None and s.tablo.cellWidget(1, 0).findChild(QToolButton, "bilgiDugmesi") is not None


def test_matriste_secili_satirin_izin_kimligi_isaretten_etkilenmez(qt_app):
    s = matris_sayfasi(qt_app)
    s.tablo.selectRow(1)
    assert s.secili_izin_id() == 2


def test_matriste_aciklama_satiri_yalnizca_notlu_izin_varsa_gorunur(qt_app):
    assert not matris_sayfasi(qt_app).lbl_aciklama.isHidden()
    sadece_sekme_acan = {**MATRIS, "izinler": [IZINLER[0], IZINLER[2]]}
    assert matris_sayfasi(qt_app, sadece_sekme_acan).lbl_aciklama.isHidden()


def test_matris_yeniden_dolunca_dugmeler_cogalmaz(qt_app):
    s = matris_sayfasi(qt_app)
    s.matris_tablosunu_doldur(MATRIS)
    s.matris_tablosunu_doldur(MATRIS)
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)              # silinmeye bırakılan eski düğmeler gerçekten silinsin
    assert len(s.tablo.findChildren(QToolButton, "bilgiDugmesi")) == 1 and s.tablo.rowCount() == 3


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


# ================================================================ tıklanabilir "i" düğmesi
def test_bilgi_dugmesine_tiklaninca_aciklama_penceresi_acilir(qt_app):
    s = matris_sayfasi(qt_app)
    dugme = s.tablo.cellWidget(1, 0).findChild(QToolButton, "bilgiDugmesi")
    with patch.object(QMessageBox, "information") as bilgi:
        dugme.click()
    assert bilgi.call_args.args[1] == "İzin Hakkında"
    assert "Rol atama veya değiştirme" in bilgi.call_args.args[2] and "tek başına yeni bir sekme açmaz" in bilgi.call_args.args[2]


def test_bilgi_dugmesi_yuvarlak_mavi_tiklanabilir_gorunur(qt_app):
    dugme = matris_sayfasi(qt_app).tablo.cellWidget(1, 0).findChild(QToolButton, "bilgiDugmesi")
    assert dugme.text() == "i" and dugme.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert dugme.width() == dugme.height() == 24 and "border-radius: 12px" in dugme.styleSheet() and "hover" in dugme.styleSheet()
    assert "tıklayın" in dugme.toolTip()


def test_her_satirin_dugmesi_kendi_notunu_gosterir(qt_app):
    veri = {**MATRIS, "izinler": IZINLER + [{"izin_id": 4, "izin_adi": "CIHAZ_EKLE", "gorunen_ad": "Cihaz ekleme"}]}
    s = matris_sayfasi(qt_app, veri)
    with patch.object(QMessageBox, "information") as bilgi:
        s.tablo.cellWidget(3, 0).findChild(QToolButton).click()
        s.tablo.cellWidget(1, 0).findChild(QToolButton).click()
    ilk, ikinci = bilgi.call_args_list
    assert "Cihaz ekleme" in ilk.args[2] and "'Cihaz Envanteri'" in ilk.args[2]
    assert "Rol atama veya değiştirme" in ikinci.args[2] and "'Kullanıcı & Personel'" in ikinci.args[2]


def test_bilgi_dugmesi_satir_secimini_ve_izin_kimligini_bozmaz(qt_app):
    s = matris_sayfasi(qt_app)
    s.tablo.selectRow(1)
    assert s.secili_izin_id() == 2 and s.tablo.item(1, 0).data(Qt.ItemDataRole.UserRole) == 2


def test_notlu_satirin_sutunu_dugmeye_yer_acar(qt_app):
    s = matris_sayfasi(qt_app)
    assert s.tablo.item(1, 0).sizeHint().width() > s.tablo.fontMetrics().horizontalAdvance("Rol atama veya değiştirme")


def test_aciklama_satiri_dugmeye_gondermede_bulunur(qt_app):
    assert "düğmeye tıklayın" in matris_sayfasi(qt_app).lbl_aciklama.text()


# ================================================================ ön koşul mantığı (sahte menü)
def test_onkosullar_dugme_izinleri_icin_sayfanin_iznini_verir_sekme_acanlar_ve_birlikte_gerekenler_icin_vermez():
    t = ib.onkosullar(MENU, KODLAR)
    assert t["K_PASIF"] == [("Kullanıcılar", ("K_OLUSTUR",))]
    assert "K_OLUSTUR" not in t and "RAPOR" not in t
    assert "ODA_EKLE" not in t and "ODA_DUZENLE" not in t                       # birlikte gerekenler: karşılıklı kilitlenmesin


def test_ayni_izin_iki_sayfanin_dugmesiyse_secenek_olarak_ikisi_de_listelenir_biri_yeter():
    t = ib.onkosullar(MENU, KODLAR)
    assert t["AKTAR"] == [("Raporlar", ("RAPOR",)), ("Arşiv", ("ARSIV",))]
    assert ib.eksik_onkosullar("AKTAR", {"ARSIV"}, t) == []                      # seçeneklerden biri yeterli
    assert ib.eksik_onkosullar("AKTAR", {"BASKA"}, t) == t["AKTAR"]


def test_eksik_onkosullar_sagliyorsa_ya_da_onkosul_yoksa_bos_doner():
    t = ib.onkosullar(MENU, KODLAR)
    assert ib.eksik_onkosullar("K_PASIF", {"K_OLUSTUR", "X"}, t) == []
    assert ib.eksik_onkosullar("K_PASIF", set(), t) == t["K_PASIF"]
    assert ib.eksik_onkosullar("YOK_BOYLE_IZIN", set(), t) == [] and ib.eksik_onkosullar("K_OLUSTUR", set(), t) == []


def test_sabit_onkosul_personel_tanimla_kullanici_olusturmaya_baglidir():
    t = ib.onkosullari_getir()
    assert t["PERSONEL_TANIMLA"] == [("Kullanıcı & Personel", ("KULLANICI_OLUSTUR",))]


def test_onkosul_metni_tek_secenek_birden_cok_kod_ve_alternatifler():
    etiket = {"A": "Birinci", "B": "İkinci"}
    assert ib.onkosul_metni([("S", ("A",))], etiket) == "'Birinci'"
    assert ib.onkosul_metni([("S", ("A", "B"))], etiket) == "'Birinci' ve 'İkinci'"
    assert ib.onkosul_metni([("S", ("A",)), ("T", ("B",))], etiket) == "'Birinci' ya da 'İkinci'"
    assert ib.onkosul_metni([("S", ("X",))]) == "'X'"


def test_gercek_menude_onkosulu_olan_her_izin_notu_da_vardir():
    t, notlar = ib.onkosullari_getir(), ib.izin_notlari()
    assert set(t) <= set(notlar) and {"ROL_ATAMA_DEGISTIRME", "CIHAZ_EKLE", "RANDEVU_DUZENLE"} <= set(t)


# ================================================================ İzin Düzenle: ön koşulu olmayan role izin verilirken uyarı
ROLLER3 = [
    {"rol_id": 1, "rol_adi": "PSIKOLOG", "gorunen_ad": "Psikolog"},
    {"rol_id": 2, "rol_adi": "MEMUR", "gorunen_ad": "Memur"},
    {"rol_id": 6, "rol_adi": "ADMIN", "gorunen_ad": "Sistem Admin"},
]
# Memur "Kullanıcı oluşturma"ya sahip; Psikolog değil. Rol atama (id 2) kimsede yok.
MATRIS3 = {"roller": ROLLER3, "izinler": IZINLER, "rol_izin_map": {"1": [1], "2": [1, 3], "6": [1, 2, 3]}}


def dialog3(izin_id, matris=MATRIS3):
    return rid.IzinDuzenleDialog("http://s", "t", izin_id, ROLLER3, matris)


def isaretle(d, *rol_idleri):
    for rol_id, kutu in d.rol_checkboxlar.items():
        kutu.setChecked(rol_id in rol_idleri)


def test_onkosulu_olmayan_role_bagli_izin_verilmek_istenirse_aciklayici_uyari_olusur(qt_app):
    d = dialog3(2)
    isaretle(d, 1)                                                                # Psikolog: Kullanıcı oluşturma yok
    mesaj = d.onkosul_engeli()
    assert "önce 'Kullanıcı oluşturma' izninin olması gerekiyor" in mesaj
    assert "'Kullanıcı & Personel' sayfasının içinde çalışır" in mesaj and "•  Psikolog" in mesaj
    assert "Memur" not in mesaj and "sonra bu izni verebilirsiniz" in mesaj


def test_onkosulu_olan_role_verilirken_uyari_cikmaz(qt_app):
    d = dialog3(2)
    isaretle(d, 2)                                                                # Memur: Kullanıcı oluşturma var
    assert d.onkosul_engeli() is None


def test_birden_cok_role_verilirken_yalnizca_onkosulu_olmayanlar_listelenir(qt_app):
    d = dialog3(2)
    isaretle(d, 1, 2)
    mesaj = d.onkosul_engeli()
    assert "•  Psikolog" in mesaj and "•  Memur" not in mesaj


def test_zaten_verilmis_olan_izne_dokunulmaz_eski_tutarsizlik_yeni_kaydi_engellemez(qt_app):
    matris = {**MATRIS3, "rol_izin_map": {"1": [1, 2], "2": [1, 3], "6": [1, 2, 3]}}      # Psikolog'da rol atama zaten var
    d = dialog3(2, matris)
    assert d.rol_checkboxlar[1].isChecked()
    assert d.onkosul_engeli() is None


def test_onkosulu_olmayan_izinler_hicbir_zaman_engellenmez(qt_app):
    d = dialog3(1)                                                                # Takvim: sekme açan izin
    isaretle(d, 1, 2)
    assert d.onkosul_engeli() is None


def test_onkosul_izni_sistemde_tanimsizsa_engellenmez(qt_app):
    matris = {**MATRIS3, "izinler": [IZINLER[0], IZINLER[1]]}                      # KULLANICI_OLUSTUR listede yok
    d = dialog3(2, matris)
    isaretle(d, 1)
    assert d.onkosul_engeli() is None


def test_bilinmeyen_izinde_onkosul_engeli_yoktur(qt_app):
    assert dialog3(999).onkosul_engeli() is None


def test_uyarida_gorunen_ad_matristeki_adla_yazilir(qt_app):
    ozel = {**MATRIS3, "izinler": [IZINLER[0], IZINLER[1], {"izin_id": 3, "izin_adi": "KULLANICI_OLUSTUR", "gorunen_ad": "Yeni kullanıcı kaydı açma"}]}
    d = dialog3(2, ozel)
    isaretle(d, 1)
    assert "'Yeni kullanıcı kaydı açma'" in d.onkosul_engeli()


def test_kaydet_onkosul_eksikse_uyari_verir_ve_sunucuya_hicbir_sey_gondermez(qt_app):
    d = dialog3(2)
    isaretle(d, 1)
    with patch.object(QMessageBox, "warning") as uyari, patch.object(rid.requests, "put") as put:
        d.kaydet()
    assert uyari.call_args.args[1] == "Önce bağlı izin gerekli" and "olması gerekiyor" in uyari.call_args.args[2]
    assert not put.called and d.result() == 0


def test_kaydet_onkosul_tamsa_normal_kaydeder(qt_app):
    d = dialog3(2)
    isaretle(d, 2)
    yanit = MagicMock(status_code=200)
    with patch.object(QMessageBox, "warning") as uyari, patch.object(QMessageBox, "information"), patch.object(rid.requests, "put", return_value=yanit) as put:
        d.kaydet()
    assert not uyari.called and put.call_count == 1
    gonderilen = put.call_args.kwargs["json"]["verilen_rol_idleri"]
    assert sorted(gonderilen) == [2, 6]                                            # Memur + korunan Admin


def test_izin_kaldirmak_ya_da_degistirmeden_kaydetmek_engellenmez(qt_app):
    d = dialog3(2)
    isaretle(d)                                                                    # hiçbir role verilmiyor
    assert d.onkosul_engeli() is None
