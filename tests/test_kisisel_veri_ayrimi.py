"""FR-008 Kişisel veri ayrımı (uygulama katmanı).

Gereksinim: operasyonel danışan kodunu gerçek kişiyle eşleştiren kayıt veya tablo bulunmamalıdır. Şema tarafı gerçek
PostgreSQL ile `test_kisisel_veri_ayrimi_pg_quality.py` dosyasındadır; burada sunucunun danışan koduyla ilgili
modelleri, yazdığı sütunlar, uçları ve yanıtları denetlenir. Veritabanı taklit edilir.
"""
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import modeller
import sunucu
from sunucu import app, mevcut_kullanici_id

KISISEL_PARCALAR = {
    "ad", "adi", "soyad", "soyadi", "tc", "kimlik", "telefon", "tel", "eposta", "email", "mail", "adres", "dogum",
    "tani", "ilac", "terapi", "travma", "aciklama", "not", "notu", "sikayet", "olcek", "gozlem", "saglik",
    "hastalik", "yorum",
}
# FR-008 İSTİSNASI: yaş grubu / terapi türü / görüşme tipi KAPALI listeli alanlardır (serbest metin yok; veritabanında CHECK
# kısıtı, modellerde Literal). "terapi" sözcüğü klinik terim sayıldığı için terapi_turu bilerek istisnadır.
KAPALI_LISTE_SUTUNLARI = {"terapi_turu"}
DANISAN_KODLARI_SUTUNLARI = {"danisan_kod_id", "ucretli_mi", "istisna_turu", "aktif_mi", "olusturulma_tarihi",
                             "olusturan_psikolog_id", "yas_grubu", "terapi_turu"}
RANDEVU_SUTUNLARI = {"randevu_id", "danisan_kod_id", "psikolog_id", "oda_id", "baslangic_zamani", "bitis_zamani",
                     "durum", "olusturulma_tarihi", "gorusme_tipi", "terapi_turu"}
KAYNAK = Path(sunucu.__file__).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def giris_yapmis_kullanici():
    app.dependency_overrides[mevcut_kullanici_id] = lambda: 5
    yield
    app.dependency_overrides.pop(mevcut_kullanici_id, None)


# ------------------------------------------------------------------ modeller
DANISAN_MODELLERI = ["DanisanKoduModeli", "RandevuModeli", "RandevuOlusturModeli", "RandevuGuncelleModeli"]


@pytest.mark.parametrize("ad", DANISAN_MODELLERI)
def test_danisan_ve_randevu_modelleri_kisisel_alan_tasimaz(ad):
    alanlar = set(getattr(modeller, ad).model_fields)
    assert alanlar, ad
    for alan in alanlar:
        if alan in KAPALI_LISTE_SUTUNLARI:
            continue
        assert not (set(alan.split("_")) & KISISEL_PARCALAR), f"{ad}.{alan} kişisel veri gibi görünüyor"


def test_modelleri_tum_alanlari_izinli_sutunlarla_eslesir():
    assert set(modeller.DanisanKoduModeli.model_fields) <= DANISAN_KODLARI_SUTUNLARI
    for ad in ("RandevuModeli", "RandevuOlusturModeli", "RandevuGuncelleModeli"):
        assert set(getattr(modeller, ad).model_fields) <= RANDEVU_SUTUNLARI, ad


# ------------------------------------------------------------------ yazılan sütunlar
def _ekleme_sutunlari(tablo):
    return [{c.strip() for c in m.group(1).split(",")}
            for m in re.finditer(r"INSERT INTO " + tablo + r"\s*\(([^)]*)\)", KAYNAK)]


def test_sunucu_danisan_kodlari_tablosuna_yalnizca_izinli_sutunlari_yazar():
    eklemeler = _ekleme_sutunlari("danisan_kodlari")
    assert eklemeler, "danisan_kodlari ekleme sorgusu bulunamadı (test eskimiş olabilir)"
    for sutunlar in eklemeler:
        assert sutunlar <= DANISAN_KODLARI_SUTUNLARI, sutunlar - DANISAN_KODLARI_SUTUNLARI


def test_sunucu_randevular_tablosuna_yalnizca_izinli_sutunlari_yazar():
    eklemeler = _ekleme_sutunlari("randevular")
    assert eklemeler, "randevular ekleme sorgusu bulunamadı (test eskimiş olabilir)"
    for sutunlar in eklemeler:
        assert sutunlar <= RANDEVU_SUTUNLARI, sutunlar - RANDEVU_SUTUNLARI


# ------------------------------------------------------------------ uçlar
def test_yolunda_danisan_gecen_uclar_bilinen_listeden_ibarettir():
    """Yeni bir 'danışan' ucu eklenirse (örn. ad-soyad alan bir uç) bu liste bilerek güncellenmek zorundadır."""
    bulunan = {(metot, yol) for yol_nesnesi in app.routes if hasattr(yol_nesnesi, "methods")
               for yol in [yol_nesnesi.path] if "danisan" in yol.lower() for metot in yol_nesnesi.methods}
    assert bulunan == {("GET", "/api/danisan-kodlari"), ("POST", "/api/danisan-kodlari"),
                       ("PATCH", "/api/danisan-kodlari/{danisan_kod_id}/durum"),
                       ("PATCH", "/api/danisan-kodlari/{danisan_kod_id}/bilgiler")}      # yalnızca aktif/pasif durumu


