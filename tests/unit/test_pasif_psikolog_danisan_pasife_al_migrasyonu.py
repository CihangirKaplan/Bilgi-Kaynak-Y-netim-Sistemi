"""Pasif psikologların danışanlarını pasife alan migrasyonun (d1e6a3b9c847) sahte veritabanı gerektirmeyen denetimleri."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "d1e6a3b9c847_pasif_psikolog_danisanlari_pasife_al.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("pasif_psikolog_danisan_pasife_al", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_zincire_baglanir():
    modul = _yukle()
    assert modul.revision == "d1e6a3b9c847"
    assert modul.down_revision == "c2e5a9d4b681"
    assert any(modul.down_revision in d.name for d in SURUMLER.glob("*.py"))


def test_yukseltme_yalnizca_pasif_psikologlarin_aktif_planlisiz_danisanlarini_isaretleyip_pasife_alir():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.upgrade()
    (sorgu,) = [c.args[0] for c in op.execute.call_args_list]
    n = " ".join(sorgu.split())
    assert n.startswith("UPDATE danisan_kodlari d SET aktif_mi = FALSE, psikolog_pasifligi_nedeniyle_pasif = TRUE FROM personel p")
    assert "k.aktif_mi = FALSE AND UPPER(r.rol_adi) = 'PSIKOLOG'" in n                         # yalnızca şu an pasif psikolog
    assert "d.aktif_mi = TRUE" in n                                                           # elle pasif olanlar işaretlenmez
    assert "x.durum = 'PLANLANDI' AND x.bitis_zamani > NOW()" in n                            # gelecekte planlı randevusu olan danışan atlanır
    for yasak in ("DELETE", "DROP", "INSERT", "ALTER"):
        assert yasak not in n.upper()


def test_geri_alma_hicbir_sey_yapmaz():
    modul = _yukle()
    with patch.object(modul, "op", MagicMock()) as op:
        modul.downgrade()
    assert not op.method_calls
