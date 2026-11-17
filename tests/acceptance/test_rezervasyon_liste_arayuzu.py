"""Cihaz Rezervasyonu sayfası: diğer cihaz sayfalarıyla aynı görünüm, arama, sayaçlar, durum etiketleri, iptal akışı.

Qt nesneleri her testte kapatılıp silinir (CI'da çıkışta oluşan aralıklı Qt çökmesine karşı; bkz. test_menu_yetkileri.py).
"""
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REZ = [
    {"rezervasyon_id": 1, "cihaz_id": "E-1 - EEG", "envanter_kodu": "E-1", "cihaz_adi": "EEG", "oda_adi": "Oda-1", "bolum_id": 4, "bolum_adi": "Psikoloji Bölümü",
     "proje_turu": "Araştırma", "proje_adi_aciklamasi": "Pilot çalışma",
     "baslangic_zamani": "2026-11-20T10:00:00", "bitis_zamani": "2026-11-20T12:00:00", "durum": "Aktif"},
    {"rezervasyon_id": 2, "cihaz_id": "E-2 - Işık Terapisi", "envanter_kodu": "E-2", "cihaz_adi": "Işık Terapisi", "oda_adi": None,
     "proje_turu": None, "proje_adi_aciklamasi": None,
     "baslangic_zamani": "2026-10-05T09:00:00", "bitis_zamani": "2026-10-06T09:30:00", "durum": "Tamamlandı"},
    {"rezervasyon_id": 3, "cihaz_id": "E-3 - Monitör", "envanter_kodu": "E-3", "cihaz_adi": "Monitör", "oda_adi": "Oda-2",
     "proje_turu": "Test", "proje_adi_aciklamasi": "",
     "baslangic_zamani": "2026-11-21T14:00:00", "bitis_zamani": "2026-11-21T15:00:00", "durum": "İptal Edildi"},
]


def yanit(durum=200, veri=None):
    return SimpleNamespace(status_code=durum, json=lambda: veri)


@pytest.fixture
def modul():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    import client.cihaz_rezervasyon_ekranlari as m
    return m


@pytest.fixture
def ac(modul):
    acilanlar = []

    def olustur(veri=None, yetkili=True):
        with patch.object(modul, "oturum_kontrollu_istek", return_value=yanit(200, REZ if veri is None else veri)):
            e = modul.RezervasyonYonetimEkrani("http://x", "T", yetkili_mi=yetkili)
        acilanlar.append(e)
        return e

    yield olustur
    from PySide6.QtCore import QCoreApplication, QEvent
    for e in acilanlar:
        e.close()
        e.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def hucre(e, satir, sutun):
    return e.tablo.item(satir, sutun).text()


def test_zaman_araligi_ayni_gun_ve_farkli_gun(modul):
    assert modul.zaman_araligi("2026-11-20T10:00:00", "2026-11-20T12:00:00") == "20.11.2026  10:00 – 12:00"
    assert modul.zaman_araligi("2026-10-05T09:00:00", "2026-10-06T09:30:00") == "05.10.2026 09:00  →  06.10.2026 09:30"
    assert modul.zaman_araligi(None, "") == "—"                                       # bozuk veri ekranı bozmaz


def test_satirlar_cihaz_oda_proje_ve_zamani_gosterir(ac):
    e = ac()
    assert e.tablo.rowCount() == 3
    assert hucre(e, 0, 0) == "E-1 · EEG" and hucre(e, 0, 1) == "Psikoloji Bölümü" and hucre(e, 0, 2) == "Oda-1"
    assert hucre(e, 0, 3) == "Araştırma – Pilot çalışma" and hucre(e, 0, 4) == "20.11.2026  10:00 – 12:00"
    assert hucre(e, 1, 1) == "—" and hucre(e, 1, 2) == "—" and hucre(e, 1, 3) == "—"      # bölüm/oda/proje girilmemiş
    assert hucre(e, 2, 3) == "Test"                                                      # boş açıklama "–" bırakmaz


