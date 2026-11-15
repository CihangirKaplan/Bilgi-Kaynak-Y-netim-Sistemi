"""Şema işleri (alembic, geri yükleme) için kimlik seçimi: DB_MIGRATION_* yoksa eski davranış (DB_USER) sürer."""

import importlib.util
import sys
from pathlib import Path

import pytest

from server.sema_kimligi import SemaKimligiHatasi, sema_kimligi

KOK = Path(__file__).resolve().parents[2]


def test_migration_kimligi_yoksa_db_user_kullanilir():
    assert sema_kimligi({"DB_USER": "uygulama", "DB_PASSWORD": "p1"}) == ("uygulama", "p1")


def test_migration_kimligi_varsa_o_kullanilir():
    ortam = {"DB_USER": "uygulama", "DB_PASSWORD": "p1", "DB_MIGRATION_USER": "yonetici", "DB_MIGRATION_PASSWORD": "p2"}
    assert sema_kimligi(ortam) == ("yonetici", "p2")


def test_migration_kullanicisi_adi_kirpilir():
    ortam = {"DB_USER": "u", "DB_PASSWORD": "p", "DB_MIGRATION_USER": "  yonetici ", "DB_MIGRATION_PASSWORD": "p2"}
    assert sema_kimligi(ortam)[0] == "yonetici"


@pytest.mark.parametrize("bos", ["", None])
def test_migration_kullanicisi_var_parola_yoksa_hata(bos):
    ortam = {"DB_USER": "u", "DB_PASSWORD": "p", "DB_MIGRATION_USER": "yonetici"}
    if bos is not None:
        ortam["DB_MIGRATION_PASSWORD"] = bos
    with pytest.raises(SemaKimligiHatasi, match="DB_MIGRATION_PASSWORD"):
        sema_kimligi(ortam)


def test_migration_parolasi_var_kullanici_yoksa_hata():
    # Parola yazılıp kullanıcı unutulursa sessizce DB_USER'a düşmek yanlış kimlikle işlem yapılmasına yol açardı.
    with pytest.raises(SemaKimligiHatasi, match="DB_MIGRATION_USER"):
        sema_kimligi({"DB_USER": "u", "DB_PASSWORD": "p", "DB_MIGRATION_PASSWORD": "p2"})


def test_hicbir_sey_tanimli_degilse_bos_doner():
    assert sema_kimligi({}) == (None, None)


def test_varsayilan_olarak_ortam_degiskenlerini_okur(monkeypatch):
    monkeypatch.setenv("DB_USER", "uyg")
    monkeypatch.setenv("DB_PASSWORD", "pp")
    monkeypatch.delenv("DB_MIGRATION_USER", raising=False)
    monkeypatch.delenv("DB_MIGRATION_PASSWORD", raising=False)
    assert sema_kimligi() == ("uyg", "pp")
    monkeypatch.setenv("DB_MIGRATION_USER", "yon")
    monkeypatch.setenv("DB_MIGRATION_PASSWORD", "yy")
    assert sema_kimligi() == ("yon", "yy")


def test_alembic_ayni_kimlik_secimini_kullanir():
    kaynak = (KOK / "database" / "migrations" / "env.py").read_text(encoding="utf-8")
    assert "from server.sema_kimligi import sema_kimligi" in kaynak
    assert "username=_SEMA_KULLANICI" in kaynak and "password=_SEMA_PAROLA" in kaynak
    assert 'os.getenv("DB_USER")' not in kaynak


def _geri_yukle_modulu():
    spec = importlib.util.spec_from_file_location("veritabani_geri_yukle_kimlik", KOK / "scripts" / "restore" / "veritabani_geri_yukle.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_geri_yukleme_yonetici_kimligini_kullanir(monkeypatch):
    modul = _geri_yukle_modulu()
    monkeypatch.setenv("DB_USER", "uygulama")
    monkeypatch.setenv("DB_PASSWORD", "p1")
    monkeypatch.setenv("DB_MIGRATION_USER", "yonetici")
    monkeypatch.setenv("DB_MIGRATION_PASSWORD", "p2")
    assert modul._sema_kimligi() == ("yonetici", "p2")


def test_geri_yukleme_tutarsiz_ayari_anlasilir_hataya_cevirir(monkeypatch):
    modul = _geri_yukle_modulu()
    monkeypatch.setenv("DB_MIGRATION_USER", "yonetici")
    monkeypatch.delenv("DB_MIGRATION_PASSWORD", raising=False)
    with pytest.raises(modul.GeriYuklemeHatasi, match="DB_MIGRATION_PASSWORD"):
        modul._sema_kimligi()


def test_geri_yukleme_veritabani_olusturamayan_kullaniciya_yol_gosterir(monkeypatch, tmp_path):
    import psycopg2

    modul = _geri_yukle_modulu()
    dump = tmp_path / "yedek.dump"
    dump.write_bytes(b"x")
    monkeypatch.setenv("DB_NAME", "canli")
    monkeypatch.setattr(modul, "pg_restore_yolu", lambda: "pg_restore")

    class Imlec:
        def execute(self, sorgu, *a):
            # İlk sorgu düz metindir (veritabanı var mı?); CREATE DATABASE ise psycopg2.sql nesnesidir.
            if not isinstance(sorgu, str):
                raise psycopg2.errors.InsufficientPrivilege("permission denied to create database")

        def fetchone(self):
            return None

    class Baglanti:
        autocommit = False

        def cursor(self):
            return Imlec()

        def close(self):
            pass

    monkeypatch.setattr(modul, "_baglan", lambda ad: Baglanti())
    with pytest.raises(modul.GeriYuklemeHatasi, match="DB_MIGRATION_USER"):
        modul.geri_yukle(dump, "yeni_veritabani", "canli")


def test_kilavuz_ve_env_ornegi_kisitli_kullanici_adimlarini_anlatir():
    kilavuz = (KOK / "docs" / "deployment" / "Sunucu_Kurulum_Kilavuzu.md").read_text(encoding="utf-8")
    assert "## 6A." in kilavuz
    for beklenen in ("scripts/uygulama_kullanicisi_olustur.py --uygula", "DB_MIGRATION_USER", "DB_MIGRATION_PASSWORD",
                     "--parolayi-yenile", "tkys_uygulama"):
        assert beklenen in kilavuz, beklenen
    ornek = (KOK / ".env.example").read_text(encoding="utf-8")
    assert "DB_MIGRATION_USER" in ornek and "DB_MIGRATION_PASSWORD" in ornek
