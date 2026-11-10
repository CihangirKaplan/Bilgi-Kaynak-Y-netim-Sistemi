"""
Psikolog oda yetkileri arayüzü.

- Oda Yetkileri penceresi: aktif odalar, mevcut atamalar işaretli, en az bir oda zorunlu
- Kullanıcı & Personel: Rolü sütunu görünen adı gösterir, karşılaştırmalar kodla yapılır
- Randevu formu: atanmış oda yoksa bilgi satırı; odası olan psikologda ilk oda seçili gelir
- Oda Yönetimi: Psikologlar sütunu verisi, 409 mesajı
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

import k_personel_ekranlari as modul
import randevu_ekranlari as randevu_modul
from k_personel_ekranlari import KullaniciPersonelEkrani, OdaYetkileriFormu


def cevap(veri, durum=200):
    yanit = MagicMock()
    yanit.status_code = durum
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


ODALAR = [
    {"oda_id": 1, "oda_adi": "EEG Odası", "kapasite": 1, "aktif_mi": True},
    {"oda_id": 2, "oda_adi": "Görüşme Odası-1", "kapasite": 1, "aktif_mi": True},
    {"oda_id": 3, "oda_adi": "Görüşme Odası-2", "kapasite": 1, "aktif_mi": True},
    {"oda_id": 9, "oda_adi": "Eski Oda", "kapasite": 1, "aktif_mi": False},
]


class Sunucu:
    """oturum_kontrollu_istek yerine geçer; gelen yazma isteklerini kaydeder."""

    def __init__(self, mevcut_odalar=(2,), mevcut_durumu=200, put_cevabi=None):
        self.mevcut_odalar = list(mevcut_odalar)
        self.mevcut_durumu = mevcut_durumu
        self.put_cevabi = put_cevabi or cevap({"durum": "basarili"})
        self.put_istekleri = []

    def __call__(self, yontem, url, **kwargs):
        if yontem == "PUT":
            self.put_istekleri.append((url, kwargs.get("json")))
            return self.put_cevabi
        if url.endswith("/api/odalar"):
            return cevap(ODALAR)
        if url.endswith("/odalar"):  # /api/kullanicilar/{id}/odalar
            if self.mevcut_durumu != 200:
                return cevap({"detail": "Oda yetkisi yalnızca psikolog rolündeki kullanıcılar için tanımlanabilir."},
                             self.mevcut_durumu)
            return cevap({"kullanici_id": 11, "oda_idleri": self.mevcut_odalar})
        return cevap([])


def pencere_ac(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        return OdaYetkileriFormu("http://testserver", "TOKEN", 11, "psikolog1")


def isaretli(form):
    return [form.liste_odalar.item(i).data(Qt.UserRole) for i in range(form.liste_odalar.count())
            if form.liste_odalar.item(i).checkState() == Qt.Checked]


# ------------------------------------------------------------------ Oda Yetkileri penceresi
def test_yalnizca_aktif_odalar_listelenir_mevcut_atamalar_isaretli_gelir():
    form = pencere_ac(Sunucu(mevcut_odalar=[2]))
    adlar = [form.liste_odalar.item(i).text() for i in range(form.liste_odalar.count())]
    assert adlar == ["EEG Odası", "Görüşme Odası-1", "Görüşme Odası-2"]  # pasif oda yok
    assert isaretli(form) == [2]
    assert form.btn_kaydet.isEnabled()
    form.close()


def test_en_az_bir_oda_secilmeden_kaydedilmez():
    sunucu = Sunucu(mevcut_odalar=[2])
    form = pencere_ac(sunucu)
    form.liste_odalar.item(1).setCheckState(Qt.Unchecked)  # tek odayı kaldır
    assert isaretli(form) == []

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()

    uyari.assert_called_once()
    assert "en az bir" in uyari.call_args.args[2]
    assert sunucu.put_istekleri == []  # istek atılmadı
    form.close()


def test_kaydet_secilen_odalari_sunucuya_gonderir():
    sunucu = Sunucu(mevcut_odalar=[2])
    form = pencere_ac(sunucu)
    form.liste_odalar.item(2).setCheckState(Qt.Checked)  # Görüşme Odası-2'yi de ekle

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "information"):
        form.kaydet()

    (url, govde), = sunucu.put_istekleri
    assert url.endswith("/api/kullanicilar/11/odalar")
    assert govde == {"oda_idleri": [2, 3]}
    assert form.result() == QDialog.Accepted
    form.close()


def test_sunucunun_reddi_kullaniciya_gosterilir():
    sunucu = Sunucu(put_cevabi=cevap({"detail": "Seçilen odalardan biri bulunamadı veya aktif değil."}, 422))
    form = pencere_ac(sunucu)

    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(QMessageBox, "warning") as uyari:
        form.kaydet()

    assert "aktif değil" in uyari.call_args.args[2]
    assert form.result() != QDialog.Accepted
    form.close()


def test_odalar_yuklenemezse_kaydet_kapali_kalir():
    with patch.object(QMessageBox, "warning") as uyari:
        form = pencere_ac(Sunucu(mevcut_durumu=422))
    uyari.assert_called_once()
    assert not form.btn_kaydet.isEnabled()
    assert form.liste_odalar.count() == 0
    form.close()


# ------------------------------------------------------------------ Kullanıcı & Personel ekranı
PERSONEL = [
    {"personel_id": 9, "kullanici_id": 11, "kullanici_adi": "psikolog1", "personel_kodu": "PER-PSK-001",
     "rol_adi": "PSIKOLOG", "gorunen_ad": "Psikolog", "aktif_mi": True, "olusturulma_tarihi": None},
    {"personel_id": 12, "kullanici_id": 14, "kullanici_adi": "memur", "personel_kodu": "PER-MEM-001",
     "rol_adi": "MEMUR", "gorunen_ad": "Memur", "aktif_mi": True, "olusturulma_tarihi": None},
    {"personel_id": 11, "kullanici_id": 13, "kullanici_adi": "admin", "personel_kodu": "PER-ADM-001",
     "rol_adi": "ADMIN", "gorunen_ad": "Sistem Admin", "aktif_mi": True, "olusturulma_tarihi": None},
    {"personel_id": 30, "kullanici_id": 40, "kullanici_adi": "eski_kayit", "personel_kodu": "PER-X-001",
     "rol_adi": "MUDUR", "aktif_mi": True, "olusturulma_tarihi": None},  # gorunen_ad gelmeyen eski cevap
]


def personel_ekrani():
    def sahte(yontem, url, **kwargs):
        return cevap(PERSONEL if url.endswith("/api/personel") else [])
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte):
        return KullaniciPersonelEkrani("http://testserver", "TOKEN")


def satir_sec(ekran, kullanici_adi):
    for satir in range(ekran.tablo.rowCount()):
        if ekran.tablo.item(satir, 1).text() == kullanici_adi:
            ekran.tablo.selectRow(satir)
            return satir
    raise AssertionError(kullanici_adi)


def test_rol_sutunu_gorunen_adi_gosterir_kodu_arkada_tutar():
    ekran = personel_ekrani()
    gorunenler = [ekran.tablo.item(i, 3).text() for i in range(ekran.tablo.rowCount())]
    kodlar = [ekran.tablo.item(i, 3).data(Qt.UserRole) for i in range(ekran.tablo.rowCount())]
    assert gorunenler == ["Psikolog", "Memur", "Sistem Admin", "MUDUR"]  # sonuncuda gorunen_ad yok: koda düşer
    assert kodlar == ["PSIKOLOG", "MEMUR", "ADMIN", "MUDUR"]
    ekran.close()


def test_rol_degistirme_formuna_gorunen_ad_degil_rol_kodu_gider():
    """RolDegistirFormu 'zaten bu rolde' kontrolünü kodla yapar; ekranda görünen ad onu bozmamalı."""
    ekran = personel_ekrani()
    satir_sec(ekran, "admin")
    with patch.object(modul, "RolDegistirFormu") as form_sinifi:
        form_sinifi.return_value.exec.return_value = QDialog.Rejected
        ekran.secili_kullanici_rol_degistir()
    assert form_sinifi.call_args.args[4] == "ADMIN"
    ekran.close()


def test_oda_yetkileri_secim_yoksa_uyarir():
    ekran = personel_ekrani()
    with patch.object(QMessageBox, "warning") as uyari, patch.object(modul, "OdaYetkileriFormu") as form_sinifi:
        ekran.secili_kullanici_oda_yetkileri()
    uyari.assert_called_once()
    form_sinifi.assert_not_called()
    ekran.close()


@pytest.mark.parametrize("kullanici_adi", ["memur", "admin"])
def test_oda_yetkileri_psikolog_olmayana_acilmaz(kullanici_adi):
    ekran = personel_ekrani()
    satir_sec(ekran, kullanici_adi)
    with patch.object(QMessageBox, "information") as bilgi, patch.object(modul, "OdaYetkileriFormu") as form_sinifi:
        ekran.secili_kullanici_oda_yetkileri()
    bilgi.assert_called_once()
    assert "psikolog" in bilgi.call_args.args[2]
    form_sinifi.assert_not_called()
    ekran.close()


def test_oda_yetkileri_psikolog_icin_pencereyi_acar():
    ekran = personel_ekrani()
    satir_sec(ekran, "psikolog1")
    with patch.object(modul, "OdaYetkileriFormu") as form_sinifi:
        ekran.secili_kullanici_oda_yetkileri()
    assert form_sinifi.call_args.args[:4] == ("http://testserver", "TOKEN", 11, "psikolog1")
    form_sinifi.return_value.exec.assert_called_once()
    ekran.close()


# ------------------------------------------------------------------ Randevu formu: atanmış oda yok / ilk oda seçili
PSIKOLOGLAR = [
    {"personel_id": 3, "ad_soyad": "odasiz", "kullanici_id": 11},
    {"personel_id": 7, "ad_soyad": "odali", "kullanici_id": 12},
]
PSIKOLOG_ODALARI = {
    3: [],
    7: [{"oda_id": 1, "oda_adi": "Oda 1", "aktif_mi": True}, {"oda_id": 2, "oda_adi": "Oda 2", "aktif_mi": True}],
}


def randevu_istegi(yontem, url, **kwargs):
    if url.endswith("/api/psikologlar"):
        return cevap(PSIKOLOGLAR)
    if "/api/psikologlar/" in url and url.endswith("/odalar"):
        return cevap(PSIKOLOG_ODALARI[int(url.split("/api/psikologlar/")[1].split("/")[0])])
    if url.endswith("/api/randevular/doluluk"):
        return cevap({"dolu_araliklar": []})
    return cevap([])


@pytest.mark.parametrize("sinif_adi", ["RandevuOlusturFormu", "RandevuDuzenleFormu"])
def test_atanmis_oda_yoksa_bilgi_satiri_gorunur_odasi_olanda_ilk_oda_secilir(sinif_adi):
    with patch.object(randevu_modul, "oturum_kontrollu_istek", side_effect=randevu_istegi):
        if sinif_adi == "RandevuOlusturFormu":
            form = randevu_modul.RandevuOlusturFormu("http://testserver", "TOKEN", None)
        else:
            eski = {"danisan_kod_id": "DAN-2026-0001", "psikolog_id": 3, "oda_id": 1,
                    "baslangic_zamani": "2026-12-01T10:00:00", "bitis_zamani": "2026-12-01T11:00:00"}
            form = randevu_modul.RandevuDuzenleFormu("http://testserver", "TOKEN", None, 42, eski)

        # Odası olmayan psikolog: sessiz boş liste yerine açıklama
        form.cmb_psikologlar.setCurrentIndex(form.cmb_psikologlar.findData(3))
        assert form.cmb_odalar.count() == 1
        assert form.cmb_odalar.itemText(0) == "Bu psikoloğa atanmış oda yok"
        assert form.cmb_odalar.currentData() is None            # kaydetmeye çalışınca "oda seçiniz" uyarısı çıkar
        assert not form.cmb_odalar.model().item(0).isEnabled()

        # Odası olan psikolog: ilk oda kendiliğinden seçili (yer tutucu kullanılırsa Qt bunu yapmaz)
        form.cmb_psikologlar.setCurrentIndex(form.cmb_psikologlar.findData(7))
        assert form.cmb_odalar.count() == 2
        assert form.cmb_odalar.currentData() == 1
    form.close()


# ------------------------------------------------------------------ Oda Yönetimi
def test_409_mesaji_sunucunun_aciklamasini_gosterir():
    from oda_yonetimi import _409_mesaji
    yanit = cevap({"detail": "Bu oda şu psikologların tek aktif odası: a, b."}, 409)
    assert _409_mesaji(yanit) == "Bu oda şu psikologların tek aktif odası: a, b."


@pytest.mark.parametrize("govde", [{}, {"detail": ""}, {"detail": ["liste"]}, {"detail": None}])
def test_409_mesaji_aciklama_yoksa_ad_cakismasi_der(govde):
    from oda_yonetimi import _409_mesaji
    assert _409_mesaji(cevap(govde, 409)) == "Bu isimde bir oda zaten mevcut!"


def test_409_mesaji_json_okunamazsa_ad_cakismasi_der():
    from oda_yonetimi import _409_mesaji
    yanit = MagicMock()
    yanit.json.side_effect = ValueError("json degil")
    assert _409_mesaji(yanit) == "Bu isimde bir oda zaten mevcut!"


def ana_pencere_gibi():
    return SimpleNamespace(api_url="http://testserver", token="TOKEN")


def test_oda_tablosu_psikolog_verisi_odaya_gore_sozluk_olur():
    import main_window as mw
    yanit = cevap([{"oda_id": 2, "psikologlar": ["psikolog1", "psikolog2"]}, {"oda_id": 3, "psikologlar": ["reyhan"]}])
    with patch.object(mw, "oturum_kontrollu_istek", return_value=yanit):
        sonuc = mw.AnaPencere.oda_psikolog_atamalarini_getir(ana_pencere_gibi())
    assert sonuc == {2: "psikolog1, psikolog2", 3: "reyhan"}


@pytest.mark.parametrize("yanit", [cevap({"detail": "yetki yok"}, 403), cevap([], 500)])
def test_oda_tablosu_psikolog_verisi_alinamazsa_bos_sozluk(yanit):
    import main_window as mw
    with patch.object(mw, "oturum_kontrollu_istek", return_value=yanit):
        assert mw.AnaPencere.oda_psikolog_atamalarini_getir(ana_pencere_gibi()) == {}


def test_oda_tablosu_psikolog_verisi_baglanti_hatasinda_bos_sozluk():
    import main_window as mw
    with patch.object(mw, "oturum_kontrollu_istek", side_effect=OSError("sunucu yok")):
        assert mw.AnaPencere.oda_psikolog_atamalarini_getir(ana_pencere_gibi()) == {}
