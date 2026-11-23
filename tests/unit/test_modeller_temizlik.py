"""server/modeller.py temizliği: ölü modeller kalkar, gerekenler kalır, kimlik listelerine üst sınır konur."""
import pytest
from pydantic import ValidationError

from server import modeller


@pytest.mark.parametrize("ad", ["KullaniciModeli", "OdaModeli", "DashboardOzetModeli", "YaklasanIslemModeli"])
def test_kullanilmayan_modeller_kaldirildi(ad):
    assert not hasattr(modeller, ad)


@pytest.mark.parametrize("ad", ["Base", "Oda", "RandevuModeli", "CihazModeli", "DanisanKoduModeli", "RolModeli"])
def test_baska_yerlerde_kullanilan_siniflar_korundu(ad):
    assert hasattr(modeller, ad)           # Base/Oda: alembic env.py ve testler; diğerleri güvenlik ve alan testleri


def test_kullanilmayan_sqlalchemy_importlari_kalktı():
    for ad in ("Float", "DateTime", "ForeignKey"):
        assert not hasattr(modeller, ad)


def test_alembic_metadata_hala_odalar_tablosunu_icerir():
    assert "odalar" in modeller.Base.metadata.tables


def test_kimlik_listelerinde_ust_sinir_vardir():
    sinir = modeller.LISTE_EN_FAZLA_ID
    assert sinir == 200
    cok = list(range(1, sinir + 2))
    tamam = list(range(1, sinir + 1))
    assert modeller.IzinDuzenleModeli(gorunen_ad="x", verilen_rol_idleri=tamam)
    with pytest.raises(ValidationError):
        modeller.IzinDuzenleModeli(gorunen_ad="x", verilen_rol_idleri=cok)
    assert modeller.KullaniciOlusturModeli(kullanici_adi="abc", rol_id=1, oda_idleri=tamam)
    with pytest.raises(ValidationError):
        modeller.KullaniciOlusturModeli(kullanici_adi="abc", rol_id=1, oda_idleri=cok)
    assert modeller.RolDegistirModeli(rol_id=1, oda_idleri=tamam)
    with pytest.raises(ValidationError):
        modeller.RolDegistirModeli(rol_id=1, oda_idleri=cok)


def test_bos_ve_gonderilmeyen_listeler_eskisi_gibi_calisir():
    assert modeller.KullaniciOlusturModeli(kullanici_adi="abc", rol_id=1).oda_idleri == []
    assert modeller.RolDegistirModeli(rol_id=1).oda_idleri is None
    assert modeller.IzinDuzenleModeli(gorunen_ad="x", verilen_rol_idleri=[]).verilen_rol_idleri == []
