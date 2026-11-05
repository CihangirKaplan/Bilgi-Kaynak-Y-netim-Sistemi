"""Cihaz Uygunluğu ekranı: ızgara, sayaçlar, süzme, hafta gezintisi, müsait cihaz bul, gün detayı, izinler."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
import requests
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication

import cihaz_uygunluk_ekrani as ekran_modulu
from cihaz_uygunluk_ekrani import (CihazUygunlukEkrani, GunDetayDialog, ILK_GUN_SUTUNU, SUTUN_CIHAZ, SUTUN_SU_AN,
                                   UYARI_SUTUNU)
import cihaz_uygunluk_mantigi as m

BUGUN = date(2026, 11, 4)                               # Çarşamba
SIMDI = datetime(2026, 11, 4, 9, 30)
HAFTA = (date(2026, 11, 2), date(2026, 11, 8))


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def sabit_zaman(monkeypatch):
    monkeypatch.setattr(CihazUygunlukEkrani, "_bugun", lambda self: BUGUN)
    monkeypatch.setattr(CihazUygunlukEkrani, "_simdi", lambda self: SIMDI)


def d(tur, bas, bit=None, kaynak="kayit"):
    return {"tur": tur, "baslangic": bas, "bitis": bit, "kaynak": kaynak}


def cihaz(cid, kod, ad, donemler=(), durum="Kullanima_Hazir", **ek):
    return {"cihaz_id": cid, "envanter_kodu": kod, "cihaz_adi": ad, "durum": durum, "kalibrasyon_gecerlilik": None,
            "kalibrasyon_uyari": None, "sonraki_bakim": None, "bakim_uyari": None, "donemler": list(donemler), **ek}


CIHAZLAR = [
    cihaz(1, "E-1", "EEG"),
    cihaz(2, "E-2", "Işık Terapi", [d("REZERVASYON", "2026-11-04T10:00:00", "2026-11-04T12:00:00")]),
    cihaz(3, "E-3", "Monitör", [d("ARIZA", "2026-11-02T09:00:00")], durum="Arizali",
          kalibrasyon_gecerlilik="2026-11-01", kalibrasyon_uyari="SURESI_DOLDU"),
    cihaz(4, "E-4", "Ultrason", [d("BAKIM", "2026-11-05T00:00:00", "2026-11-07T00:00:00")],
          sonraki_bakim="2026-11-10", bakim_uyari="YAKLASIYOR"),
    cihaz(5, "E-5", "Spiro", [d("KULLANIM_DISI", "2026-11-04T00:00:00", None, "durum")], durum="Kullanim_Disi"),
]


def yanit(cihazlar, bas, bit, durum=200):
    r = MagicMock()
    r._tkys_oturum_reddedildi = False
    r.status_code = durum
    r.json.return_value = {"bugun": BUGUN.isoformat(), "baslangic": bas, "bitis": bit, "cihazlar": cihazlar}
    r.raise_for_status.return_value = None
    return r


class Sunucu:
    """oturum_kontrollu_istek yerine geçer; istekleri kaydeder."""
    def __init__(self, cihazlar=None, hata=None, durum=200):
        self.cihazlar = CIHAZLAR if cihazlar is None else cihazlar
        self.hata, self.durum, self.istekler = hata, durum, []

    def __call__(self, yontem, url, **kw):
        self.istekler.append((yontem, url, kw.get("params"), kw.get("headers")))
        if self.hata:
            raise self.hata
        p = kw["params"]
        return yanit(self.cihazlar, p["baslangic"], p["bitis"], self.durum)


def ac(sunucu=None, **ekran_kw):
    sunucu = sunucu or Sunucu()
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", sunucu):
        e = CihazUygunlukEkrani("http://x", "T", **ekran_kw)
    return e, sunucu


def metin(e, satir, sutun):
    return e.tablo.item(satir, sutun).text()


def gun_sutunu(gun):
    return ILK_GUN_SUTUNU + (gun - HAFTA[0]).days


def gorunen_kimlikler(e):
    return [e.tablo.item(i, SUTUN_CIHAZ).data(Qt.UserRole) for i in range(e.tablo.rowCount())]


# --------------------------------------------------------------------------------- ızgara
def test_izgara_cihazlari_ve_haftanin_gunlerini_gosterir(qt_app):
    e, s = ac()
    assert e.tablo.rowCount() == 5 and e.tablo.columnCount() == 10
    assert metin(e, 0, SUTUN_CIHAZ) == "E-1  ·  EEG"
    basliklar = [e.tablo.horizontalHeaderItem(i).text() for i in range(10)]
    assert basliklar[ILK_GUN_SUTUNU] == "Pzt\n2 Kas" and basliklar[ILK_GUN_SUTUNU + 6] == "Paz\n8 Kas"
    assert basliklar[gun_sutunu(BUGUN)] == "Çar\n4 Kas\nBUGÜN"
    assert sum("BUGÜN" in b for b in basliklar) == 1
    assert e.lbl_hafta.text() == "2 – 8 Kasım 2026"
    assert len(s.istekler) == 1                                          # bugün bu haftada: tek istek


def test_istek_dogru_adrese_parametreyle_ve_tokenla_gider(qt_app):
    e, s = ac()
    yontem, url, params, basliklar = s.istekler[0]
    assert (yontem, url) == ("GET", "http://x/api/cihaz-uygunluk")
    assert params == {"baslangic": "2026-11-02", "bitis": "2026-11-08"}
    assert basliklar == {"Authorization": "Bearer T"}


def test_gun_hucreleri_durumlari_ve_aciklamalari_gosterir(qt_app):
    e, _ = ac()
    assert all(metin(e, 0, ILK_GUN_SUTUNU + i) == "Müsait" for i in range(7))
    assert metin(e, 1, gun_sutunu(BUGUN)) == "Kısmen dolu\n2 sa 00 dk"
    assert metin(e, 1, gun_sutunu(date(2026, 11, 3))) == "Müsait"
    assert [metin(e, 2, ILK_GUN_SUTUNU + i) for i in range(7)] == ["Arızalı"] * 7          # açık arıza pazartesiden itibaren
    assert [metin(e, 3, ILK_GUN_SUTUNU + i) for i in range(7)] == ["Müsait"] * 3 + ["Bakımda"] * 2 + ["Müsait"] * 2
    assert metin(e, 4, gun_sutunu(date(2026, 11, 3))) == "Müsait"
    assert metin(e, 4, gun_sutunu(BUGUN)) == "Kullanım dışı"
    ipucu = e.tablo.item(2, gun_sutunu(BUGUN)).toolTip()
    assert "Arızalı" in ipucu and "2 Kasım 09:00'den beri açık" in ipucu and "çözülene kadar rezerve edilemez" in ipucu


def test_renkler_durumla_eslesir(qt_app):
    e, _ = ac()
    renk = lambda satir, sutun: e.tablo.item(satir, sutun).background().color().name().upper()
    assert renk(0, ILK_GUN_SUTUNU) == m_renk(m.MUSAIT) and renk(2, ILK_GUN_SUTUNU) == m_renk(m.ARIZA)
    assert renk(3, gun_sutunu(date(2026, 11, 5))) == m_renk(m.BAKIM)
    assert renk(1, gun_sutunu(BUGUN)) == m_renk(m.KISMEN) and renk(4, gun_sutunu(BUGUN)) == m_renk(m.KULLANIM_DISI)


def m_renk(kod):
    return ekran_modulu.RENKLER[kod][1].upper()


def test_su_an_sutunu_simdiki_duruma_gore(qt_app):
    e, _ = ac()                                                          # 09:30: rezervasyon 10:00'da başlıyor
    assert [metin(e, i, SUTUN_SU_AN) for i in range(5)] == ["Müsait", "Müsait", "Arızalı", "Müsait", "Kullanım dışı"]


def test_su_an_rezervasyon_surerken_rezerve_gorunur(qt_app, monkeypatch):
    monkeypatch.setattr(CihazUygunlukEkrani, "_simdi", lambda self: datetime(2026, 11, 4, 10, 30))
    e, _ = ac()
    assert metin(e, 1, SUTUN_SU_AN) == "Rezerve"


def test_uyarilar_sutunu_kritik_ve_yaklasan(qt_app):
    e, _ = ac()
    assert metin(e, 2, UYARI_SUTUNU) == "⚠ Kalibrasyon süresi doldu (1 Kasım 2026, 3 gün önce)"
    assert metin(e, 3, UYARI_SUTUNU) == "⚠ Bakım zamanı yaklaşıyor (10 Kasım 2026, 6 gün kaldı)"
    assert metin(e, 0, UYARI_SUTUNU) == ""
    assert e.tablo.item(2, UYARI_SUTUNU).foreground().color().name().upper() == "#991B1B"      # kritik kırmızı
    assert e.tablo.item(3, UYARI_SUTUNU).foreground().color().name().upper() == "#854D0E"      # yaklaşan amber


def test_sayaclar_bugunun_durumunu_gosterir(qt_app):
    e, _ = ac()
    assert e.cip_musait.text() == "bugün 3 müsait" and e.cip_dolu.text() == "0 dolu"
    assert e.cip_bakim.text() == "0 bakımda" and e.cip_ariza.text() == "1 arızalı" and e.cip_kdisi.text() == "1 kullanım dışı"


# ------------------------------------------------------------------------------- süzme
def test_arama_kod_ve_ada_gore_turkce_duyarsiz(qt_app):
    e, _ = ac()
    e.arama.setText("IŞIK")
    assert gorunen_kimlikler(e) == [2]
    e.arama.setText("e-4")
    assert gorunen_kimlikler(e) == [4]
    e.arama.setText("yokboyle")
    assert gorunen_kimlikler(e) == [] and not e.bos_mesaj.isHidden() and e.tablo.isHidden()
    assert "uyan cihaz bulunamadı" in e.bos_mesaj.text()
    e.arama.setText("")
    assert len(gorunen_kimlikler(e)) == 5 and e.bos_mesaj.isHidden()


def test_filtre_bugun_musait_ve_sorunlu(qt_app):
    e, _ = ac()
    e.cmb_filtre.setCurrentIndex(e.cmb_filtre.findData("BUGUN_MUSAIT"))
    assert gorunen_kimlikler(e) == [1, 2, 4]
    e.cmb_filtre.setCurrentIndex(e.cmb_filtre.findData("SORUNLU"))
    assert gorunen_kimlikler(e) == [3, 4, 5]                                # arıza, bakım, kullanım dışı (+uyarılılar)
    e.cmb_filtre.setCurrentIndex(e.cmb_filtre.findData("TUMU"))
    assert len(gorunen_kimlikler(e)) == 5


# -------------------------------------------------------------------------- hafta gezintisi
def test_sonraki_ve_onceki_hafta_dogru_aralik_ister_ve_bugun_icin_ayri_istek_atar(qt_app):
    e, s = ac()
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        e.btn_sonraki.click()
    assert e.lbl_hafta.text() == "9 – 15 Kasım 2026" and e.hafta_basi == date(2026, 11, 9)
    assert [i[2] for i in s.istekler[1:]] == [{"baslangic": "2026-11-09", "bitis": "2026-11-15"},
                                              {"baslangic": "2026-11-04", "bitis": "2026-11-04"}]
    assert e.cip_musait.text() == "bugün 3 müsait"                          # sayaç hâlâ bugünü gösterir
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        e.btn_onceki.click()
        e.btn_onceki.click()
    assert e.lbl_hafta.text() == "26 Ekim – 1 Kasım 2026"
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        e.btn_bugun.click()
    assert e.hafta_basi == date(2026, 11, 2)


def test_tarih_secici_o_haftaya_gider_program_degisikligi_tekrar_istek_atmaz(qt_app):
    e, s = ac()
    sayi = len(s.istekler)
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        e.dt_git.setDate(QDate(2026, 12, 25))
    assert e.hafta_basi == date(2026, 12, 21)
    yeni = len(s.istekler)
    assert yeni == sayi + 2 and e.lbl_hafta.text() == "21 – 27 Aralık 2026"
    assert e.dt_git.date() == QDate(2026, 12, 21)                            # seçici haftanın başına döner
    assert len(s.istekler) == yeni                                           # geri yazma yeni istek atmadı


def test_hafta_degisince_musait_bul_sonucu_temizlenir(qt_app):
    e, s = ac()
    e.dt_bul.setDate(QDate(2026, 11, 4))
    e.cmb_bul_bas.setCurrentText("12:00"); e.cmb_bul_bit.setCurrentText("13:00")
    e._musait_bul()
    assert e.musait_idler
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        e.btn_sonraki.click()
    assert e.musait_idler is None and e.lbl_sonuc.text() == "" and len(gorunen_kimlikler(e)) == 5


# --------------------------------------------------------------------- müsait cihaz bul
def bul(e, tarih, bas, bit):
    e.dt_bul.setDate(QDate(tarih.year, tarih.month, tarih.day))
    e.cmb_bul_bas.setCurrentText(bas)
    e.cmb_bul_bit.setCurrentText(bit)
    e._musait_bul()


def test_musait_cihaz_bul_aralikta_bos_cihazlari_listeler(qt_app):
    e, _ = ac()
    bul(e, BUGUN, "10:00", "11:00")                                         # E-2 rezerve, E-3 arızalı, E-5 kullanım dışı
    assert gorunen_kimlikler(e) == [1, 4] and e.lbl_sonuc.text() == "2 cihaz müsait (4 Kasım 2026, 10:00 – 11:00)"
    bul(e, BUGUN, "12:00", "13:00")                                         # E-2 12:00'de serbest
    assert gorunen_kimlikler(e) == [1, 2, 4]
    bul(e, date(2026, 11, 5), "09:00", "10:00")                             # E-4 perşembe bakımda
    assert gorunen_kimlikler(e) == [1, 2]


def test_musait_cihaz_yoksa_bilgi_verir_ve_temizle_geri_getirir(qt_app):
    e, _ = ac(Sunucu([CIHAZLAR[2], CIHAZLAR[4]]))
    bul(e, BUGUN, "10:00", "11:00")
    assert gorunen_kimlikler(e) == [] and e.lbl_sonuc.text().startswith("Bu aralıkta müsait cihaz yok")
    e._bulmayi_temizle()
    assert len(gorunen_kimlikler(e)) == 2 and e.lbl_sonuc.text() == "" and e.musait_idler is None


def test_gecersiz_saat_araligi_uyari_verir_filtre_uygulamaz(qt_app):
    e, _ = ac()
    bul(e, BUGUN, "11:00", "10:00")
    assert e.lbl_sonuc.text() == "Bitiş saati başlangıçtan sonra olmalıdır." and e.musait_idler is None
    assert len(gorunen_kimlikler(e)) == 5


def test_baska_haftanin_gunu_secilirse_o_hafta_yuklenir(qt_app):
    e, s = ac()
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        bul(e, date(2026, 11, 11), "10:00", "11:00")
    assert e.hafta_basi == date(2026, 11, 9) and e.musait_idler is not None
    assert any(i[2] == {"baslangic": "2026-11-09", "bitis": "2026-11-15"} for i in s.istekler)


# --------------------------------------------------------------------------- gün detayı
def test_hucre_tiklaninca_dogru_cihaz_ve_gun_icin_detay_acilir(qt_app):
    e, _ = ac()
    with patch.object(ekran_modulu, "GunDetayDialog") as pencere:
        e.tablo.cellClicked.emit(3, gun_sutunu(date(2026, 11, 6)))                  # E-4, cuma
    cihaz_, gun, bugun = pencere.call_args.args[:3]
    assert cihaz_["envanter_kodu"] == "E-4" and gun == date(2026, 11, 6) and bugun == BUGUN
    pencere.return_value.exec.assert_called_once()


def test_su_an_hucresi_bugunun_detayini_acar_diger_sutunlar_acmaz(qt_app):
    e, _ = ac()
    with patch.object(ekran_modulu, "GunDetayDialog") as pencere:
        e.tablo.cellClicked.emit(1, SUTUN_SU_AN)
        assert pencere.call_args.args[1] == BUGUN
        pencere.reset_mock()
        e.tablo.cellClicked.emit(1, SUTUN_CIHAZ)
        e.tablo.cellClicked.emit(1, UYARI_SUTUNU)
        pencere.assert_not_called()


def tum_yetkiler(**ek):
    return {"rezervasyon": True, "ariza": True, "bakim": True, "kalibrasyon": True, **ek}


def dialog(cihaz_, gun, yetkiler, git=None, ac_=None, simdi=SIMDI):
    return GunDetayDialog(cihaz_, gun, BUGUN, simdi, yetkiler, git, ac_)


def test_detay_basligi_durumu_ve_saat_cizelgesi(qt_app):
    p = dialog(CIHAZLAR[1], BUGUN, tum_yetkiler(), MagicMock(), MagicMock())
    assert p.lbl_durum.text() == "Kısmen dolu" and p.windowTitle() == "E-2 — 4 Kasım 2026 Çarşamba"
    assert len(p.cizelge_etiketleri) == 10 and p.cizelge_etiketleri[2].toolTip() == "10:00 – 11:00  Rezerve"
    assert p.cizelge_etiketleri[0].toolTip() == "08:00 – 09:00  Müsait"
    assert "Rezervasyon: 10:00 – 12:00" in p.satir_metinleri


def test_detayda_kisisel_veri_yok_yalnizca_saat_ve_neden(qt_app):
    p = dialog(CIHAZLAR[2], BUGUN, tum_yetkiler(), MagicMock(), MagicMock())
    tum = " ".join(p.satir_metinleri)
    assert "Arıza: 2 Kasım 09:00'den beri açık" in tum and "Arıza çözülene kadar rezerve edilemez." in tum
    assert [u.text() for u in p.uyari_etiketleri] == ["⚠ Kalibrasyon süresi doldu (1 Kasım 2026, 3 gün önce)"]


def test_rezervasyon_dugmesi_yetkiliye_gorunur_ve_formu_onerilen_saatle_acar(qt_app):
    ac_ = MagicMock()
    p = dialog(CIHAZLAR[1], date(2026, 11, 5), tum_yetkiler(), MagicMock(), ac_)
    assert p.btn_rezervasyon.isEnabled() and p.btn_rezervasyon.toolTip() == "08:00 – 09:00 için rezervasyon formunu açar"
    p.btn_rezervasyon.click()
    ac_.assert_not_called()                                                           # pencere kapanmadan çalışmaz
    assert p.sonraki_islem == (ac_, (2, date(2026, 11, 5), "08:00", "09:00")) and p.result() == 1


def test_rezervasyon_dugmesi_bugunde_sonraki_tam_saati_onerir(qt_app):
    ac_ = MagicMock()
    p = dialog(CIHAZLAR[0], BUGUN, tum_yetkiler(), MagicMock(), ac_)                  # 09:30 -> 10:00
    p.btn_rezervasyon.click()
    assert p.sonraki_islem == (ac_, (1, BUGUN, "10:00", "11:00"))


@pytest.mark.parametrize("cihaz_, gun, neden", [
    (CIHAZLAR[2], BUGUN, "Arıza çözülene kadar rezerve edilemez."),
    (CIHAZLAR[4], BUGUN, "Cihaz kullanım dışı olduğu için rezerve edilemez."),
    (CIHAZLAR[0], date(2026, 11, 3), "Geçmiş günlere rezervasyon yapılamaz."),
    (CIHAZLAR[3], date(2026, 11, 5), "Bakım süresince rezerve edilemez.")])
def test_rezervasyon_dugmesi_engelli_ve_gecmis_gunlerde_kapali_nedenini_soyler(qt_app, cihaz_, gun, neden):
    ac_ = MagicMock()
    p = dialog(cihaz_, gun, tum_yetkiler(), MagicMock(), ac_)
    assert not p.btn_rezervasyon.isEnabled() and p.btn_rezervasyon.toolTip() == neden
    p.btn_rezervasyon.click()                                                         # devre dışı düğme tıklanmaz
    assert p.sonraki_islem is None and p.result() == 0
    ac_.assert_not_called()


def test_izinsiz_kullanici_hic_islem_dugmesi_gormez(qt_app):
    yok = {"rezervasyon": False, "ariza": False, "bakim": False, "kalibrasyon": False}
    for cihaz_ in CIHAZLAR:
        p = dialog(cihaz_, BUGUN, yok, MagicMock(), MagicMock())
        assert p.btn_rezervasyon is p.btn_ariza is p.btn_bakim is p.btn_kalibrasyon is None
    p = dialog(CIHAZLAR[0], BUGUN, tum_yetkiler(), None, None)                       # geri çağırma yoksa da düğme yok
    assert p.btn_rezervasyon is p.btn_ariza is p.btn_bakim is p.btn_kalibrasyon is None


def test_gecis_dugmeleri_yalnizca_ilgili_neden_ve_izin_varsa_gorunur(qt_app):
    git = MagicMock()
    ariza = dialog(CIHAZLAR[2], BUGUN, tum_yetkiler(), git, MagicMock())
    assert ariza.btn_ariza is not None and ariza.btn_bakim is None
    assert ariza.btn_kalibrasyon is not None                                          # kalibrasyon süresi doldu uyarısı
    ariza.btn_ariza.click()
    git.assert_not_called()
    assert ariza.sonraki_islem == (git, ("Arıza Kayıtları",))
    bakim = dialog(CIHAZLAR[3], date(2026, 11, 6), tum_yetkiler(), git, MagicMock())
    assert bakim.btn_bakim is not None and bakim.btn_ariza is None
    bakim.btn_bakim.click()
    assert bakim.sonraki_islem == (git, ("Bakım Kayıtları",))
    sadece_ariza_izni = dialog(CIHAZLAR[2], BUGUN, tum_yetkiler(ariza=False, kalibrasyon=False), git, MagicMock())
    assert sadece_ariza_izni.btn_ariza is None and sadece_ariza_izni.btn_kalibrasyon is None


def test_psikolog_gibi_salt_okur_kullanici_bilgiyi_gorur_islem_yapamaz(qt_app):
    e, _ = ac(yetkiler={})                                                            # hiçbir işlem izni yok
    assert len(gorunen_kimlikler(e)) == 5 and metin(e, 2, gun_sutunu(BUGUN)) == "Arızalı"
    p = dialog(CIHAZLAR[2], BUGUN, e.yetkiler, e.sayfaya_git, e.rezervasyon_ac)
    assert p.btn_rezervasyon is p.btn_ariza is p.btn_bakim is p.btn_kalibrasyon is None


# ---------------------------------------------------------------------- hata durumları
def test_sunucu_hatasinda_anlasilir_mesaj(qt_app):
    e, _ = ac(Sunucu(hata=requests.ConnectionError("yok")))
    assert "yüklenemedi" in e.bos_mesaj.text() and not e.bos_mesaj.isHidden() and e.tablo.isHidden()


def test_yetki_yoksa_403_mesaji(qt_app):
    cevap = MagicMock(status_code=403)
    hata = requests.HTTPError(response=cevap)
    e, _ = ac(Sunucu(hata=hata))
    assert e.bos_mesaj.text() == "Bu bilgiyi görüntüleme yetkiniz yok."


def test_cihaz_yoksa_bos_mesaj(qt_app):
    e, _ = ac(Sunucu([]))
    assert e.bos_mesaj.text() == "Henüz cihaz kaydı yok." and not e.bos_mesaj.isHidden() and e.tablo.isHidden()


def test_oturum_bittiyse_sessizce_cikar(qt_app):
    with patch.object(ekran_modulu, "oturum_hatasi_mi", return_value=True), \
         patch.object(ekran_modulu, "oturum_kontrollu_istek", Sunucu()):
        e = CihazUygunlukEkrani("http://x", "T")
    assert e.hafta_verisi is None and e.tablo.rowCount() == 0


def test_yenile_dugmesinin_gonderdigi_bool_arguman_sorun_cikarmaz(qt_app):
    e, s = ac()
    with patch.object(ekran_modulu, "oturum_kontrollu_istek", s):
        e.verileri_yukle(False)
        e.verileri_yukle()
    assert len(s.istekler) == 3


# --------------------------------------------------------------------------- satır yüksekliği
def test_satir_yuksekligi_uyari_sayisina_gore_uzar_en_az_54(qt_app):
    from cihaz_uygunluk_ekrani import satir_yuksekligi
    assert satir_yuksekligi([]) == 54
    assert satir_yuksekligi(["Kısa uyarı"]) == 54
    uzun = "Kalibrasyon süresi doldu (1 Kasım 2026, 3 gün önce)"            # 51 karakter -> 2 satır
    assert satir_yuksekligi([uzun]) == 56
    assert satir_yuksekligi([uzun, "Bakım gecikti (30 Ekim 2026, 5 gün önce)"]) == 22 + 17 * 4


def test_uyarisiz_satirlar_varsayilan_yukseklikte_uyarililar_uzundur(qt_app):
    e, _ = ac()
    assert e.tablo.rowHeight(0) == 54 and e.tablo.rowHeight(1) == 54
    assert e.tablo.rowHeight(2) > 54                                        # iki uyarısı var (kalibrasyon + bakım)


def test_ekran_islemi_pencere_kapandiktan_sonra_calistirir(qt_app):
    e, _ = ac()
    git, ac_ = MagicMock(), MagicMock()
    e.sayfaya_git, e.rezervasyon_ac = git, ac_
    sahte = MagicMock(sonraki_islem=(ac_, (1, BUGUN, "10:00", "11:00")))
    sahte.exec.side_effect = lambda: ac_.assert_not_called()                          # exec sürerken henüz çalışmadı
    with patch.object(ekran_modulu, "GunDetayDialog", return_value=sahte):
        e.gun_detayi_ac(CIHAZLAR[0], BUGUN)
    ac_.assert_called_once_with(1, BUGUN, "10:00", "11:00")
    sahte2 = MagicMock(sonraki_islem=None)
    with patch.object(ekran_modulu, "GunDetayDialog", return_value=sahte2):
        e.gun_detayi_ac(CIHAZLAR[0], BUGUN)
    assert ac_.call_count == 1 and git.call_count == 0                                # işlem yoksa hiçbir şey çağrılmaz


def test_gecis_dugmeleri_ayri_satirda_ve_etiketli(qt_app):
    p = dialog(CIHAZLAR[2], BUGUN, tum_yetkiler(), MagicMock(), MagicMock())
    from PySide6.QtWidgets import QLabel
    assert any(e.text() == "İlgili kayıtlar:" for e in p.findChildren(QLabel))
    sade = dialog(CIHAZLAR[0], BUGUN, tum_yetkiler(), MagicMock(), MagicMock())
    assert not any(e.text() == "İlgili kayıtlar:" for e in sade.findChildren(QLabel))   # geçiş düğmesi yoksa etiket de yok
