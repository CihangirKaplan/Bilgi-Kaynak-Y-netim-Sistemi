"""TKYS yedek rotasyonu güvenlik testleri."""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "yedek_rotasyonu.py"


def sahte_pg_dump(klasor, basarili=True):
    """Windows'ta ve Linux'ta çalışan sahte pg_dump: Python betiği + küçük çalıştırıcı.

    Aldığı veritabanı adını klasor/son_veritabani.txt dosyasına yazar. basarili=False ise
    yarım bir dosya bırakıp hata koduyla çıkar. Yolunu (PG_DUMP_PATH için) döndürür.
    """
    py = klasor / "sahte_pg_dump.py"
    py.write_text(
        "import pathlib, sys\n"
        "a = sys.argv[1:]\n"
        "pathlib.Path(__file__).with_name('son_veritabani.txt').write_text(a[-1])\n"
        "if '--file' in a:\n"
        f"    pathlib.Path(a[a.index('--file') + 1]).write_text({'yedek icerigi' if basarili else 'eksik yedek'!r})\n"
        f"sys.exit({0 if basarili else 1})\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        komut = klasor / "pg_dump.bat"
        komut.write_bytes(f'@echo off\r\n"{sys.executable}" "{py}" %*\r\n'.encode("utf-8"))
    else:
        komut = klasor / "pg_dump"
        komut.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n')
        komut.chmod(0o755)
    return komut


def rotasyon_calistir(klasor, *parametreler):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *parametreler],
        capture_output=True,
        text=True,
        cwd=klasor,
        check=False,
    )


@pytest.fixture
def yedek_ortami(tmp_path):
    """Gerçek backups klasörünü kullanmadan test ortamı oluştur."""
    script = tmp_path / "scripts" / "yedek_rotasyonu.py"
    script.parent.mkdir()
    script.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    klasor = tmp_path / "backups"
    klasor.mkdir()

    return script, klasor


