"""Yabancı anahtar indeksleri migrasyonunun (a7d3e9c1b254) sahte veritabanı gerektirmeyen denetimleri."""

import importlib.util
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

MIGRASYON = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "a7d3e9c1b254_yabanci_anahtar_indeksleri.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("yabanci_anahtar_indeksleri", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_zincire_dogru_baglanir():
    modul = _yukle()
    assert modul.revision == "a7d3e9c1b254"
    assert modul.down_revision == "b5e2c8d9a1f3"


def test_yirmi_dort_indeks_tekrarsiz_tanimli():
    modul = _yukle()
    assert len(modul.INDEKSLER) == 24
    assert len(set(modul.INDEKSLER)) == 24


def test_indeks_adlari_postgresql_sinirinin_altinda_ve_tekrarsiz():
    modul = _yukle()
    adlar = [modul.indeks_adi(t, s) for t, s in modul.INDEKSLER]
    assert len(set(adlar)) == len(adlar)
    assert all(len(ad) <= 63 for ad in adlar)
    assert all(re.fullmatch(r"ix_[a-z0-9_]+", ad) for ad in adlar)


def test_yukseltme_her_indeksi_varsa_atlayarak_olusturur():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.upgrade()
    sorgular = [cagri.args[0] for cagri in op.execute.call_args_list]
    assert len(sorgular) == 24
    assert all(s.startswith("CREATE INDEX IF NOT EXISTS ") for s in sorgular)
    assert 'ON "kullanicilar" ("rol_id")' in " ".join(sorgular)


def test_geri_alma_yalnizca_kendi_indekslerini_siler():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.downgrade()
    sorgular = [cagri.args[0] for cagri in op.execute.call_args_list]
    assert len(sorgular) == 24
    assert all(s.startswith("DROP INDEX IF EXISTS ") for s in sorgular)
    assert not any("TABLE" in s.upper() for s in sorgular)


def test_migrasyon_veriye_dokunmaz():
    kaynak = MIGRASYON.read_text(encoding="utf-8").upper()
    for yasak in ("INSERT ", "UPDATE ", "DELETE ", "DROP TABLE", "ALTER TABLE"):
        assert yasak not in kaynak, yasak