def test_eski_sunucu_yanitiyla_da_calisir(ac):
    eski = [{"rezervasyon_id": 9, "cihaz_id": "E-9 - Eski", "baslangic_zamani": "2026-11-20T10:00:00",
             "bitis_zamani": "2026-11-20T11:00:00", "durum": "Aktif"}]
    e = ac(eski)
    assert hucre(e, 0, 0) == "E-9 - Eski" and hucre(e, 0, 1) == "—" and hucre(e, 0, 2) == "—"


def test_sayaclar_durumlari_sayar(ac):
    e = ac()
    assert (e.cip_toplam.text(), e.cip_aktif.text(), e.cip_tamam.text(), e.cip_iptal.text()) == \
        ("3 rezervasyon", "1 aktif", "1 tamamlandı", "1 iptal")
    farkli = [dict(REZ[0], durum="Aktif"), dict(REZ[0], durum="Aktif"), dict(REZ[1]), dict(REZ[2]), dict(REZ[2]), dict(REZ[2])]
    e2 = ac(farkli)                                                                      # sayılar birbirinden farklı: karışıklık yakalanır
    assert (e2.cip_toplam.text(), e2.cip_aktif.text(), e2.cip_tamam.text(), e2.cip_iptal.text()) == \
        ("6 rezervasyon", "2 aktif", "1 tamamlandı", "3 iptal")


def test_arama_cihaz_oda_ve_projeye_gore_suzer_bos_mesaj_gosterir(ac):
    e = ac()
    e.arama.setText("oda-2")
    assert e.tablo.rowCount() == 1 and hucre(e, 0, 0) == "E-3 · Monitör"
    e.arama.setText("psikoloji")                                                         # bölüm adına göre
    assert e.tablo.rowCount() == 1 and hucre(e, 0, 0) == "E-1 · EEG"
    e.arama.setText("pilot")
    assert e.tablo.rowCount() == 1 and hucre(e, 0, 0) == "E-1 · EEG"
    e.arama.setText("yok yok")
    assert e.tablo.rowCount() == 0 and not e.bos_mesaj.isHidden() and e.bos_mesaj.text() == "Aramaya uyan rezervasyon yok."
    e.arama.setText("")
    assert e.tablo.rowCount() == 3 and e.bos_mesaj.isHidden()
    assert e.cip_toplam.text() == "3 rezervasyon"                                        # sayaçlar aramadan etkilenmez


def test_liste_bos_ise_bilgi_mesaji(ac):
    e = ac([])
    assert e.tablo.rowCount() == 0 and not e.bos_mesaj.isHidden() and e.bos_mesaj.text() == "Henüz rezervasyon yok."


def test_iptal_dugmesi_yalniz_aktif_ve_yetkili_icin(ac):
    e = ac()
    assert [e.tablo.cellWidget(i, 6) is not None for i in range(3)] == [True, False, False]
    assert [e.tablo.cellWidget(i, 5) is not None for i in range(3)] == [True, True, True]          # durum etiketi hep var
    assert ac(yetkili=False).tablo.cellWidget(0, 6) is None


def test_iptal_onaylanirsa_istek_gider_ve_liste_yenilenir(modul, ac):
    e = ac()
    assert e.tablo.cellWidget(0, 6) is not None
    istekler = []

    def sahte(yontem, url, **kw):
        istekler.append((yontem, url))
        return yanit(200, REZ if yontem == "GET" else {})

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte), \
         patch.object(modul.IptalOnayKutusu, "exec", return_value=1), \
         patch.object(modul.QMessageBox, "information") as bilgi:
        e.rezervasyon_iptal_et(1)
    assert istekler[0] == ("PATCH", "http://x/api/rezervasyonlar/1/iptal") and istekler[1][0] == "GET"
    bilgi.assert_called_once()


def test_iptalden_vazgecilirse_istek_gitmez(modul, ac):
    e = ac()
    with patch.object(modul, "oturum_kontrollu_istek") as istek, patch.object(modul.IptalOnayKutusu, "exec", return_value=0):
        e.rezervasyon_iptal_et(1)
    istek.assert_not_called()


