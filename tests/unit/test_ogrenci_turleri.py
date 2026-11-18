"""Öğrenci türleri: etiketler, Gönüllü/Asistan ekleme, Danışma Masası'nın bu uçtan eklenememesi, Bölüm/Sınıf kaydı, pasife alma kuralı.
Gerçek PostgreSQL kullanılmaz."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from server.modeller import OgrenciEkleModeli
from server.sunucu import OGRENCI_TUR_ETIKETLERI, ogrenci_aktiflik_duzenle, ogrenci_ekle

VERI = {"ad_soyad": "Test Öğrenci", "ogrenci_numarasi": "2026001", "telefon": "05551234567"}


def test_uc_ogrenci_turunun_etiketi_var():
    """Etiket listesi mevcut öğrencileri (Danışma Masası dahil) göstermek içindir."""
    assert OGRENCI_TUR_ETIKETLERI == {
        "GONULLU": "Gönüllü Öğrenci",
        "DANISMA_MASASI": "Danışma Masası Öğrencisi",
        "ASISTAN": "Asistan Öğrenci",
    }


@pytest.mark.parametrize("tur", ["GONULLU", "ASISTAN"])
def test_ekleme_ucu_veritabanina_secilen_turu_ve_bolum_sinifi_yazar(tur):
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (77,)
    model = OgrenciEkleModeli(**VERI, tur=tur, bolum="  Psikoloji ", sinif="3")
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.denetim.denetim_kaydi_olustur"):
        sonuc = ogrenci_ekle(model, yetkili_id=1)
    assert sonuc["ogrenci_id"] == 77
    insert = next(c for c in cursor.execute.call_args_list if "INSERT INTO ogrenciler" in c.args[0])
    assert "bolum" in insert.args[0] and "sinif" in insert.args[0]
    assert insert.args[1] == ("Test Öğrenci", "2026001", "05551234567", tur, "Psikoloji", "3")


def test_bolum_ve_sinif_bos_ise_null_yazilir_ve_sinirlar_denetlenir():
    model = OgrenciEkleModeli(**VERI, tur="GONULLU", bolum="", sinif="   ")
    assert model.bolum is None and model.sinif is None
    with pytest.raises(ValidationError):
        OgrenciEkleModeli(**VERI, tur="GONULLU", bolum="B" * 101)         # veritabanı: VARCHAR(100)
    with pytest.raises(ValidationError):
        OgrenciEkleModeli(**VERI, tur="GONULLU", sinif="S" * 21)          # veritabanı: VARCHAR(20)


def _aktiflik(kullanici_id, tur, aktif_mi=False):
    """Pasife alma isteğini sahte veritabanıyla çalıştırır; (sonuç ya da HTTPException) döner."""
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    if kullanici_id is None:
        cursor.fetchone.side_effect = [(None,), (tur, True), None]
    else:
        cursor.fetchone.side_effect = [(kullanici_id,), ("DANISMA_OGRENCISI",), (tur, True), None, (5,)]
    veri = SimpleNamespace(aktif_mi=aktif_mi)
    with patch("server.sunucu.psycopg2.connect", return_value=conn), patch("server.sunucu.denetim_kaydi_olustur"):
        try:
            return ogrenci_aktiflik_duzenle(1, veri, yetkili_id=9)
        except HTTPException as hata:
            return hata


def test_danisma_masasi_ogrencisi_bu_uctan_eklenemez():
    """Danışma Masası öğrencisi giriş hesabı gerektirir; hesapsız kayıt oluşmaması için ekleme ucu reddeder."""
    with pytest.raises(ValidationError):
        OgrenciEkleModeli(**VERI, tur="DANISMA_MASASI")


def test_hesaba_bagli_danisma_ogrencisi_hala_bu_ekrandan_pasife_alinamaz():
    sonuc = _aktiflik(kullanici_id=12, tur="DANISMA_MASASI")
    assert isinstance(sonuc, HTTPException) and sonuc.status_code == 409
    assert "pasife alınamaz" in sonuc.detail


@pytest.mark.parametrize("tur", ["GONULLU", "ASISTAN"])
def test_gonullu_ve_asistan_pasife_alinabilir(tur):
    sonuc = _aktiflik(kullanici_id=None, tur=tur)
    assert not isinstance(sonuc, HTTPException) and sonuc["aktif_mi"] is False


def test_migrasyon_zincire_baglanir():
    dosya = (Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
             / "d6c3a9e1f407_ogrenci_asistan_turu_bolum_sinif.py")
    spec = importlib.util.spec_from_file_location("ogrenci_turu_migrasyonu", dosya)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    # Zincirdeki yeri sabit bir revizyona bağlanmaz (başka PR'lar araya yeni migrasyon ekleyebilir); var olan bir revizyona
    # bağlı olduğu ve tek head bıraktığı ayrı testlerde (test_audit_degistirilemez) denetlenir.
    assert modul.revision == "d6c3a9e1f407"
    mevcutlar = {d.name.split("_")[0] for d in dosya.parent.glob("*.py")}
    assert modul.down_revision in mevcutlar
    metin = dosya.read_text(encoding="utf-8")
    assert "ADD VALUE IF NOT EXISTS 'ASISTAN'" in metin and "ADD COLUMN IF NOT EXISTS bolum" in metin