def test_yedi_gunluk_onizleme(yedek_ortami):
    script, klasor = yedek_ortami
    dosya = klasor / "crkys_alembic_test_20200101_000000_000000.dump"
    dosya.write_text("sahte yedek")

    eski = time.time() - 10 * 86400
    os.utime(dosya, (eski, eski))

    sonuc = subprocess.run(
        [sys.executable, str(script), "--database", "crkys_alembic_test", "--days", "7"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Silinecek:" in sonuc.stdout
    assert dosya.exists()


def test_eski_yedek_silinir_yeni_korunur(yedek_ortami):
    script, klasor = yedek_ortami

    eski = klasor / "crkys_alembic_test_20200101_000000_000000.dump"
    yeni = klasor / "crkys_alembic_test_20261104_090000_000000.dump"

    eski.write_text("eski")
    yeni.write_text("yeni")

    zaman = time.time() - 10 * 86400
    os.utime(eski, (zaman, zaman))

    subprocess.run(
        [sys.executable, str(script), "--database", "crkys_alembic_test", "--days", "7", "--apply"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert not eski.exists()
    assert yeni.exists()


def test_gecersiz_saklama_suresi(yedek_ortami):
    script, _ = yedek_ortami

    sonuc = subprocess.run(
        [sys.executable, str(script), "--database", "crkys_alembic_test", "--days", "0"],
        capture_output=True,
        text=True,
    )

    assert sonuc.returncode != 0


def test_yedekleme_hatasinda_eksik_dosya_temizlenir(tmp_path):
    """pg_dump hata verirse yarım kalan yedek silinmeli."""
    kaynak = Path(__file__).resolve().parents[1] / "scripts" / "veritabani_yedekle.py"

    script = tmp_path / "scripts" / "veritabani_yedekle.py"
    script.parent.mkdir(exist_ok=True)
    script.write_text(kaynak.read_text(encoding="utf-8"), encoding="utf-8")

    ortam = os.environ.copy()
    ortam.update({
        "PG_DUMP_PATH": str(sahte_pg_dump(tmp_path, basarili=False)),
        "DB_NAME": "crkys_alembic_test",
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_USER": "test",
        "DB_PASSWORD": "test",
    })

    sonuc = subprocess.run(
        [sys.executable, str(script)],
        env=ortam,
        capture_output=True,
        text=True,
        check=False,
    )

    assert sonuc.returncode != 0
    assert list((tmp_path / "backups").glob("*.dump")) == []



# ------------------------------------------------------------------ ana veritabanı desteği
YEDEKLE = Path(__file__).resolve().parents[1] / "scripts" / "veritabani_yedekle.py"


def yedekle(tmp_path, *parametreler, db_name="crkys"):
    script = tmp_path / "scripts" / "veritabani_yedekle.py"
    script.parent.mkdir(exist_ok=True)
    script.write_text(YEDEKLE.read_text(encoding="utf-8"), encoding="utf-8")
    ortam = {k: v for k, v in os.environ.items() if k != "DB_NAME"}
    ortam.update({"PG_DUMP_PATH": str(sahte_pg_dump(tmp_path)),
                  "DB_HOST": "localhost", "DB_PORT": "5432", "DB_USER": "test", "DB_PASSWORD": "test"})
    if db_name:
        ortam["DB_NAME"] = db_name
    return subprocess.run([sys.executable, str(script), *parametreler], env=ortam, capture_output=True, text=True)


def test_varsayilan_olarak_env_deki_ana_veritabani_yedeklenir(tmp_path):
    sonuc = yedekle(tmp_path)                                  # DB_NAME=crkys, parametre yok
    assert sonuc.returncode == 0, sonuc.stderr
    dosyalar = list((tmp_path / "backups").glob("*.dump"))
    assert len(dosyalar) == 1 and dosyalar[0].name.startswith("crkys_")
    assert re.fullmatch(r"crkys_\d{8}_\d{6}_\d{6}\.dump", dosyalar[0].name)
    assert (tmp_path / "son_veritabani.txt").read_text().strip() == "crkys"


def test_database_parametresi_env_i_ezer_ve_test_veritabani_da_yedeklenir(tmp_path):
    sonuc = yedekle(tmp_path, "--database", "crkys_alembic_test")
    assert sonuc.returncode == 0, sonuc.stderr
    assert (tmp_path / "son_veritabani.txt").read_text().strip() == "crkys_alembic_test"
    assert list((tmp_path / "backups").glob("crkys_alembic_test_*.dump"))


@pytest.mark.parametrize("ad", ["crkys; DROP DATABASE x", "a-b", "../etc", "ad soyad", "x" * 64])
def test_gecersiz_veritabani_adi_reddedilir_ve_dosya_olusmaz(tmp_path, ad):
    sonuc = yedekle(tmp_path, "--database", ad)
    assert sonuc.returncode != 0
    assert not (tmp_path / "backups").exists() or not list((tmp_path / "backups").glob("*.dump"))
    assert not (tmp_path / "son_veritabani.txt").exists()      # pg_dump hiç çağrılmadı


def test_veritabani_adi_hic_verilmezse_hata(tmp_path):
    sonuc = yedekle(tmp_path, db_name=None)
    assert sonuc.returncode != 0
    assert not (tmp_path / "son_veritabani.txt").exists()


# ------------------------------------------------------------ rotasyon: yalnız seçilen veritabanı
def test_rotasyon_baska_veritabanlarinin_yedeklerine_dokunmaz(yedek_ortami):
    script, klasor = yedek_ortami
    zaman = time.time() - 30 * 86400
    ana = klasor / "crkys_20200101_000000_000000.dump"
    test = klasor / "crkys_alembic_test_20200101_000000_000000.dump"
    elle = klasor / "crkys_elle_alinan.dump"
    yabanci = klasor / "baska_20200101_000000_000000.dump"
    for d in (ana, test, elle, yabanci):
        d.write_text("x")
        os.utime(d, (zaman, zaman))

    subprocess.run([sys.executable, str(script), "--database", "crkys", "--days", "7", "--apply"],
                   check=True, capture_output=True, text=True)

    assert not ana.exists()                                    # yalnız seçilen veritabanının eski yedeği silinir
    assert test.exists() and elle.exists() and yabanci.exists()  # test DB yedeği, elle dosya, başka DB korunur


def test_rotasyon_veritabani_adi_olmadan_calismaz(tmp_path):
    script = tmp_path / "scripts" / "yedek_rotasyonu.py"
    script.parent.mkdir()
    script.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "backups").mkdir()
    ortam = {k: v for k, v in os.environ.items() if k != "DB_NAME"}
    sonuc = subprocess.run([sys.executable, str(script), "--apply"], env=ortam, capture_output=True, text=True)
    assert sonuc.returncode != 0
