"""danisan_kodlari.psikolog_pasifligi_nedeniyle_pasif sütununu ekleyen migrasyonun (ccd4e7b1a925) sahte veritabanı gerektirmeyen denetimleri."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "ccd4e7b1a925_danisan_psikolog_pasifligi_isareti.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("danisan_psikolog_pasifligi_isareti", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _sorgular(islev):
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        getattr(modul, islev)()
    return [c.args[0] for c in op.execute.call_args_list]


def test_zincire_baglanir():
    modul = _yukle()
    assert modul.revision == "ccd4e7b1a925"
    assert modul.down_revision == "d6c3a9e1f407"
    assert any(modul.down_revision in d.name for d in SURUMLER.glob("*.py"))      # bağlandığı revizyon gerçekten var


def test_yukseltme_yalnizca_isaret_sutununu_ekler_veriye_dokunmaz():
    (sorgu,) = _sorgular("upgrade")
    assert sorgu == "ALTER TABLE danisan_kodlari ADD COLUMN IF NOT EXISTS psikolog_pasifligi_nedeniyle_pasif BOOLEAN NOT NULL DEFAULT FALSE"
    for yasak in ("UPDATE", "DELETE", "INSERT", "DROP"):
        assert yasak not in sorgu.upper()


def test_geri_alma_yalnizca_kendi_sutununu_siler():
    (sorgu,) = _sorgular("downgrade")
    assert sorgu == "ALTER TABLE danisan_kodlari DROP COLUMN IF EXISTS psikolog_pasifligi_nedeniyle_pasif"