def test_iptal_reddedilirse_sunucunun_mesaji_gosterilir(modul, ac):
    e = ac()
    ret = yanit(404, {"detail": "Rezervasyon bulunamadı veya yetkiniz yok."})
    with patch.object(modul, "oturum_kontrollu_istek", return_value=ret), \
         patch.object(modul.IptalOnayKutusu, "exec", return_value=1), \
         patch.object(modul.QMessageBox, "warning") as uyari:
        e.rezervasyon_iptal_et(1)
    uyari.assert_called_once()
    assert "bulunamadı" in uyari.call_args.args[2]


def test_onay_ve_form_penceresi_ortak_stili_kullanir(modul, ac):
    from client.tablo_tasarimi import FORM_STIL
    ac()
    kutu = modul.IptalOnayKutusu()
    assert kutu.styleSheet().startswith(FORM_STIL) and kutu.btn_evet.objectName() == "tehlike"
    kutu.close()
    kutu.deleteLater()
    with patch.object(modul.YeniRezervasyonFormu, "verileri_yukle"):
        form = modul.YeniRezervasyonFormu("http://x", "T")
    assert form.styleSheet().startswith(FORM_STIL) and form.btn_kaydet.objectName() == "kaydet"
    form.close()
    form.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


# ----------------------------------------------------------------------------- form: bölüm ve proje türü listeleri
BOLUMLER = [{"bolum_id": 4, "bolum_adi": "Psikoloji Bölümü", "sorumlu_ad_soyad": "Ayşe Y."},
            {"bolum_id": 7, "bolum_adi": "Fizyoloji Bölümü", "sorumlu_ad_soyad": "Can K."}]
TURLER = [{"proje_turu_id": 1, "ad": "Araştırma"}, {"proje_turu_id": 2, "ad": "Test"}]


class SahteSunucu:
    """/api/cihazlar, /api/odalar, /api/bolumler, /api/proje-turleri ve POST uçlarını taklit eder; istekleri kaydeder."""

    def __init__(self, bolumler=None, turler=None, post_durumu=201, post_govde=None):
        self.bolumler = list(BOLUMLER if bolumler is None else bolumler)
        self.turler = list(TURLER if turler is None else turler)
        self.post_durumu, self.post_govde = post_durumu, post_govde
        self.istekler = []

    def __call__(self, yontem, url, **kw):
        self.istekler.append((yontem, url.replace("http://x", ""), kw.get("json")))
        if yontem == "POST":
            if self.post_durumu == 201:
                if url.endswith("/api/bolumler"):
                    self.bolumler.append({"bolum_id": 99, "bolum_adi": kw["json"]["bolum_adi"]})
                    return yanit(201, {"bolum_id": 99, "bolum_adi": kw["json"]["bolum_adi"]})
                if url.endswith("/api/proje-turleri"):
                    self.turler.append({"proje_turu_id": 50, "ad": kw["json"]["ad"]})
                    return yanit(201, {"proje_turu_id": 50, "ad": kw["json"]["ad"]})
            return yanit(self.post_durumu, self.post_govde)
        yol = url.replace("http://x", "")
        veri = {"/api/cihazlar": [{"cihaz_id": 1, "envanter_kodu": "E-1", "cihaz_adi": "EEG", "durum": "Kullanima_Hazir"}],
                "/api/cihaz-odalari": [{"oda_id": 5, "oda_adi": "Cihaz Odası A", "aktif_mi": True}],
                "/api/bolumler": self.bolumler, "/api/proje-turleri": self.turler}[yol]
        return yanit(200, veri)


@pytest.fixture
def form_ac(modul):
    acilanlar = []

    def olustur(sunucu=None):
        sunucu = sunucu or SahteSunucu()
        with patch.object(modul, "oturum_kontrollu_istek", sunucu):
            f = modul.YeniRezervasyonFormu("http://x", "T")
        f._sunucu = sunucu
        acilanlar.append(f)
        return f

    yield olustur
    from PySide6.QtCore import QCoreApplication, QEvent
    for f in acilanlar:
        f.close()
        f.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def kutu_metinleri(kutu):
    return [kutu.itemText(i) for i in range(kutu.count())]