def _kod_olustur(sorgu_dizesi=""):
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), (7, "PSIKOLOG"), ("DAN-2026-0099", True, "YOK", True, None, 7, "YETISKIN", "BIREYSEL_TERAPI")]   # izin, kimlik, kayıt
    sorgu_dizesi = (sorgu_dizesi + "&" if sorgu_dizesi else "?") + "yas_grubu=YETISKIN"      # yaş grubu zorunludur
    with patch("sunucu.psycopg2.connect", return_value=conn), \
            patch("sunucu.otomatik_danisan_kodu_uret", return_value="DAN-2026-0099"):
        yanit = TestClient(app).post("/api/danisan-kodlari" + sorgu_dizesi)
    ekleme = next((x for x in c.execute.call_args_list if "INSERT INTO danisan_kodlari" in x.args[0]), None)
    return yanit, (ekleme.args[1] if ekleme else None)           # doğrulama reddederse kayıt sorgusu hiç çalışmaz


def test_kod_olusturma_fazladan_kisisel_alanlari_yok_sayar_ve_kaydetmez():
    yanit, parametreler = _kod_olustur("?ad_soyad=Ali%20Veli&telefon=5551234567&tc_kimlik=12345678901&tani=x")
    assert yanit.status_code == 201
    assert parametreler == ("DAN-2026-0099", True, "YOK", 7, "YETISKIN", "BIREYSEL_TERAPI")   # kod, ücret, istisna, psikolog, yaş grubu, terapi
    assert not any(isinstance(p, str) and ("Ali" in p or "555" in p or "123456" in p) for p in parametreler)


def test_kod_olusturma_yaniti_yalnizca_izinli_alanlari_icerir():
    yanit, _ = _kod_olustur()
    veri = yanit.json()["veri"]
    assert set(veri) == DANISAN_KODLARI_SUTUNLARI
    assert not any(set(alan.split("_")) & KISISEL_PARCALAR for alan in veri if alan not in KAPALI_LISTE_SUTUNLARI)


def test_kod_olusturma_ucu_yalnizca_ucret_ve_istisna_parametresi_alir():
    import inspect
    parametreler = set(inspect.signature(sunucu.danisan_kodu_olustur).parameters)
    # psikolog_id yalnızca bir personel kimliğidir (kişisel veri değil); admin/danışma danışanın psikoloğunu bununla bildirir
    assert parametreler == {"ucretli_mi", "istisna_turu", "psikolog_id", "yas_grubu", "terapi_turu", "kullanici_id"}


def test_kod_listesi_yalnizca_kod_ucret_ve_aktiflik_dondurur():
    conn = MagicMock()
    c = conn.cursor.return_value
    c.fetchone.side_effect = [(1,), ("MEMUR",)]
    c.fetchall.return_value = [("DAN-2026-0001", True, True, "YOK", datetime(2026, 5, 1, 10, 0), 3)]
    with patch("sunucu.psycopg2.connect", return_value=conn):
        yanit = TestClient(app).get("/api/danisan-kodlari")
    assert yanit.status_code == 200
    for kayit in yanit.json():
        assert set(kayit) <= DANISAN_KODLARI_SUTUNLARI


# ------------------------------------------------------------------ istisna_turu izin listesi (FR-008)
@pytest.mark.parametrize("deger", ["Ali Veli - depresyon", "kanser", "SEHIT GAZI", "ENGELLI", "", " YOK", "YOK; DROP TABLE x"])
def test_istisna_turu_serbest_metin_kabul_etmez(deger):
    from urllib.parse import quote
    yanit, _ = _kod_olustur("?ucretli_mi=false&istisna_turu=" + quote(deger))
    assert yanit.status_code == 422


def test_istisna_turu_reddedilince_kayit_yapilmaz_ve_deger_yanita_yazilmaz():
    yanit, parametreler = _kod_olustur("?ucretli_mi=false&istisna_turu=Ali%20Veli")
    assert yanit.status_code == 422
    assert parametreler is None and "Ali" not in yanit.text      # INSERT çalışmadı, girilen metin geri yansıtılmadı


@pytest.mark.parametrize("sorgu", ["?ucretli_mi=true&istisna_turu=YOK", "?ucretli_mi=false&istisna_turu=KANSER",
                                   "?ucretli_mi=false&istisna_turu=SEHIT_GAZI", ""])
def test_izinli_istisna_turleri_kabul_edilir(sorgu):
    yanit, _ = _kod_olustur(sorgu)
    assert yanit.status_code == 201


def test_ucretli_danisan_icin_istisna_turu_yok_disinda_olamaz():
    for tur in ("KANSER", "SEHIT_GAZI"):
        yanit, _ = _kod_olustur("?ucretli_mi=true&istisna_turu=" + tur)
        assert yanit.status_code == 422 and "Ücretli" in yanit.json()["detail"]


def test_izinli_istisna_listesi_arayuzun_sundugu_degerlerle_ayni():
    assert sunucu.IZINLI_ISTISNA_TURLERI == ("YOK", "KANSER", "SEHIT_GAZI")
    kaynak = (Path(__file__).resolve().parent.parent / "danisan_diyalog.py").read_text(encoding="utf-8")
    for deger in sunucu.IZINLI_ISTISNA_TURLERI:
        assert f'"{deger}"' in kaynak

