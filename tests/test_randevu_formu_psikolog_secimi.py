"""
Randevu formunda psikolog kutusunun davranışı.

Forma verilen kimlik, giriş yapan KULLANICI kimliğidir (personel_id değil).
- Kullanıcı psikolog listesinde varsa (kendisi psikologsa) kendi adına kilitlenir.
- Admin ve danışma öğrencisi listede olmadığı için psikolog seçebilir.
"""

from unittest.mock import MagicMock, patch

import pytest

import randevu_ekranlari as modul
from randevu_ekranlari import RandevuOlusturFormu

PSIKOLOGLAR = [
    {"personel_id": 3, "ad_soyad": "ali", "kullanici_id": 11},
    {"personel_id": 7, "ad_soyad": "ayse", "kullanici_id": 12},
]
ODALAR = {
    3: [{"oda_id": 1, "oda_adi": "Oda 1", "aktif_mi": True}],
    7: [{"oda_id": 1, "oda_adi": "Oda 1", "aktif_mi": True},
        {"oda_id": 2, "oda_adi": "Oda 2", "aktif_mi": True}],
}


def cevap(veri):
    yanit = MagicMock()
    yanit.status_code = 200
    yanit.json.return_value = veri
    yanit._tkys_oturum_reddedildi = False
    return yanit


def sahte_istek(yontem, url, **kwargs):
    if url.endswith("/api/psikologlar"):
        return cevap(PSIKOLOGLAR)
    if "/api/psikologlar/" in url and url.endswith("/odalar"):
        personel_id = int(url.split("/api/psikologlar/")[1].split("/")[0])
        return cevap(ODALAR[personel_id])
    return cevap([])  # /api/odalar, /api/danisan-kodlari


def form_ac(kullanici_id):
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte_istek):
        return RandevuOlusturFormu("http://testserver", "TOKEN", kullanici_id)


def test_psikolog_kendi_adina_kilitlenir():
    # Forma giriş yapan kişinin PERSONEL kimliği verilir (login_ekrani: personel_id or kullanici_id).
    # Psikolog 'ayse': personel_id 7, kullanici_id 12 (ikisi bilerek farklı).
    form = form_ac(7)
    assert form.cmb_psikologlar.currentData() == 7
    assert not form.cmb_psikologlar.isEnabled()
    assert form.cmb_odalar.count() == 2
    form.close()


@pytest.mark.parametrize("personel_id", [1, 11, 12])
def test_psikolog_olmayan_kullanici_psikolog_secebilir(personel_id):
    # 11 ve 12, psikologların KULLANICI kimlikleridir ama personel kimlikleri değildir.
    # Gerçek hayattaki hata: admin'in personel_id'si 11, psikolog1'in kullanici_id'si 11 idi;
    # kimlikler karışınca admin psikolog1'e kilitleniyor, diğer psikologlar seçilemiyordu.
    form = form_ac(personel_id)
    assert form.cmb_psikologlar.isEnabled()
    form.close()


def test_psikolog_degisince_odalar_o_psikologa_gore_yenilenir():
    form = form_ac(1)
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte_istek):
        form.cmb_psikologlar.setCurrentIndex(form.cmb_psikologlar.findData(7))
    assert form.cmb_odalar.count() == 2
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte_istek):
        form.cmb_psikologlar.setCurrentIndex(form.cmb_psikologlar.findData(3))
    assert form.cmb_odalar.count() == 1
    form.close()
