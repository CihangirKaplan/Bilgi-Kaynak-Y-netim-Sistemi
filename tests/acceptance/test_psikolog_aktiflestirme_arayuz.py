"""Kullanıcı & Personel ekranı: psikolog pasife alınırken / aktifleştirilirken oda kuralları.

- Pasife alma: istek gövdesiz gider; sunucunun 409 uyarısı (planlı randevu vb.) kullanıcıya aynen gösterilir
- Pasif psikolog aktifleştirilirken oda seçme penceresi açılır; seçilen odalar durum isteğiyle gider, iptalde istek atılmaz
- Psikolog olmayan kullanıcıda davranış eskisi gibi (pencere yok, gövde yok)
"""

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

import client.k_personel_ekranlari as modul
from client.k_personel_ekranlari import AktiflestirmeOdaFormu, KullaniciPersonelEkrani


def cevap(veri, durum=200):
    yanit = MagicMock()
    yanit.status_code = durum
    yanit.json.return_value = veri
    yanit.text = str(veri)
    yanit._tkys_oturum_reddedildi = False
    return yanit


PERSONEL = [
    {"personel_id": 9, "kullanici_id": 11, "kullanici_adi": "aktif_psikolog", "personel_kodu": "PER-PSK-001", "rol_adi": "PSIKOLOG",
     "gorunen_ad": "Psikolog", "aktif_mi": True, "olusturulma_tarihi": None},
    {"personel_id": 10, "kullanici_id": 12, "kullanici_adi": "pasif_psikolog", "personel_kodu": "PER-PSK-002", "rol_adi": "PSIKOLOG",
     "gorunen_ad": "Psikolog", "aktif_mi": False, "olusturulma_tarihi": None},
    {"personel_id": 12, "kullanici_id": 14, "kullanici_adi": "pasif_memur", "personel_kodu": "PER-MEM-001", "rol_adi": "MEMUR",
     "gorunen_ad": "Memur", "aktif_mi": False, "olusturulma_tarihi": None},
]
ODALAR = [{"oda_id": 2, "oda_adi": "Görüşme Odası-1", "aktif_mi": True}, {"oda_id": 3, "oda_adi": "Görüşme Odası-2", "aktif_mi": True}]


class Sunucu:
    """PATCH isteklerini kaydeder; liste ve oda uçlarını sahte verilerle yanıtlar."""

    def __init__(self, patch_cevabi=None):
        self.patch_cevabi = patch_cevabi or cevap({"yeni_durum": True})
        self.patch_istekleri = []

    def __call__(self, yontem, url, **kwargs):
        if yontem == "PATCH":
            self.patch_istekleri.append((url, kwargs))
            return self.patch_cevabi
        if url.endswith("/api/personel"):
            return cevap(PERSONEL)
        if url.endswith("/api/odalar"):
            return cevap(ODALAR)
        if url.endswith("/odalar"):
            return cevap({"kullanici_id": 12, "oda_idleri": []})
        return cevap([])


@pytest.fixture
def ekran_ac(tkys_qapplication):
    acilanlar = []

    def ac(sunucu):
        with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
            ekran = KullaniciPersonelEkrani("http://testserver", "TOKEN")
        acilanlar.append(ekran)
        return ekran

    yield ac
    for e in acilanlar:
        e.close()


def satir_sec(ekran, kullanici_adi):
    for satir in range(ekran.tablo.rowCount()):
        if ekran.tablo.item(satir, 1).text() == kullanici_adi:
            ekran.tablo.selectRow(satir)
            return
    raise AssertionError(kullanici_adi)


def durum_degistir(ekran, sunucu, kullanici_adi, onay=QMessageBox.Yes, oda_formu=None):
    satir_sec(ekran, kullanici_adi)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), \
            patch.object(modul.QMessageBox, "question", return_value=onay), \
            patch.object(modul.QMessageBox, "warning") as uyari, \
            patch.object(modul, "basari_bildirimi") as bilgi, \
            patch.object(modul.QMessageBox, "critical") as kritik, \
            patch.object(modul, "AktiflestirmeOdaFormu", return_value=oda_formu) as form_sinifi:
        ekran.secili_kullanici_durum_degistir()
    return uyari, bilgi, kritik, form_sinifi


def sahte_oda_formu(sonuc=QDialog.Accepted, odalar=(2, 3)):
    form = MagicMock()
    form.exec.return_value = sonuc
    form.secilen_odalar = list(odalar)
    return form


def test_aktif_psikolog_pasife_alinirken_istek_govdesiz_gider_pencere_acilmaz(ekran_ac):
    sunucu = Sunucu(cevap({"yeni_durum": False}))
    ekran = ekran_ac(sunucu)
    uyari, bilgi, _, form_sinifi = durum_degistir(ekran, sunucu, "aktif_psikolog")
    (url, kwargs), = sunucu.patch_istekleri
    assert url.endswith("/api/kullanicilar/11/durum-degistir") and "json" not in kwargs
    form_sinifi.assert_not_called()
    bilgi.assert_called_once()
    uyari.assert_not_called()


@pytest.mark.parametrize("durum, detay", [
    (409, "Bu psikologun bugünden sonra 2 planlı randevusu var. Pasife almadan önce bu randevuları iptal edin."),
    (422, "Psikolog aktifleştirilirken en az bir görüşme odası seçilmelidir."),
    (409, "Cihaz rezervasyonu için kullanılan oda psikologa atanamaz: EEG Odası (1 rezervasyon)."),
])
def test_sunucunun_409_ve_422_uyarisi_kullaniciya_aynen_gosterilir(ekran_ac, durum, detay):
    sunucu = Sunucu(cevap({"detail": detay}, durum))
    ekran = ekran_ac(sunucu)
    uyari, bilgi, kritik, _ = durum_degistir(ekran, sunucu, "aktif_psikolog")
    uyari.assert_called_once()
    assert detay in uyari.call_args.args[2]
    bilgi.assert_not_called()
    kritik.assert_not_called()                                                # genel "Sunucu hatası" kutusu çıkmaz