def test_form_bolum_ve_proje_turu_listelerini_veritabanindan_doldurur(form_ac):
    f = form_ac()
    assert kutu_metinleri(f.cmb_bolum) == ["Bölüm seçin", "Psikoloji Bölümü", "Fizyoloji Bölümü"]
    assert f.cmb_bolum.currentData() is None and f.cmb_bolum.itemData(1) == 4
    assert kutu_metinleri(f.cmb_proje_turu) == ["Seçilmedi", "Araştırma", "Test"]
    assert f.btn_yeni_bolum.text() == "＋ Yeni bölüm" and f.btn_yeni_proje_turu.text() == "＋ Yeni tür"
    assert not hasattr(f, "txt_proje_turu")                                              # elle yazma kalktı


def test_form_yalniz_cihaz_odalarini_ister_psikolog_odalarini_degil(form_ac):
    f = form_ac()
    yollar = [yol for _, yol, _ in f._sunucu.istekler]
    assert "/api/cihaz-odalari" in yollar and "/api/odalar" not in yollar            # oda görüntüleme izni gerektirmeyen rezervasyon odaları ucu
    assert kutu_metinleri(f.cmb_oda) == ["Cihaz Odası A"] and f.cmb_oda.currentData() == 5


def test_aktif_oda_yoksa_form_acik_kalir_ve_uyarir(modul, form_ac):
    class OdasizSunucu(SahteSunucu):
        def __call__(self, yontem, url, **kw):
            if url.endswith("/api/cihaz-odalari"):
                self.istekler.append((yontem, "/api/cihaz-odalari", None))
                return yanit(200, [])
            return super().__call__(yontem, url, **kw)

    f = form_ac(OdasizSunucu())
    assert kutu_metinleri(f.cmb_oda) == ["Aktif oda yok"] and f.cmb_oda.currentData() is None
    assert "Oda Yönetimi" in f.cmb_oda.toolTip()


def test_form_liste_alinamazsa_yine_acilir(form_ac):
    class ListeleriVermeyenSunucu(SahteSunucu):
        def __call__(self, yontem, url, **kw):
            if url.endswith(("/api/bolumler", "/api/proje-turleri")):
                return yanit(500)
            return super().__call__(yontem, url, **kw)

    f = form_ac(ListeleriVermeyenSunucu())
    assert kutu_metinleri(f.cmb_bolum) == ["Bölüm seçin"] and kutu_metinleri(f.cmb_proje_turu) == ["Seçilmedi"]
    assert f.cmb_cihaz.count() == 1                                                      # cihaz listesi yine yüklenir
    assert not f.lbl_uyari.isHidden()                                                    # sessiz kalmaz: neden yazılır
    assert "Bölümler alınamadı" in f.lbl_uyari.text() and "Proje türleri alınamadı" in f.lbl_uyari.text()
    assert "Sunucuda bir hata" in f.lbl_uyari.text()


SEMA_YANITI = {"detail": "Veritabanı şeması sunucu sürümüyle uyumlu değil (eksik tablo ya da sütun). "
                         "Sistem yöneticisi güncellemeyi çalıştırmalı: python -m alembic upgrade head", "kod": "SEMA_UYUMSUZ"}


class TabloYokSunucu(SahteSunucu):
    """proje_turleri tablosu yokken (migrasyon çalıştırılmamış) sunucunun verdiği yanıtı taklit eder."""

    def __call__(self, yontem, url, **kw):
        if url.endswith("/api/proje-turleri"):
            self.istekler.append((yontem, "/api/proje-turleri", kw.get("json")))
            return yanit(503, SEMA_YANITI)
        return super().__call__(yontem, url, **kw)


def test_liste_sorunsuzsa_uyari_gorunmez(form_ac):
    f = form_ac()
    assert f.lbl_uyari.isHidden() and f.lbl_uyari.text() == ""


def test_migrasyon_calismamissa_uyari_ne_yapilacagini_soyler(form_ac):
    f = form_ac(TabloYokSunucu())
    metin = f.lbl_uyari.text()
    assert not f.lbl_uyari.isHidden()
    assert "Proje türleri alınamadı" in metin and "python -m alembic upgrade head" in metin
    assert "Bölümler" not in metin and "Odalar" not in metin                             # yalnızca bozuk liste anılır
    assert kutu_metinleri(f.cmb_bolum) == ["Bölüm seçin", "Psikoloji Bölümü", "Fizyoloji Bölümü"]    # diğer listeler yine dolu


