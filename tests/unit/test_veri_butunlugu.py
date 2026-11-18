"""Veri bütünlüğü: girdi uzunlukları veritabanı sütunlarıyla uyumlu, uzun parola sunucu hatası vermez, migrasyon zincirde.
Gerçek PostgreSQL kullanılmaz (gerçek kısıt davranışı test_veri_butunlugu_pg_quality.py'de)."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import bcrypt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from server.guvenlik import parola_dogrula
from server.modeller import (
    GirisModeli, OgrenciEkleModeli, RandevuGuncelleModeli, RandevuOlusturModeli, SifreDegistirModeli,
)

VERI = {"ad_soyad": "Test Öğrenci", "ogrenci_numarasi": "2026001", "tur": "GONULLU"}
RANDEVU = dict(psikolog_id=1, oda_id=1, baslangic_zamani="2030-01-01T10:00:00", bitis_zamani="2030-01-01T11:00:00")


def test_ogrenci_ekleme_alanlari_veritabani_sinirlarini_asamaz():
    assert OgrenciEkleModeli(**{**VERI, "ad_soyad": "A" * 100}).ad_soyad == "A" * 100
    for kotu in ({"ad_soyad": "A" * 101}, {"ad_soyad": "   "}, {"ad_soyad": ""},
                 {"ogrenci_numarasi": "1" * 16}, {"ogrenci_numarasi": "  "}, {"telefon": "0" * 21}):
        with pytest.raises(ValidationError):
            OgrenciEkleModeli(**{**VERI, **kotu})


def test_ogrenci_ekleme_bosluklari_kirpar_ve_bos_telefonu_yok_sayar():
    model = OgrenciEkleModeli(**{**VERI, "ad_soyad": "  Ayşe Kaya ", "ogrenci_numarasi": " 123 ", "telefon": "   "})
    assert (model.ad_soyad, model.ogrenci_numarasi, model.telefon) == ("Ayşe Kaya", "123", None)


def test_randevu_danisan_kodu_en_fazla_50_karakter():
    RandevuOlusturModeli(danisan_kod_id="D" * 50, **RANDEVU)
    with pytest.raises(ValidationError):
        RandevuOlusturModeli(danisan_kod_id="D" * 51, **RANDEVU)
    RandevuGuncelleModeli(danisan_kod_id="D" * 50)
    with pytest.raises(ValidationError):
        RandevuGuncelleModeli(danisan_kod_id="D" * 51)


def test_giris_alanlari_makul_sinirla_sinirli():
    GirisModeli(kullanici_adi="u" * 100, parola="p" * 256)
    for kotu in ({"kullanici_adi": "u" * 101, "parola": "x"}, {"kullanici_adi": "u", "parola": "p" * 257}):
        with pytest.raises(ValidationError):
            GirisModeli(**kotu)


def test_yeni_parola_72_bayti_gecemez_turkce_karakterler_iki_bayttir():
    SifreDegistirModeli(eski_parola="x", yeni_parola="a" * 72, yeni_parola_tekrar="x")      # 72 bayt
    SifreDegistirModeli(eski_parola="x", yeni_parola="ş" * 36, yeni_parola_tekrar="x")      # 72 bayt
    with pytest.raises(ValidationError) as hata:
        SifreDegistirModeli(eski_parola="x", yeni_parola="ş" * 37, yeni_parola_tekrar="x")  # 74 bayt: bcrypt hata verirdi
    assert "72 bayt" in str(hata.value)


def test_cok_uzun_parola_bcrypt_hatasi_degil_yanlis_parola_sayilir():
    hash_ = bcrypt.hashpw(b"dogru-parola", bcrypt.gensalt(4)).decode()
    assert parola_dogrula("dogru-parola", hash_) is True
    assert parola_dogrula("yanlis", hash_) is False
    assert parola_dogrula("x" * 73, hash_) is False          # eskiden ValueError -> 500
    assert parola_dogrula("ş" * 37, hash_) is False          # 74 bayt


def test_giris_ucu_cok_uzun_parolada_500_degil_401_doner():
    from server.sunucu import giris_yap

    hash_ = bcrypt.hashpw(b"dogru-parola", bcrypt.gensalt(4)).decode()
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (7, "kullanici", hash_, 3, True, 0, None, False, "MEMUR", None)
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"):
        with pytest.raises(HTTPException) as hata:
            giris_yap(GirisModeli(kullanici_adi="kullanici", parola="x" * 200))
    assert hata.value.status_code == 401
    # başarısız deneme sayılır (kilitleme sayacı artar): uzun parolayla kilitleme atlatılamaz
    assert any("basarisiz_giris_sayisi" in str(c.args[0]) for c in cursor.execute.call_args_list)


def _migrasyon():
    dosya = (Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
             / "e8b4d2f6a193_veri_butunlugu_kisitlari.py")
    spec = importlib.util.spec_from_file_location("veri_butunlugu_migrasyonu", dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return dosya, modul


def test_migrasyon_icerigi_ve_zincirdeki_yeri():
    dosya, modul = _migrasyon()
    assert modul.revision == "e8b4d2f6a193"
    assert modul.down_revision in {d.name.split("_")[0] for d in dosya.parent.glob("*.py")}   # sabit head'e bağlanmaz
    assert modul.RANDEVU_DURUMLARI == ("PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI")
    assert set(modul.CIHAZ_TABLOLARI) == {"cihaz_arizalari", "cihaz_bakimlari", "cihaz_kalibrasyonlari", "cihaz_bakim_planlari"}
    # Erteleme geçmişi gibi bilerek ON DELETE SET NULL olan sütunlar kapsam dışıdır (öğrenci silinse de geçmiş kalmalı).
    assert "erteleme" not in dosya.read_text(encoding="utf-8").split('"""')[2]
    assert [t for t, _s, _i in modul.AD_INDEKSLERI] == ["kullanicilar", "odalar", "bolumler"]


def test_ad_anahtari_turkce_i_harflerini_ayni_sayar():
    _dosya, modul = _migrasyon()
    sql = modul.ad_anahtari_sql("oda_adi")
    assert sql == "lower(translate(oda_adi, 'İIı', 'iii'))"
