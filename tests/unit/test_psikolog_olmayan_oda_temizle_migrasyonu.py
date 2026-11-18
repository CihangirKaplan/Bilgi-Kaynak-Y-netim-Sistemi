"""Psikolog olmayan kullanıcıların oda atamalarını temizleyen migrasyonun (a9d3c7e1f452) sahte veritabanı gerektirmeyen denetimleri."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "a9d3c7e1f452_psikolog_olmayan_oda_atamalari_temizle.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("psikolog_olmayan_oda_temizle", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_zincire_baglanir():
    modul = _yukle()
    assert modul.revision == "a9d3c7e1f452"
    assert modul.down_revision == "c5a2e8f1d739"
    assert any(modul.down_revision in d.name for d in SURUMLER.glob("*.py"))      # bağlandığı revizyon gerçekten var


def test_yukseltme_yalnizca_psikolog_olmayanlarin_oda_atamalarini_siler():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.upgrade()
    (sorgu,) = [c.args[0] for c in op.execute.call_args_list]
    normal = " ".join(sorgu.split())
    assert normal.startswith("DELETE FROM psikolog_odalar WHERE kullanici_id IN")
    assert "JOIN roller r ON r.rol_id = k.rol_id WHERE UPPER(r.rol_adi) <> 'PSIKOLOG'" in normal
    for dokunulmaz in ("randevular", "danisan_kodlari", "personel", "odalar WHERE", "DROP", "ALTER", "UPDATE"):
        assert dokunulmaz not in normal.replace("psikolog_odalar", "")


def test_geri_alma_hicbir_sey_yapmaz():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.downgrade()
    assert not op.method_calls
