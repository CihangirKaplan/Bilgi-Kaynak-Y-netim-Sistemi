"""cihazlar.durum onarım migrasyonu (c5a2e8f1d739): eski metin değerleri enum değerlerine çevrilir.
Gerçek PostgreSQL kullanılmaz; çevirme kuralı ve zincir bağlantısı sınanır."""
import importlib.util
from pathlib import Path

import pytest

DOSYA = (Path(__file__).resolve().parents[2] / "database" / "migrations" / "versions"
         / "c5a2e8f1d739_cihaz_durumu_enum_onarim.py")


@pytest.fixture(scope="module")
def migrasyon():
    spec = importlib.util.spec_from_file_location("cihaz_durumu_onarim", DOSYA)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.mark.parametrize("eski,yeni", [
    ("Kullanılabilir", "Kullanima_Hazir"), ("kullanilabilir", "Kullanima_Hazir"), ("KULLANILABİLİR", "Kullanima_Hazir"),
    ("Kullanıma Hazır", "Kullanima_Hazir"), ("kullanima_hazir", "Kullanima_Hazir"), (" Arızalı ", "Arizali"),
    ("Bakımda", "Bakimda"), ("Kalibrasyonda", "Kalibrasyonda"), ("Kullanım Dışı", "Kullanim_Disi"),
    ("Rezerve", "Rezerve"), ("Kullanimda", "Kullanimda"),
])
def test_eski_yazimlar_taninan_degere_cevrilir(migrasyon, eski, yeni):
    assert migrasyon.durumu_coz(eski) == yeni


@pytest.mark.parametrize("deger", ["Kullanima_Hazir", "Rezerve", "Kullanimda", "Arizali",
                                                              "Bakimda", "Kalibrasyonda", "Kullanim_Disi"])
def test_gecerli_degerler_degismez(migrasyon, deger):
    assert migrasyon.durumu_coz(deger) == deger


@pytest.mark.parametrize("deger", ["", "Bilinmiyor", "Hazır Değil", "xyz"])
def test_taninmayan_deger_none_doner(migrasyon, deger):
    assert migrasyon.durumu_coz(deger) is None


def test_migrasyon_zincirde_ve_tek_head_birakir(migrasyon):
    assert migrasyon.revision == "c5a2e8f1d739" and migrasyon.down_revision == "b3e8f1a5d472"
    assert set(migrasyon.ESLEME.values()) == set(migrasyon.GECERLI_DURUMLAR)
