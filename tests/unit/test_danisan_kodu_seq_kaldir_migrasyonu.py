"""e5a2c8d1f396: kullanılmayan danisan_kodu_seq sayacını kaldıran migrasyonun veritabanı gerektirmeyen denetimleri."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "e5a2c8d1f396_danisan_kodu_seq_kaldir.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("danisan_kodu_seq_kaldir", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_zincire_baglanir():
    modul = _yukle()
    assert modul.revision == "e5a2c8d1f396"
    assert isinstance(modul.down_revision, str) and any(d.name.startswith(modul.down_revision) for d in SURUMLER.glob("*.py"))


def test_yukseltme_yalnizca_sayaci_kaldirir_veriye_dokunmaz():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.upgrade()
    (sorgu,) = [c.args[0] for c in op.execute.call_args_list]
    assert sorgu == "DROP SEQUENCE IF EXISTS danisan_kodu_seq;"                       # yeniden çalıştırılabilir (IF EXISTS), tablo/veri yok


def test_geri_alma_sayaci_yeniden_kurar_ve_mevcut_en_buyuk_koda_ayarlar():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.downgrade()
    sorgular = [" ".join(c.args[0].split()) for c in op.execute.call_args_list]
    assert sorgular[0] == "CREATE SEQUENCE IF NOT EXISTS danisan_kodu_seq START 1;"
    assert sorgular[1].startswith("SELECT setval('danisan_kodu_seq'") and "MAX(" in sorgular[1] and "danisan_kodlari" in sorgular[1]
    for s in sorgular:
        assert not s.upper().startswith(("DELETE", "UPDATE", "INSERT", "TRUNCATE"))
