"""
Randevu formlarında dolu saatlerin gösterimi.

- Dolu saat soluk ve seçilemez olur, etiketinde dolu olanın türü yazar.
- Seçili saat dolu çıkarsa ilk boş saate geçilir; hiç boş yoksa kaydedilmez.
- Sunucuya ulaşılamazsa hiçbir saat kapatılmaz (son karar sunucudadır).
- Düzenleme formu kendi randevusunu "dolu" saymaz.
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

import randevu_ekranlari as modul
from randevu_ekranlari import (
    SAAT_LISTESI,
    RandevuDuzenleFormu,
    RandevuOlusturFormu,
    dolu_saatleri_hesapla,
)

TARIH = "2026-12-01"
PSIKOLOGLAR = [{"personel_id": 3, "ad_soyad": "ali", "kullanici_id": 11}]
ODALAR = [{"oda_id": 1, "oda_adi": "Oda 1", "aktif_mi": True}]


def aralik(bas, bit, sebep="oda"):
    return {"baslangic": f"{TARIH}T{bas}:00", "bitis": f"{TARIH}T{bit}:00", "sebep": sebep}


# ------------------------------------------------------------------ saf hesaplama
def test_aralik_sinirlari_komsu_saati_kapatmaz():
    dolu = dolu_saatleri_hesapla([aralik("10:00", "11:00")], TARIH)
    assert dolu == {"10:00": "oda"}


def test_cok_saatlik_aralik_tum_dilimleri_kapatir():
    dolu = dolu_saatleri_hesapla([aralik("10:30", "12:30", "psikolog")], TARIH)
    assert dolu == {"10:00": "psikolog", "11:00": "psikolog", "12:00": "psikolog"}


def test_ayni_saatte_oda_ve_psikolog_dolu_ise_birlesik_sebep():
    dolu = dolu_saatleri_hesapla(
        [aralik("10:00", "11:00", "oda"), aralik("10:00", "11:00", "psikolog")], TARIH
    )
    assert dolu == {"10:00": "oda_ve_psikolog"}


def test_bozuk_aralik_yok_sayilir():
    assert dolu_saatleri_hesapla([{"baslangic": "bozuk"}, {}], TARIH) == {}


def test_hic_aralik_yoksa_hepsi_bos():
    assert dolu_saatleri_hesapla([], TARIH) == {}


# ------------------------------------------------------------------ form
class Sunucu:
    """oturum_kontrollu_istek yerine geçer; doluluk cevabını ve gelen istekleri tutar."""

    def __init__(self, araliklar=(), doluluk_durumu=200):
        self.araliklar = list(araliklar)
        self.doluluk_durumu = doluluk_durumu
        self.doluluk_istekleri = []
        self.diger_istekler = []

    @staticmethod
    def cevap(veri, durum=200):
        yanit = MagicMock()
        yanit.status_code = durum
        yanit.json.return_value = veri
        yanit._tkys_oturum_reddedildi = False
        return yanit

    def __call__(self, yontem, url, **kwargs):
        if url.endswith("/api/randevular/doluluk"):
            self.doluluk_istekleri.append(kwargs.get("params"))
            if self.doluluk_durumu != 200:
                return self.cevap({"detail": "hata"}, self.doluluk_durumu)
            return self.cevap({"tarih": TARIH, "dolu_araliklar": self.araliklar})
        if url.endswith("/api/psikologlar"):
            return self.cevap(PSIKOLOGLAR)
        if "/api/psikologlar/" in url and url.endswith("/odalar"):
            return self.cevap(ODALAR)
        if url.endswith("/api/danisan-kodlari"):
            return self.cevap([{"danisan_kod_id": "DAN-2026-0001"}])
        if yontem == "GET":
            return self.cevap([])  # /api/odalar gibi alakasız okumalar
        self.diger_istekler.append((yontem, url, kwargs))  # yalnızca yazma istekleri (POST/PATCH)
        return self.cevap({"durum": "basarili"}, 201)


def olustur_formu(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form = RandevuOlusturFormu("http://testserver", "TOKEN", None)
        form.dt_tarih.setDate(QDate(2026, 12, 1))
        form.doluluk_yenile()
    return form


def etiketler(form):
    return [form.cmb_saat.itemText(i) for i in range(form.cmb_saat.count())]


def aktif_mi(form, saat):
    return form.cmb_saat.model().item(form.cmb_saat.findData(saat)).isEnabled()


def renk(form, saat):
    return form.cmb_saat.model().item(form.cmb_saat.findData(saat)).foreground().color().name()


def test_dolu_saatler_soluk_ve_secilemez_etiketlenir():
    sunucu = Sunucu([aralik("10:00", "11:00", "oda"), aralik("13:00", "14:00", "psikolog")])
    form = olustur_formu(sunucu)

    assert not aktif_mi(form, "10:00")
    assert not aktif_mi(form, "13:00")
    assert "Oda dolu" in form.cmb_saat.itemText(form.cmb_saat.findData("10:00"))
    assert "Psikolog dolu" in form.cmb_saat.itemText(form.cmb_saat.findData("13:00"))
    for saat in ("09:00", "11:00", "12:00", "14:00", "15:00"):
        assert aktif_mi(form, saat)
        assert form.cmb_saat.itemText(form.cmb_saat.findData(saat)) == saat
    # Dolu saatler soluk (gri), boş saatler normal renkte görünür.
    assert renk(form, "10:00") == "#94a3b8" and renk(form, "13:00") == "#94a3b8"
    assert renk(form, "11:00") == "#0f2552"
    form.close()


def test_saat_listesi_standart_ciziciyi_kullanir():
    """Varsayılan çizici soluk rengi göstermez; dolu saatlerin gri görünmesi bu çiziciye bağlıdır."""
    form = olustur_formu(Sunucu())
    assert type(form.cmb_saat.itemDelegate()).__name__ == "QStyledItemDelegate"
    form.close()


def test_istek_secilen_tarih_oda_ve_psikologu_gonderir():
    sunucu = Sunucu()
    form = olustur_formu(sunucu)
    assert sunucu.doluluk_istekleri[-1] == {"tarih": TARIH, "oda_id": 1, "psikolog_id": 3}
    form.close()


def test_secili_saat_dolu_cikarsa_ilk_bos_saate_gecilir():
    form = olustur_formu(Sunucu([aralik("09:00", "11:00")]))
    assert form.saat_secimi() == "11:00"
    form.close()


def test_hic_bos_saat_yoksa_secim_bos_ve_kaydedilmez():
    sunucu = Sunucu([aralik("09:00", "16:00")])
    form = olustur_formu(sunucu)
    assert form.saat_secimi() is None
    assert form.cmb_saat.currentIndex() == -1

    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0001"))
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.QMessageBox, "warning") as uyari:
        form.randevuyu_kaydet()

    uyari.assert_called_once()
    assert sunucu.diger_istekler == []  # POST atılmadı
    form.close()


def test_bos_saatle_kayit_sunucuya_dogru_saatle_gider():
    sunucu = Sunucu([aralik("09:00", "10:00")])
    form = olustur_formu(sunucu)
    form.cmb_danisan_kodu.setCurrentIndex(form.cmb_danisan_kodu.findData("DAN-2026-0001"))

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.QMessageBox, "information"):
        form.randevuyu_kaydet()

    (yontem, url, kwargs), = sunucu.diger_istekler
    assert yontem == "POST" and url.endswith("/api/randevular")
    assert kwargs["json"]["baslangic_zamani"] == f"{TARIH}T10:00:00"
    assert kwargs["json"]["bitis_zamani"] == f"{TARIH}T11:00:00"
    form.close()


@pytest.mark.parametrize("durum", [403, 500])
def test_sunucu_hatasinda_hicbir_saat_kapatilmaz(durum):
    form = olustur_formu(Sunucu([aralik("10:00", "11:00")], doluluk_durumu=durum))
    assert all(aktif_mi(form, saat) for saat in SAAT_LISTESI)
    assert etiketler(form) == SAAT_LISTESI
    form.close()


def test_baglanti_hatasinda_hicbir_saat_kapatilmaz():
    sunucu = Sunucu([aralik("10:00", "11:00")])

    def kopuk(yontem, url, **kwargs):
        if url.endswith("/api/randevular/doluluk"):
            raise OSError("sunucu yok")
        return sunucu(yontem, url, **kwargs)

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=kopuk):
        form = RandevuOlusturFormu("http://testserver", "TOKEN", None)
        form.doluluk_yenile()
    assert all(aktif_mi(form, saat) for saat in SAAT_LISTESI)
    form.close()


def test_tarih_degisince_yeniden_planlanir_ve_yenilenir():
    sunucu = Sunucu()
    form = olustur_formu(sunucu)
    onceki = len(sunucu.doluluk_istekleri)
    form.dt_tarih.setDate(QDate(2026, 12, 2))
    assert form._doluluk_zamanlayici.isActive()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.doluluk_yenile()
    assert sunucu.doluluk_istekleri[onceki]["tarih"] == "2026-12-02"
    form.close()


# ------------------------------------------------------------------ düzenleme formu
ESKI_VERILER = {
    "danisan_kod_id": "DAN-2026-0001",
    "psikolog_id": 3,
    "oda_id": 1,
    "baslangic_zamani": f"{TARIH}T10:00:00",
    "bitis_zamani": f"{TARIH}T11:00:00",
    "durum": "PLANLANDI",
}


def duzenle_formu(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form = RandevuDuzenleFormu("http://testserver", "TOKEN", None, 42, ESKI_VERILER)
        form.doluluk_yenile()
    return form


def test_duzenleme_formu_kendi_randevusunu_haric_tutar():
    sunucu = Sunucu([aralik("13:00", "14:00")])  # sunucu 42 numaralıyı zaten çıkarmıştır
    form = duzenle_formu(sunucu)

    assert sunucu.doluluk_istekleri[-1]["haric_randevu_id"] == 42
    assert form.cmb_saat.currentData() == "10:00"   # eski saat bulundu ve seçili
    assert aktif_mi(form, "10:00")
    assert not aktif_mi(form, "13:00")
    form.close()


def test_duzenleme_formu_dolu_saate_kaydetmez():
    sunucu = Sunucu([aralik("09:00", "16:00")])
    form = duzenle_formu(sunucu)
    assert form.saat_secimi() is None

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.QMessageBox, "warning") as uyari:
        form.randevuyu_guncelle()

    uyari.assert_called_once()
    assert sunucu.diger_istekler == []  # PATCH atılmadı
    form.close()


@pytest.mark.parametrize("durum", [403, 500])
def test_doluluk_hatasinda_kaydet_pasif_ve_uyari_gorunur(durum):
    sunucu = Sunucu([], doluluk_durumu=durum)
    form = olustur_formu(sunucu)

    assert not form.btn_kaydet.isEnabled()
    assert not form.lbl_doluluk_hatasi.isHidden()
    assert "doğrulanamadı" in form.lbl_doluluk_hatasi.text()

    form.close()


def test_doluluk_sunucusu_duzelince_kaydet_aktiflesir():
    sunucu = Sunucu([], doluluk_durumu=500)
    form = olustur_formu(sunucu)

    assert not form.btn_kaydet.isEnabled()

    sunucu.doluluk_durumu = 200
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.doluluk_yenile()

    assert form.btn_kaydet.isEnabled()
    assert form.lbl_doluluk_hatasi.isHidden()

    form.close()


def test_doluluk_dogrulanmadan_post_gonderilmez():
    sunucu = Sunucu([], doluluk_durumu=500)
    form = olustur_formu(sunucu)

    with patch.object(modul.QMessageBox, "warning") as uyari, \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.randevuyu_kaydet()

    uyari.assert_called_once()
    assert sunucu.diger_istekler == []

    form.close()


@pytest.mark.parametrize("durum", [403, 500])
def test_form_listesi_http_hatasinda_kayit_engellenir(durum):
    sunucu = Sunucu([])
    form = olustur_formu(sunucu)

    assert form.btn_kaydet.isEnabled()

    def hata(yontem, url, **kwargs):
        if url.endswith("/api/odalar"):
            return Sunucu.cevap({"detail": "hata"}, durum)
        return sunucu(yontem, url, **kwargs)

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=hata):
        form.odalari_yukle()

    assert not form.btn_kaydet.isEnabled()
    assert not form.lbl_form_hatasi.isHidden()
    assert "Gerekli bilgiler yüklenemedi" in form.lbl_form_hatasi.text()

    form.close()


def test_form_listesi_baglanti_hatasinda_kayit_engellenir():
    sunucu = Sunucu([])
    form = olustur_formu(sunucu)

    def kopuk(yontem, url, **kwargs):
        if url.endswith("/api/odalar"):
            raise OSError("Sunucuya ulasilamadi")
        return sunucu(yontem, url, **kwargs)

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=kopuk):
        form.odalari_yukle()

    assert not form.btn_kaydet.isEnabled()
    assert not form.lbl_form_hatasi.isHidden()

    form.close()


def test_form_listesi_duzelince_kayit_yeniden_etkinlesir():
    sunucu = Sunucu([])
    form = olustur_formu(sunucu)

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=Sunucu.cevap({"detail": "hata"}, 500)
    ):
        form.odalari_yukle()

    assert not form.btn_kaydet.isEnabled()

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.odalari_yukle()

    assert form.btn_kaydet.isEnabled()
    assert form.lbl_form_hatasi.isHidden()

    form.close()


def test_form_listesi_gecersiz_200_yanitinda_kayit_engellenir():
    sunucu = Sunucu([])
    form = olustur_formu(sunucu)

    assert form.btn_kaydet.isEnabled()

    with patch.object(
        modul,
        "oturum_kontrollu_istek",
        return_value=Sunucu.cevap({"beklenmeyen": "veri"}, 200),
    ):
        form.odalari_yukle()

    assert not form.btn_kaydet.isEnabled()
    assert not form.lbl_form_hatasi.isHidden()
    assert "beklenmeyen veri" in form.lbl_form_hatasi.text()

    form.close()


def test_form_listesi_hatasinda_dogrudan_post_engellenir():
    sunucu = Sunucu([])
    form = olustur_formu(sunucu)

    assert form._doluluk_dogrulandi

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=Sunucu.cevap({"detail": "hata"}, 500),
    ):
        form.odalari_yukle()

    assert form._doluluk_dogrulandi
    assert form._form_hatalari

    with patch.object(modul.QMessageBox, "warning") as uyari, \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.randevuyu_kaydet()

    uyari.assert_called_once()
    assert sunucu.diger_istekler == []

    form.close()


@pytest.mark.parametrize("durum", [403, 500])
def test_duzenleme_formu_liste_hatasinda_patch_engellenir(durum):
    sunucu = Sunucu([])
    form = duzenle_formu(sunucu)

    assert form._doluluk_dogrulandi
    assert form.btn_guncelle.isEnabled()

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=Sunucu.cevap({"detail": "hata"}, durum),
    ):
        form.odalari_yukle()

    assert not form.btn_guncelle.isEnabled()
    assert not form.lbl_form_hatasi.isHidden()

    with patch.object(modul.QMessageBox, "warning") as uyari, \
         patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        form.randevuyu_guncelle()

    uyari.assert_called_once()
    assert sunucu.diger_istekler == []
    form.close()


def test_duzenleme_formu_liste_duzelince_guncelleme_acilir():
    sunucu = Sunucu([])
    form = duzenle_formu(sunucu)

    with patch.object(
        modul, "oturum_kontrollu_istek",
        return_value=Sunucu.cevap({"detail": "hata"}, 500),
    ):
        form.odalari_yukle()

    assert not form.btn_guncelle.isEnabled()

    with patch.object(
        modul, "oturum_kontrollu_istek", side_effect=sunucu
    ):
        form.odalari_yukle()

    assert form.btn_guncelle.isEnabled()
    assert form.lbl_form_hatasi.isHidden()
    form.close()
