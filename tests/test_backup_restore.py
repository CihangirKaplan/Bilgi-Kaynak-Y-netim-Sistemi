"""TKYS yedek rotasyonu güvenlik testleri."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "yedek_rotasyonu.py"


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
    script.write_text(SCRIPT.read_text())

    klasor = tmp_path / "backups"
    klasor.mkdir()

    return script, klasor


def test_yedi_gunluk_onizleme(yedek_ortami):
    script, klasor = yedek_ortami
    dosya = klasor / "crkys_alembic_test_eski.dump"
    dosya.write_text("sahte yedek")

    eski = time.time() - 10 * 86400
    os.utime(dosya, (eski, eski))

    sonuc = subprocess.run(
        [sys.executable, str(script), "--days", "7"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Silinecek:" in sonuc.stdout
    assert dosya.exists()


def test_eski_yedek_silinir_yeni_korunur(yedek_ortami):
    script, klasor = yedek_ortami

    eski = klasor / "crkys_alembic_test_eski.dump"
    yeni = klasor / "crkys_alembic_test_yeni.dump"

    eski.write_text("eski")
    yeni.write_text("yeni")

    zaman = time.time() - 10 * 86400
    os.utime(eski, (zaman, zaman))

    subprocess.run(
        [sys.executable, str(script), "--days", "7", "--apply"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert not eski.exists()
    assert yeni.exists()


def test_gecersiz_saklama_suresi(yedek_ortami):
    script, _ = yedek_ortami

    sonuc = subprocess.run(
        [sys.executable, str(script), "--days", "0"],
        capture_output=True,
        text=True,
    )

    assert sonuc.returncode != 0


def test_yedekleme_hatasinda_eksik_dosya_temizlenir(tmp_path):
    """pg_dump hata verirse yarım kalan yedek silinmeli."""
    kaynak = Path(__file__).resolve().parents[1] / "scripts" / "veritabani_yedekle.py"

    script = tmp_path / "scripts" / "veritabani_yedekle.py"
    script.parent.mkdir(exist_ok=True)
    script.write_text(kaynak.read_text())

    sahte_komut = tmp_path / "pg_dump"
    sahte_komut.write_text("""#!/bin/sh
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--file" ]; then
        shift
        printf 'eksik yedek' > "$1"
        exit 1
    fi
    shift
done
exit 1
""")
    sahte_komut.chmod(0o755)

    ortam = os.environ.copy()
    ortam.update({
        "PATH": str(tmp_path) + os.pathsep + ortam.get("PATH", ""),
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
