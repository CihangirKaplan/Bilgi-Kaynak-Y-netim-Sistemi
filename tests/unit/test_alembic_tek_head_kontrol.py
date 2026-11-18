"""Alembic tek head denetim betiği (scripts/alembic_tek_head_kontrol.py): çoklu head'i, bozuk zinciri ve sağlam zinciri tanır.
Gerçek veritabanı kullanılmaz; sahte migration dizinleri geçici klasörde kurulur."""
import importlib.util
from pathlib import Path

import pytest

BETIK = Path(__file__).resolve().parents[2] / "scripts" / "alembic_tek_head_kontrol.py"


@pytest.fixture(scope="module")
def betik():
    spec = importlib.util.spec_from_file_location("alembic_tek_head_kontrol", BETIK)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def migrasyon_dizini(tmp_path, zincir):
    """zincir: [(revizyon, down_revision)] -> geçici alembic betik dizini."""
    (tmp_path / "versions").mkdir()
    for rev, down in zincir:
        (tmp_path / "versions" / f"{rev}_deneme.py").write_text(
            f'"""{rev} deneme migrasyonu"""\nrevision = "{rev}"\ndown_revision = {down!r}\n'
            "branch_labels = None\ndepends_on = None\n\ndef upgrade():\n    pass\n\ndef downgrade():\n    pass\n",
            encoding="utf-8")
    return tmp_path


def test_projenin_gercek_zincirinde_tek_head_vardir(betik):
    kod, mesaj = betik.kontrol_et()
    assert kod == 0 and mesaj.startswith("Tek head var: ")


def test_duz_zincir_tek_head(betik, tmp_path):
    kod, mesaj = betik.kontrol_et(migrasyon_dizini(tmp_path, [("a1", None), ("b1", "a1"), ("c1", "b1")]))
    assert kod == 0 and "c1" in mesaj


def test_iki_pr_ayni_noktadan_dallanirsa_hata_verir_ve_cozumu_anlatir(betik, tmp_path):
    kod, mesaj = betik.kontrol_et(migrasyon_dizini(tmp_path, [("a1", None), ("b1", "a1"), ("c1", "a1")]))
    assert kod == 1
    assert "Birden fazla migration head'i var (2)" in mesaj
    assert "b1" in mesaj and "c1" in mesaj                  # iki head de adıyla listelenir
    assert "b1_deneme.py" in mesaj and "c1_deneme.py" in mesaj   # dosyaları gösterilir
    assert "down_revision" in mesaj and "git merge origin/develop" in mesaj


def test_birlestirme_migrasyonu_ile_tek_head_olur(betik, tmp_path):
    zincir = [("a1", None), ("b1", "a1"), ("c1", "a1"), ("m1", ("b1", "c1"))]
    kod, mesaj = betik.kontrol_et(migrasyon_dizini(tmp_path, zincir))
    assert kod == 0 and "m1" in mesaj


@pytest.mark.filterwarnings("ignore:Revision .* is not present:UserWarning")
def test_olmayan_revizyona_baglanan_bozuk_zincir_hata_verir(betik, tmp_path):
    kod, mesaj = betik.kontrol_et(migrasyon_dizini(tmp_path, [("a1", None), ("b1", "yok_boyle_bir_revizyon")]))
    assert kod == 1 and "zinciri okunamadı" in mesaj


def test_github_ortaminda_hata_pr_ekraninda_gorunecek_etiketle_yazilir(betik, tmp_path, monkeypatch, capsys):
    cift = migrasyon_dizini(tmp_path, [("a1", None), ("b1", "a1"), ("c1", "a1")])
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(betik, "kontrol_et", lambda: betik.__class__ and (1, "satir1\nsatir2 %"))
    assert betik.main() == 1
    cikti = capsys.readouterr().out
    assert "::error title=Alembic migration zinciri hatali::satir1%0Asatir2 %25" in cikti
    assert cift.exists()


def test_tek_head_icin_main_sifir_doner_ve_etiket_yazmaz(betik, monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert betik.main() == 0
    assert "::error" not in capsys.readouterr().out