def test_pasif_psikolog_aktiflestirilirken_secilen_odalar_istekle_gider(ekran_ac):
    sunucu = Sunucu()
    ekran = ekran_ac(sunucu)
    form = sahte_oda_formu(odalar=(2, 3))
    uyari, bilgi, _, form_sinifi = durum_degistir(ekran, sunucu, "pasif_psikolog", oda_formu=form)
    assert form_sinifi.call_args.args[2:4] == (12, "pasif_psikolog")
    (url, kwargs), = sunucu.patch_istekleri
    assert url.endswith("/api/kullanicilar/12/durum-degistir") and kwargs["json"] == {"oda_idleri": [2, 3]}
    bilgi.assert_called_once()


def test_oda_secimi_iptal_edilirse_istek_atilmaz(ekran_ac):
    sunucu = Sunucu()
    ekran = ekran_ac(sunucu)
    durum_degistir(ekran, sunucu, "pasif_psikolog", oda_formu=sahte_oda_formu(sonuc=QDialog.Rejected))
    assert sunucu.patch_istekleri == []


def test_onay_verilmezse_oda_penceresi_de_acilmaz(ekran_ac):
    sunucu = Sunucu()
    ekran = ekran_ac(sunucu)
    _, _, _, form_sinifi = durum_degistir(ekran, sunucu, "pasif_psikolog", onay=QMessageBox.No)
    form_sinifi.assert_not_called()
    assert sunucu.patch_istekleri == []


def test_psikolog_olmayan_pasif_kullanici_aktiflestirilirken_pencere_acilmaz_govde_yok(ekran_ac):
    sunucu = Sunucu()
    ekran = ekran_ac(sunucu)
    _, bilgi, _, form_sinifi = durum_degistir(ekran, sunucu, "pasif_memur")
    form_sinifi.assert_not_called()
    (url, kwargs), = sunucu.patch_istekleri
    assert "json" not in kwargs
    bilgi.assert_called_once()


# ------------------------------------------------------------------ oda seçme penceresi
def oda_formu_ac(sunucu):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu):
        return AktiflestirmeOdaFormu("http://testserver", "TOKEN", 12, "pasif_psikolog")


def test_oda_penceresi_odalari_listeler_hicbiri_isaretli_gelmez(tkys_qapplication):
    form = oda_formu_ac(Sunucu())
    assert [form.liste_odalar.item(i).text() for i in range(form.liste_odalar.count())] == ["Görüşme Odası-1", "Görüşme Odası-2"]
    assert form.secilen_oda_idleri() == [] and form.btn_kaydet.text() == "Aktifleştir"
    form.close()


def test_oda_penceresi_oda_secilmeden_kapanmaz_ve_sunucuya_yazmaz(tkys_qapplication):
    sunucu = Sunucu()
    form = oda_formu_ac(sunucu)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu), patch.object(modul.QMessageBox, "warning") as uyari:
        form.kaydet()
    uyari.assert_called_once()
    assert "en az bir" in uyari.call_args.args[2] and form.result() != QDialog.Accepted
    assert form.secilen_odalar == [] and sunucu.patch_istekleri == []
    form.close()


def test_oda_penceresi_secimi_kaydetmeden_cagirana_verir(tkys_qapplication):
    sunucu = Sunucu()
    form = oda_formu_ac(sunucu)
    form.liste_odalar.item(1).setCheckState(Qt.Checked)
    form.liste_odalar.item(0).setCheckState(Qt.Checked)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sunucu) as istek:
        form.kaydet()
    assert form.secilen_odalar == [2, 3] and form.result() == QDialog.Accepted
    istek.assert_not_called()                                                 # oda yetkisi ucuna (PUT) hiç istek gitmez
    form.close()


# ------------------------------------------------------------------ danışan sayısı mesajı
def test_pasife_alinan_danisan_sayisi_basari_mesajinda_gosterilir(ekran_ac):
    sunucu = Sunucu(cevap({"yeni_durum": False, "pasife_alinan_danisan": 3}))
    ekran = ekran_ac(sunucu)
    _, bilgi, _, _ = durum_degistir(ekran, sunucu, "aktif_psikolog")
    mesaj = bilgi.call_args.args[1]
    assert "Pasif duruma getirildi" in mesaj and "3 danışan da pasife alındı." in mesaj


def test_aktif_edilen_danisan_sayisi_basari_mesajinda_gosterilir(ekran_ac):
    sunucu = Sunucu(cevap({"yeni_durum": True, "aktif_edilen_danisan": 2}))
    ekran = ekran_ac(sunucu)
    _, bilgi, _, _ = durum_degistir(ekran, sunucu, "pasif_psikolog", oda_formu=sahte_oda_formu())
    assert "2 danışan yeniden aktif edildi." in bilgi.call_args.args[1]


def test_danisan_sayisi_yoksa_ya_da_sifirsa_mesaj_degismez(ekran_ac):
    for yanit in ({"yeni_durum": False}, {"yeni_durum": False, "pasife_alinan_danisan": 0}):
        sunucu = Sunucu(cevap(yanit))
        ekran = ekran_ac(sunucu)
        _, bilgi, _, _ = durum_degistir(ekran, sunucu, "aktif_psikolog")
        assert "danışan" not in bilgi.call_args.args[1]