def test_yeni_tur_eklenirken_tablo_yoksa_sema_mesaji_gosterilir(modul, form_ac):
    sunucu = TabloYokSunucu()
    f = form_ac(sunucu)
    with pencere_doldur(modul, modul.YeniProjeTuruPenceresi, txt_ad="Staj"), \
         patch.object(modul, "oturum_kontrollu_istek", sunucu), patch.object(modul.QMessageBox, "warning") as uyari:
        f.yeni_proje_turu_ekle()
    uyari.assert_called_once()
    assert "alembic upgrade head" in uyari.call_args.args[2]


def test_oda_listesi_alinamazsa_uyari_yazilir(form_ac):
    class OdaYetkisiz(SahteSunucu):
        def __call__(self, yontem, url, **kw):
            if url.endswith("/api/cihaz-odalari"):
                return yanit(403)
            return super().__call__(yontem, url, **kw)

    f = form_ac(OdaYetkisiz())
    assert kutu_metinleri(f.cmb_oda) == ["Odalar alınamadı"]
    assert "Odalar alınamadı" in f.lbl_uyari.text() and "yetki" in f.lbl_uyari.text()


def test_liste_istegi_baglanti_hatasi_verirse_uyari_yazilir_form_acilir(modul, form_ac):
    import requests

    class Kopuk(SahteSunucu):
        def __call__(self, yontem, url, **kw):
            if url.endswith("/api/bolumler"):
                raise requests.exceptions.ConnectionError("gizli ayrıntı")
            return super().__call__(yontem, url, **kw)

    f = form_ac(Kopuk())
    assert "Bölümler alınamadı" in f.lbl_uyari.text() and "Sunucuya bağlanılamadı" in f.lbl_uyari.text()
    assert "gizli ayrıntı" not in f.lbl_uyari.text()
    assert kutu_metinleri(f.cmb_proje_turu) == ["Seçilmedi", "Araştırma", "Test"]          # sonraki liste yine yüklenir


def test_sorun_giderilince_uyari_kalkar(modul, form_ac):
    f = form_ac(TabloYokSunucu())
    assert not f.lbl_uyari.isHidden()
    with patch.object(modul, "oturum_kontrollu_istek", SahteSunucu()):                    # migrasyon çalıştırıldı
        f.proje_turlerini_yukle()
    assert f.lbl_uyari.isHidden() and f.lbl_uyari.text() == ""
    assert kutu_metinleri(f.cmb_proje_turu) == ["Seçilmedi", "Araştırma", "Test"]


def test_form_kaydi_bolum_ve_proje_turuyle_gonderir(modul, form_ac):
    f = form_ac()
    f.cmb_bolum.setCurrentIndex(2)
    f.cmb_proje_turu.setCurrentIndex(1)
    f.txt_proje_aciklama.setPlainText("Beyin dalgası")
    from PySide6.QtCore import QDate
    f.dt_baslangic_tarih.setMinimumDate(QDate(2020, 1, 1))
    gelecek = QDate.currentDate().addDays(5)
    f.dt_baslangic_tarih.setDate(gelecek)
    f.dt_bitis_tarih.setDate(gelecek)
    gonderilen = {}

    def sahte(parent, yontem, url, veri, basliklar, *a):
        gonderilen.update(veri)
        return yanit(201, {})
    with patch.object(modul, "cakisma_cozumlu_istek", side_effect=sahte), patch.object(modul.QMessageBox, "exec", return_value=0):
        f.kaydet()
    assert gonderilen["bolum_id"] == 7 and gonderilen["proje_turu"] == "Araştırma" and gonderilen["cihaz_id"] == 1
    assert gonderilen["proje_adi_aciklamasi"] == "Beyin dalgası"


def test_bolum_secilmeden_kayit_gitmez(modul, form_ac):
    f = form_ac()
    with patch.object(modul, "cakisma_cozumlu_istek") as istek, patch.object(modul.QMessageBox, "warning") as uyari:
        f.kaydet()
    istek.assert_not_called()
    uyari.assert_called_once()
    assert "bölümü seçin" in uyari.call_args.args[2]


