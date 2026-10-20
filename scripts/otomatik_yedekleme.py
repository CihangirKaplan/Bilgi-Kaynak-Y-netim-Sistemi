"""TKYS otomatik test veritabani yedekleme ve rotasyon gorevi."""

import subprocess
import sys
from pathlib import Path

PROJE = Path(__file__).resolve().parents[1]
SCRIPTS = PROJE / "scripts"


def main():
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "veritabani_yedekle.py"),
            "--database",
            "crkys_alembic_test",
        ],
        check=True,
        cwd=PROJE,
    )

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "yedek_rotasyonu.py"),
            "--days",
            "7",
            "--apply",
        ],
        check=True,
        cwd=PROJE,
    )

    print("Otomatik yedekleme ve rotasyon tamamlandi.")


if __name__ == "__main__":
    main()
