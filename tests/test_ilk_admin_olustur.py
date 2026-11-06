"""İlk yönetici betiği: sahte imleçle, gerçek veritabanına dokunmaz."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_yol = Path(__file__).resolve().parents[1] / "scripts" / "ilk_admin_olustur.py"
_spec = importlib.util.spec_from_file_location("ilk_admin_olustur", _yol)
betik = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(betik)


def imlec(*sonuclar):
    """fetchone sırayla verilen sonuçları döndürür."""
    c = MagicMock()
    c.fetchone.side_effect = list(sonuclar)
    return c


def calisan_sorgular(c):
    return [cagri.args[0] for cagri in c.execute.call_args_list]


def test_admin_yoksa_olusturur_ve_ilk_giris_zorunlu_kilar():
    c = imlec((7,), None, None, (42,), (0,))
    ad, parola, kod = betik.admin_olustur(c, "yonetici")
    assert (ad, kod) == ("yonetici", "PER-ADM-001") and len(parola) >= 12
    ekle = next(q for q in c.execute.call_args_list if "INSERT INTO kullanicilar" in q.args[0])
    assert "TRUE, TRUE" in ekle.args[0]                     # aktif_mi, ilk_giris_mi
    assert ekle.args[1][0] == "yonetici" and ekle.args[1][1] != parola   # parola düz yazı saklanmaz
    assert ekle.args[1][2] == 7
    assert any("INSERT INTO personel" in q for q in calisan_sorgular(c))


def test_zaten_admin_varsa_hicbir_sey_eklemez():
    c = imlec((7,), (1,))
    with pytest.raises(betik.IlkAdminHatasi, match="zaten bir ADMIN"):
        betik.admin_olustur(c, "yonetici")
    assert not any("INSERT" in q for q in calisan_sorgular(c))


def test_admin_rolu_yoksa_migration_hatirlatir():
    with pytest.raises(betik.IlkAdminHatasi, match="alembic upgrade head"):
        betik.admin_olustur(imlec(None), "yonetici")


def test_kullanici_adi_baska_hesapta_kullaniliyorsa_reddeder():
    c = imlec((7,), None, (9,))
    with pytest.raises(betik.IlkAdminHatasi, match="zaten kullanılıyor"):
        betik.admin_olustur(c, "yonetici")
    assert not any("INSERT" in q for q in calisan_sorgular(c))


@pytest.mark.parametrize("ad", ["", "ab", "bosluk var", "a;drop", "x" * 51, None])
def test_gecersiz_kullanici_adi_veritabanina_gitmeden_reddedilir(ad):
    c = imlec()
    with pytest.raises(betik.IlkAdminHatasi):
        betik.admin_olustur(c, ad)
    c.execute.assert_not_called()


def test_her_calistirmada_farkli_gecici_parola_uretilir():
    parolalar = {betik.admin_olustur(imlec((7,), None, None, (1,), (0,)), "yonetici")[1] for _ in range(5)}
    assert len(parolalar) == 5
