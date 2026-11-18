"""Pasif psikologların oda atamalarını temizleyen migrasyonun (e7c1a9d4b362) sahte veritabanı gerektirmeyen denetimleri."""

import importlib.util
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "e7c1a9d4b362_pasif_psikolog_oda_atamalari_temizle.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("pasif_psikolog_oda_temizle", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_zincire_baglanir_ve_tek_uc_kalir():
    modul = _yukle()
    assert modul.revision == "e7c1a9d4b362"
    assert modul.down_revision == "e0f32bef6d16"
    assert any(modul.down_revision in d.name for d in SURUMLER.glob("*.py"))      # bağlandığı revizyon gerçekten var


def test_yukseltme_yalnizca_pasif_kullanicilarin_oda_atamalarini_siler():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.upgrade()
    (sorgu,) = [c.args[0] for c in op.execute.call_args_list]
    normal = " ".join(sorgu.split())
    assert normal.startswith("DELETE FROM psikolog_odalar WHERE")
    assert "kullanicilar WHERE aktif_mi = FALSE" in normal
    for dokunulmaz in ("randevular", "danisan_kodlari", "personel", "odalar WHERE", "DROP", "ALTER", "UPDATE"):
        assert dokunulmaz not in normal.replace("psikolog_odalar", "")


def test_geri_alma_hicbir_sey_yapmaz():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.downgrade()
    assert not op.method_calls
