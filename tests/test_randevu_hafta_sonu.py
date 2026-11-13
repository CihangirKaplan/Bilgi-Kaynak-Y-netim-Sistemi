"""
Hafta sonu randevu verilemez (kurum hafta sonu kapalı).

- Sunucu asıl korumadır: oluşturma ve zaman değiştiren güncelleme cumartesi/pazar için 422 döner (veritabanına gitmeden).
- Randevu formu: hafta sonu seçilirse saat listesi kapanır, uyarı çıkar, Kaydet kapanır; form hafta sonu açılırsa tarih
  sonraki pazartesiye ayarlanır; takvimde cumartesi/pazar sönük görünür.
- Eskiden kalan hafta sonu randevularının yalnızca zamanı olmayan alanları (oda, danışan) değişebilir.
- Satır sonu (\\n) hataları: etiketlerde harfiyen "\\n" yazısı görünmez.

Sabit tarihler kullanılabilir: kural takvime bağlıdır (2026-12-04 Cuma, 05 Cumartesi, 06 Pazar, 07 Pazartesi).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication

import randevu_ekranlari as modul
import sunucu
from randevu_ekranlari import (
    HAFTA_SONU_MESAJI as ISTEMCI_MESAJI, RandevuDuzenleFormu, RandevuOlusturFormu, hafta_sonu_mu, siradaki_is_gunu,
)
from sunucu import HAFTA_SONU_MESAJI, app, hafta_sonuna_denk_mi, mevcut_kullanici_id

CUMA, CUMARTESI, PAZAR, PAZARTESI = (datetime(2026, 12, g, 10, 0) for g in (4, 5, 6, 7))


# ------------------------------------------------------------------ yardımcılar
def test_sunucu_yardimcisi_cumartesi_ve_pazari_yakalar():
    assert not hafta_sonuna_denk_mi(CUMA, CUMA.replace(hour=11))
    assert hafta_sonuna_denk_mi(CUMARTESI, CUMARTESI.replace(hour=11))
    assert hafta_sonuna_denk_mi(PAZAR, PAZAR.replace(hour=11))
    assert not hafta_sonuna_denk_mi(PAZARTESI, PAZARTESI.replace(hour=11))
    assert hafta_sonuna_denk_mi(CUMA, CUMARTESI)                    # bitiş hafta sonuna taşarsa da reddedilir


def test_istemci_yardimcilari():
    assert [hafta_sonu_mu(QDate(2026, 12, g)) for g in (4, 5, 6, 7)] == [False, True, True, False]
    assert siradaki_is_gunu(QDate(2026, 12, 5)) == QDate(2026, 12, 7)       # cumartesi -> pazartesi
    assert siradaki_is_gunu(QDate(2026, 12, 6)) == QDate(2026, 12, 7)       # pazar -> pazartesi
    assert siradaki_is_gunu(QDate(2026, 12, 4)) == QDate(2026, 12, 4)       # hafta içi aynı kalır
    assert ISTEMCI_MESAJI.startswith("Hafta sonu randevu verilmez")


# ------------------------------------------------------------------ sunucu
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def govde(baslangic, saat_farki=1):
    return {"danisan_kod_id": "DAN-2026-0001", "psikolog_id": 3, "oda_id": 2,
            "baslangic_zamani": baslangic.isoformat(),
            "bitis_zamani": baslangic.replace(hour=baslangic.hour + saat_farki).isoformat()}


@pytest.mark.parametrize("gun", [CUMARTESI, PAZAR])
def test_hafta_sonu_randevu_olusturma_422_ve_veritabanina_gitmez(istemci, gun):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)          # yalnızca izin denetimi
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.post("/api/randevular", json=govde(gun))
    assert yanit.status_code == 422 and yanit.json()["detail"] == HAFTA_SONU_MESAJI
    sorgular = [a[0] for a, _ in conn.cursor.return_value.execute.call_args_list]
    assert not any("INSERT INTO randevular" in s for s in sorgular)


def test_hafta_ici_randevu_hafta_sonu_kuralina_takilmaz(istemci):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.post("/api/randevular", json=govde(PAZARTESI))
    assert yanit.json().get("detail") != HAFTA_SONU_MESAJI


def _guncelle(istemci, degisiklik, mevcut_bas=CUMA):
    conn = MagicMock()
    c = conn.cursor.return_value
    mevcut = ("DAN-2026-0001", 3, 2, mevcut_bas, mevcut_bas.replace(hour=11), "PLANLANDI")
    c.fetchone.side_effect = [(1,), mevcut, ("MEMUR",), None, None, None]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = istemci.patch("/api/randevular/1", json=degisiklik)
    sorgular = [a[0] for a, _ in c.execute.call_args_list]
    return yanit, sorgular


def test_randevuyu_hafta_sonuna_tasimak_422(istemci):
    yanit, sorgular = _guncelle(istemci, {"baslangic_zamani": CUMARTESI.isoformat(),
                                          "bitis_zamani": CUMARTESI.replace(hour=11).isoformat()})
    assert yanit.status_code == 422 and yanit.json()["detail"] == HAFTA_SONU_MESAJI
    assert not any(s.startswith("UPDATE randevular") for s in sorgular)


def test_eskiden_kalan_hafta_sonu_randevusunun_zamani_degismeden_diger_alani_guncellenebilir(istemci):
    yanit, sorgular = _guncelle(istemci, {"danisan_kod_id": "DAN-2026-0002"}, mevcut_bas=CUMARTESI)
    assert yanit.status_code == 200
    assert any(s.startswith("UPDATE randevular") for s in sorgular)


# ------------------------------------------------------------------ randevu formu
AKTIF = {}


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


def sahte_sunucu(yontem, url, **kwargs):
    AKTIF.setdefault("istekler", []).append(url)
    if url.endswith("/api/randevular/doluluk"):
        return cevap({"dolu_araliklar": []})
    if url.endswith("/api/psikologlar"):
        return cevap([{"personel_id": 3, "ad_soyad": "Ayşe", "kullanici_id": 13}])
    if "/odalar" in url:
        return cevap([{"oda_id": 2, "oda_adi": "Oda-1", "kapasite": 1, "aktif_mi": True}])
    return cevap([])


@pytest.fixture(autouse=True)
def form_yamasi():
    AKTIF.clear()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=sahte_sunucu):
        yield


def isle():
    QApplication.processEvents()
    QApplication.processEvents()


def acik_saatler(form):
    model = form.cmb_saat.model()
    return [form.cmb_saat.itemData(i) for i in range(form.cmb_saat.count()) if model.item(i).isEnabled()]


def hafta_ici_yap(form):
    form.dt_tarih.setDate(QDate(2026, 12, 7))
    isle()


def test_yeni_randevu_formu_hafta_sonu_acilmaz(qapp=None):
    form = RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    assert not hafta_sonu_mu(form.dt_tarih.date())                  # bugün hafta sonuysa bile sonraki pazartesi
    form.close()


def test_hafta_sonu_secilince_saatler_kapanir_uyari_cikar_kaydet_kapanir():
    form = RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    hafta_ici_yap(form)
    assert acik_saatler(form) and form.btn_kaydet.isEnabled()      # hafta içi: saatler açık, kaydedilebilir
    form.dt_tarih.setDate(QDate(2026, 12, 5))                     # cumartesi
    isle()
    assert acik_saatler(form) == [] and form.saat_secimi() is None
    assert form.lbl_doluluk_hatasi.text() == ISTEMCI_MESAJI
    assert not form.btn_kaydet.isEnabled()
    form.dt_tarih.setDate(QDate(2026, 12, 6))                     # pazar
    isle()
    assert acik_saatler(form) == [] and not form.btn_kaydet.isEnabled()
    form.dt_tarih.setDate(QDate(2026, 12, 8))                     # salı: yeniden açılır
    isle()
    assert acik_saatler(form) and form.btn_kaydet.isEnabled() and form.lbl_doluluk_hatasi.text() == ""
    form.close()


def test_hafta_sonunda_doluluk_istegi_gonderilmez():
    form = RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    hafta_ici_yap(form)
    onceki = AKTIF["istekler"].count("http://testserver/api/randevular/doluluk")
    form.dt_tarih.setDate(QDate(2026, 12, 5))
    isle()
    assert AKTIF["istekler"].count("http://testserver/api/randevular/doluluk") == onceki
    form.close()


def test_takvimde_cumartesi_ve_pazar_soluk_gorunur():
    form = RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    takvim = form.dt_tarih.calendarWidget()
    for gun in (Qt.Saturday, Qt.Sunday):
        assert takvim.weekdayTextFormat(gun).foreground().color().name().lower() == "#94a3b8"
    form.close()


def test_duzenleme_formunda_hafta_sonuna_tasima_engellenir():
    eski = {"danisan_kod_id": "DAN-2026-0001", "psikolog_id": 3, "oda_id": 2, "durum": "PLANLANDI",
            "baslangic_zamani": "2026-12-04T10:00:00", "bitis_zamani": "2026-12-04T11:00:00"}
    form = RandevuDuzenleFormu("http://testserver", "TOKEN", 11, 1, eski)
    isle()
    assert acik_saatler(form) and form.btn_guncelle.isEnabled()
    form.dt_tarih.setDate(QDate(2026, 12, 5))
    isle()
    assert acik_saatler(form) == [] and not form.btn_guncelle.isEnabled()
    assert form.lbl_doluluk_hatasi.text() == ISTEMCI_MESAJI
    form.close()


# ------------------------------------------------------------------ satır sonu
def test_etiketlerde_harfiyen_ters_bolu_n_yazisi_yok():
    import danisanlar_ekrani
    import k_personel_ekranlari
    for modul_ in (modul, danisanlar_ekrani, k_personel_ekranlari):
        kaynak = open(modul_.__file__, encoding="utf-8").read()
        assert '\\\\n' not in kaynak, modul_.__name__


def test_form_hatasi_etiketi_satirlari_gercek_satir_sonuyla_birlestirir():
    form = RandevuOlusturFormu("http://testserver", "TOKEN", 11)
    form._form_hata_durumu("a", "Birinci hata")
    form._form_hata_durumu("b", "İkinci hata")
    assert form.lbl_form_hatasi.text() == "Birinci hata\nİkinci hata"
    form.close()
