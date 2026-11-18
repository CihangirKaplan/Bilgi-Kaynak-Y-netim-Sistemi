"""f3c8a1d7b520: #402 (e8b4d2f6a193) ve #403 (ccd4e7b1a925) migration kollarını birleştiren boş revizyonun denetimleri."""

import importlib.util
from pathlib import Path

from scripts.alembic_tek_head_kontrol import kontrol_et

SURUMLER = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
MIGRASYON = SURUMLER / "f3c8a1d7b520_alembic_head_birlestirme.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("alembic_head_birlestirme", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_iki_kolu_birlestirir():
    modul = _yukle()
    assert modul.revision == "f3c8a1d7b520"
    assert set(modul.down_revision) == {"ccd4e7b1a925", "e8b4d2f6a193"}
    assert {p.name.split("_")[0] for p in SURUMLER.glob("*.py")} >= set(modul.down_revision)     # bağlandığı revizyonlar gerçekten var


def test_sema_ve_veriye_dokunmaz():
    modul = _yukle()
    assert modul.upgrade() is None and modul.downgrade() is None
    kaynak = MIGRASYON.read_text(encoding="utf-8")
    assert "op." not in kaynak and "import op" not in kaynak                                       # hiç işlem yok


def test_zincirde_tek_head_kalir():
    """Birleştirmeden sonra zincir tek uçludur (head başka bir sonraki migration olabilir; kimliği sabit beklenmez)."""
    kod, mesaj = kontrol_et()
    assert kod == 0, mesaj
