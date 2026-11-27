"""Yayın öncesi kontrol betiği (scripts/yayin_oncesi_kontrol.py): tutarsızlığı HATA, yayın günü eksiklerini UYARI olarak bildirir;
belge geçişi (develop -> main) yalnızca git komutlarını değiştirir. Gerçek veritabanı/ağ kullanılmaz; sahte proje ağacı geçici klasörde kurulur."""
import importlib.util
import shutil
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[2]
BETIK = KOK / "scripts" / "yayin_oncesi_kontrol.py"


@pytest.fixture(scope="module")
def y():
    spec = importlib.util.spec_from_file_location("yayin_oncesi_kontrol", BETIK)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def sahte_agac(tmp_path, y, istemci="1.0.0", sunucu="1.0.0", changelog="## [1.0.0] — 01.12.2026", notlar="# TKYS 1.0.0 — Sürüm Notları\n| Yayın tarihi | 01.12.2026 |",
               go="| 1 | Build | Ekip | CI | ☑ |", belge="    git checkout develop\n    git pull origin develop\n"):
    for yol, icerik in {
        "client/surum.py": f'SURUM = "{istemci}"\n', "server/surum.py": f'SURUM = "{sunucu}"\n',
        "CHANGELOG.md": changelog + "\n", "RELEASE_NOTES.md": notlar + "\n",
        "docs/test-reports/GO-NO-GO_Kontrol_Listesi.md": go + "\n",
    }.items():
        (tmp_path / yol).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / yol).write_text(icerik, encoding="utf-8")
    for yol in y.KURULUM_BELGELERI:
        (tmp_path / yol).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / yol).write_text(belge, encoding="utf-8", newline="")
    (tmp_path / "database" / "migrations" / "versions").mkdir(parents=True)
    (tmp_path / "database" / "migrations" / "versions" / "aaa_ilk.py").write_text(
        '"""ilk"""\nrevision = "aaa"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n\ndef upgrade():\n    pass\n\ndef downgrade():\n    pass\n',
        encoding="utf-8")
    return tmp_path


def durumlar(y, kok):
    return {ad: durum for durum, ad, _ in y.kontroller(kok)}


def test_gercek_projede_hata_yok(y):
    assert not [s for s in y.kontroller(KOK) if s[0] == y.HATA]


def test_surum_uyusmazligi_hatadir(y, tmp_path):
    d = durumlar(y, sahte_agac(tmp_path, y, istemci="1.0.1"))
    assert d["Sürüm numarası"] == y.HATA


def test_changelog_ve_notlarda_surum_yoksa_hata(y, tmp_path):
    d = durumlar(y, sahte_agac(tmp_path, y, changelog="## [0.9.0]", notlar="# TKYS 0.9"))
    assert d["CHANGELOG"] == y.HATA and d["RELEASE_NOTES"] == y.HATA


def test_yayin_gunu_eksikleri_uyaridir(y, tmp_path):
    kok = sahte_agac(tmp_path, y, changelog="## [1.0.0] — Yayın tarihi: GO/NO-GO kararından sonra yazılacak",
                     go="| 1 | Build | Ekip | CI | ☐ |\n| 2 | Test | Ekip | CI | ☐ |")
    d = durumlar(y, kok)
    assert d["Yayın tarihi/alanı: CHANGELOG.md"] == y.UYARI and d["GO/NO-GO maddeleri"] == y.UYARI
    assert d["Kurulum belgeleri hâlâ develop'u izliyor"] == y.UYARI
    assert y.ana([], kok=kok) == 0                  # UYARI tek başına başarısızlık değildir
    assert y.ana(["--go"], kok=kok) == 1            # yayın anında UYARI da HATA'dır


def test_belgeler_main_yapilinca_hazir_olur(y, tmp_path):
    kok = sahte_agac(tmp_path, y)
    assert y.ana(["--belgeleri-main-yap"], kok=kok) == 0
    for yol in y.KURULUM_BELGELERI:
        metin = (kok / yol).read_text(encoding="utf-8")
        assert "git checkout main" in metin and "git pull origin main" in metin and "develop" not in metin
    assert y.ana(["--go"], kok=kok) == 0            # her şey tamam: yayın anı kontrolü geçer
    assert y.belgeleri_main_yap(kok) == []          # ikinci çalıştırma bir şey değiştirmez


def test_belge_gecisi_yalniz_komutlari_degistirir_ve_satir_sonunu_korur(y, tmp_path):
    belge = "Açıklama: develop'ta iki head olursa bildirin.\r\ngit switch develop\r\ngit pull --ff-only origin develop\r\n"
    kok = sahte_agac(tmp_path, y, belge=belge)
    y.belgeleri_main_yap(kok)
    ham = (kok / y.KURULUM_BELGELERI[0]).read_bytes().decode("utf-8")
    assert ham == "Açıklama: develop'ta iki head olursa bildirin.\r\ngit switch main\r\ngit pull --ff-only origin main\r\n"


def test_cok_head_hatadir(y, tmp_path):
    kok = sahte_agac(tmp_path, y)
    (kok / "database" / "migrations" / "versions" / "bbb_ikinci.py").write_text(
        '"""ikinci"""\nrevision = "bbb"\ndown_revision = None\nbranch_labels = None\ndepends_on = None\n\ndef upgrade():\n    pass\n\ndef downgrade():\n    pass\n',
        encoding="utf-8")
    assert durumlar(y, kok)["Alembic zinciri"] == y.HATA
