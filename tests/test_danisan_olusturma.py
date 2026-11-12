"""
Yeni danışan oluşturma: danışanın hangi psikologa ait olduğu her zaman belli olur.

- Psikolog hesabı: danışan kendi adına açılır (istek başka psikolog bildirse de).
- Admin/danışma gibi roller: psikolog seçmek zorunda; seçilen kişi aktif bir psikolog olmalı.
- Ücretli/ücretsiz ve istisna seçimi sunucuya gerçekten ulaşır (eskiden JSON gövdesinde gidip yok sayılıyordu).
- Menüde: Danışanlar sayfasında Yeni Danışan var, Yeni Randevu yok; Randevu Yönetimi'nde tersi.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QPushButton

import danisan_diyalog as modul
import main_window as mw
from danisan_diyalog import DanisanOlusturDialog
from sunucu import app, mevcut_kullanici_id

KAYIT = ("DAN-2026-0099", True, "YOK", True, None, 7)


# ------------------------------------------------------------------ menü
def _aksiyonlar(sayfa):
    for _, ogeler in mw.MENU:
        for oge in ogeler:
            if oge["ad"] == sayfa:
                return [etiket for etiket, _ in oge.get("aksiyon", [])]
    raise AssertionError(sayfa)


def test_randevu_yonetiminde_yeni_danisan_yok_yeni_randevu_var():
    etiketler = _aksiyonlar("Randevu Yönetimi")
    assert any("Yeni Randevu" in e for e in etiketler)
    assert not any("Yeni Danışan" in e for e in etiketler)


def test_danisanlar_sayfasinda_yeni_danisan_var_randevu_olusturma_yok():
    etiketler = _aksiyonlar("Danışanlar")
    assert any("Yeni Danışan" in e for e in etiketler)
    assert not any("Randevu" in e for e in etiketler)


# ------------------------------------------------------------------ sunucu
@pytest.fixture
def istemci():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield TestClient(app)
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


def _olustur(istemci, kimlik, sorgu="", psikolog_kaydi=(7,)):
    """kimlik: (personel_id, rol) satırı; psikolog_kaydi: seçilen psikolog doğrulama sonucu."""
    conn = MagicMock()
    c = conn.cursor.return_value
    sirali = [(1,), kimlik]
    if kimlik[1] != "PSIKOLOG":
        sirali.append(psikolog_kaydi)
    sirali.append(KAYIT)
    c.fetchone.side_effect = sirali
    with patch("sunucu.psycopg2.connect", return_value=conn), \
            patch("sunucu.otomatik_danisan_kodu_uret", return_value="DAN-2026-0099"):
        yanit = istemci.post("/api/danisan-kodlari" + sorgu)
    ekleme = next((x for x in c.execute.call_args_list if "INSERT INTO danisan_kodlari" in x.args[0]), None)
    return yanit, (ekleme.args[1] if ekleme else None)


def test_psikolog_danisani_kendi_adina_acar_istenen_psikolog_yok_sayilir(istemci):
    yanit, parametreler = _olustur(istemci, (9, "PSIKOLOG"), "?psikolog_id=7")
    assert yanit.status_code == 201
    assert parametreler[3] == 9


def test_personel_kaydi_olmayan_psikolog_403(istemci):
    yanit, parametreler = _olustur(istemci, (None, "PSIKOLOG"))
    assert yanit.status_code == 403 and parametreler is None


def test_admin_psikolog_secmeden_danisan_olusturamaz(istemci):
    yanit, parametreler = _olustur(istemci, (22, "ADMIN"))
    assert yanit.status_code == 422 and "psikolog" in yanit.json()["detail"].lower()
    assert parametreler is None


def test_admin_secilen_psikolog_adina_danisan_olusturur_kendi_personel_kaydi_kullanilmaz(istemci):
    yanit, parametreler = _olustur(istemci, (22, "ADMIN"), "?psikolog_id=7")
    assert yanit.status_code == 201
    assert parametreler == ("DAN-2026-0099", True, "YOK", 7)


def test_danisma_ogrencisi_personel_kaydi_olmasa_da_psikolog_secerek_olusturur(istemci):
    yanit, parametreler = _olustur(istemci, (None, "DANISMA_OGRENCISI"), "?psikolog_id=7")
    assert yanit.status_code == 201 and parametreler[3] == 7


def test_secilen_kisi_aktif_psikolog_degilse_422(istemci):
    yanit, parametreler = _olustur(istemci, (22, "ADMIN"), "?psikolog_id=99", psikolog_kaydi=None)
    assert yanit.status_code == 422 and parametreler is None


@pytest.mark.parametrize("deger", ["0", "-1", "abc"])
def test_gecersiz_psikolog_id_reddedilir(istemci, deger):
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (1,)
    with patch("sunucu.psycopg2.connect", return_value=conn):
        assert istemci.post("/api/danisan-kodlari?psikolog_id=" + deger).status_code == 422


# ------------------------------------------------------------------ pencere
PSIKOLOGLAR = [{"personel_id": 3, "ad_soyad": "Ayşe Yılmaz"}, {"personel_id": 7, "ad_soyad": "Reyhan Kaya"}]


def cevap(veri, durum=200):
    y = MagicMock()
    y.status_code = durum
    y.json.return_value = veri
    y._tkys_oturum_reddedildi = False
    return y


class Sunucu:
    def __init__(self, post_durumu=201):
        self.post_durumu = post_durumu
        self.postlar = []

    def __call__(self, yontem, url, **kwargs):
        if yontem == "POST":
            self.postlar.append(kwargs)
            return cevap({"durum": "basarili", "veri": {"danisan_kod_id": "DAN-2026-0050"}}, self.post_durumu)
        if url.endswith("/api/psikologlar"):
            return cevap(PSIKOLOGLAR)
        return cevap([])


@pytest.fixture
def sunucu_taklidi():
    taklit = Sunucu()
    with patch.object(modul, "oturum_kontrollu_istek", side_effect=taklit), \
            patch.object(modul.QMessageBox, "information"), patch.object(modul.QMessageBox, "warning") as uyari:
        taklit.uyari = uyari
        yield taklit


def pencere(**kwargs):
    return DanisanOlusturDialog("http://testserver", "TOKEN", **kwargs)


def test_psikolog_hesabinda_psikolog_kutusu_kendi_adina_kilitli(sunucu_taklidi):
    p = pencere(mevcut_psikolog_id=3)
    assert p.cmb_psikolog.currentData() == 3 and not p.cmb_psikolog.isEnabled()


def test_yetkili_rolde_psikolog_secmeden_kaydedilemez(sunucu_taklidi):
    p = pencere(mevcut_psikolog_id=22)
    assert p.cmb_psikolog.isEnabled() and p.cmb_psikolog.currentData() is None
    p.kaydet()
    sunucu_taklidi.uyari.assert_called_once()
    assert sunucu_taklidi.postlar == []


def test_danisanlar_sayfasinda_secili_psikolog_onerilir(sunucu_taklidi):
    p = pencere(mevcut_psikolog_id=22, onceden_psikolog_id=7)
    assert p.cmb_psikolog.currentData() == 7 and p.cmb_psikolog.isEnabled()


def test_ucretsiz_ve_istisna_secimi_ile_psikolog_sunucuya_sorgu_parametresi_olarak_gider(sunucu_taklidi):
    p = pencere(mevcut_psikolog_id=22, onceden_psikolog_id=7)
    p.cmb_ucret.setCurrentIndex(p.cmb_ucret.findData(False))
    p.cmb_istisna.setCurrentIndex(p.cmb_istisna.findData("KANSER"))
    with patch.object(p, "accept"):
        p.kaydet()
    gonderilen = sunucu_taklidi.postlar[0]
    assert gonderilen["params"] == {"ucretli_mi": "false", "istisna_turu": "KANSER", "psikolog_id": 7}
    assert "json" not in gonderilen
    assert p.olusan_kod == "DAN-2026-0050"


def test_psikolog_hesabi_kendi_kimligiyle_gonderir(sunucu_taklidi):
    p = pencere(mevcut_psikolog_id=3)
    with patch.object(p, "accept"):
        p.kaydet()
    assert sunucu_taklidi.postlar[0]["params"] == {"ucretli_mi": "true", "istisna_turu": "YOK", "psikolog_id": 3}