def test_proje_turu_secilmezse_bos_gonderilir(modul, form_ac):
    f = form_ac()
    f.cmb_bolum.setCurrentIndex(1)
    from PySide6.QtCore import QDate
    gelecek = QDate.currentDate().addDays(5)
    f.dt_baslangic_tarih.setDate(gelecek)
    f.dt_bitis_tarih.setDate(gelecek)
    gonderilen = {}
    with patch.object(modul, "cakisma_cozumlu_istek", side_effect=lambda p, y, u, v, b, *a: gonderilen.update(v) or yanit(201, {})), \
         patch.object(modul.QMessageBox, "exec", return_value=0):
        f.kaydet()
    assert gonderilen["proje_turu"] == "" and gonderilen["bolum_id"] == 4


def pencere_doldur(modul, sinif, **alanlar):
    def exec_(self):
        for ad, deger in alanlar.items():
            getattr(self, ad).setText(deger)
        return 1 if self.eksik_alan() is None else 0
    return patch.object(sinif, "exec", exec_)


def test_yeni_bolum_kaydedilir_listeye_duser_ve_secili_gelir(modul, form_ac):
    f = form_ac()
    with pencere_doldur(modul, modul.YeniBolumPenceresi, txt_ad=" Nöroloji Bölümü ", txt_sorumlu="Zeynep T.", txt_iletisim=""), \
         patch.object(modul, "oturum_kontrollu_istek", f._sunucu):
        f.yeni_bolum_ekle()
    yontem, yol, govde = next(i for i in f._sunucu.istekler if i[0] == "POST")
    assert (yontem, yol) == ("POST", "/api/bolumler")
    assert govde == {"bolum_adi": "Nöroloji Bölümü", "sorumlu_ad_soyad": "Zeynep T.", "iletisim_bilgisi": None}
    assert f.cmb_bolum.currentText() == "Nöroloji Bölümü" and f.cmb_bolum.currentData() == 99


def test_yeni_proje_turu_kaydedilir_listeye_duser_ve_secili_gelir(modul, form_ac):
    f = form_ac()
    f.cmb_proje_turu.setCurrentIndex(2)                                                  # önceki seçim: Test
    with pencere_doldur(modul, modul.YeniProjeTuruPenceresi, txt_ad="Staj"), patch.object(modul, "oturum_kontrollu_istek", f._sunucu):
        f.yeni_proje_turu_ekle()
    assert ("POST", "/api/proje-turleri", {"ad": "Staj"}) in f._sunucu.istekler
    assert "Staj" in kutu_metinleri(f.cmb_proje_turu) and f.cmb_proje_turu.currentText() == "Staj"


def test_yeni_kayit_penceresi_bos_alanla_kaydedilmez(modul, form_ac):
    f = form_ac()
    with pencere_doldur(modul, modul.YeniBolumPenceresi, txt_ad="Bölüm", txt_sorumlu="  "), \
         patch.object(modul, "oturum_kontrollu_istek", f._sunucu):
        f.yeni_bolum_ekle()
    assert not [i for i in f._sunucu.istekler if i[0] == "POST"]
    assert kutu_metinleri(f.cmb_bolum) == ["Bölüm seçin", "Psikoloji Bölümü", "Fizyoloji Bölümü"]


def test_yeni_kayit_reddedilirse_mesaj_gosterilir_liste_degismez(modul, form_ac):
    f = form_ac()
    sunucu = SahteSunucu(post_durumu=409, post_govde={"detail": "Bu proje türü zaten mevcut."})
    sunucu.istekler = f._sunucu.istekler
    with pencere_doldur(modul, modul.YeniProjeTuruPenceresi, txt_ad="Test"), \
         patch.object(modul, "oturum_kontrollu_istek", sunucu), patch.object(modul.QMessageBox, "warning") as uyari:
        f.yeni_proje_turu_ekle()
    uyari.assert_called_once()
    assert "zaten mevcut" in uyari.call_args.args[2]
    assert kutu_metinleri(f.cmb_proje_turu) == ["Seçilmedi", "Araştırma", "Test"]
