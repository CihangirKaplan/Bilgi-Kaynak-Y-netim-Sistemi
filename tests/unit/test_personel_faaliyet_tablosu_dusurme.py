"""personel_faaliyet_kayitlari tablosunu düşüren migrasyonun (d5b9f2c7a418) sahte veritabanı gerektirmeyen denetimleri."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

MIGRASYON = Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions" / "d5b9f2c7a418_personel_faaliyet_kayitlari_dusur.py"


def _yukle():
    spec = importlib.util.spec_from_file_location("personel_faaliyet_dusur", MIGRASYON)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _sorgular(islev, modul):
    with patch.object(modul, "op", MagicMock()) as op:
        getattr(modul, islev)()
    return [cagri.args[0] for cagri in op.execute.call_args_list]


def test_zincire_dogru_baglanir():
    modul = _yukle()
    assert modul.revision == "d5b9f2c7a418"
    assert modul.down_revision == "c8f2a5d1e704"


def test_yukseltme_once_veri_denetler_sonra_tabloyu_dusurur():
    sorgular = _sorgular("upgrade", _yukle())
    assert len(sorgular) == 2
    assert "RAISE EXCEPTION" in sorgular[0] and "SELECT 1 FROM personel_faaliyet_kayitlari" in sorgular[0]
    assert sorgular[1] == "DROP TABLE IF EXISTS personel_faaliyet_kayitlari"


def test_yukseltme_baska_tabloya_dokunmaz():
    sorgular = " ".join(_sorgular("upgrade", _yukle()))
    for baska in ("ogrenci_faaliyet_takip", "faaliyetler", "faaliyet_birimleri", "personel "):
        assert baska not in sorgular.replace("personel_faaliyet_kayitlari", "")


def test_geri_alma_tabloyu_ve_indeksleri_yeniden_olusturur():
    sorgular = _sorgular("downgrade", _yukle())
    tablo = sorgular[0]
    assert "CREATE TABLE IF NOT EXISTS personel_faaliyet_kayitlari" in tablo
    assert "REFERENCES faaliyetler(faaliyet_id)" in tablo and "REFERENCES faaliyet_birimleri(birim_id)" in tablo
    assert any('"ix_personel_faaliyet_kayitlari_birim_id"' in s for s in sorgular)
    assert any('"ix_personel_faaliyet_kayitlari_faaliyet_id"' in s for s in sorgular)
