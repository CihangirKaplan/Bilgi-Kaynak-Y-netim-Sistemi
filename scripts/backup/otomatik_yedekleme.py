"""TKYS otomatik veritabanı yedekleme ve rotasyon görevi.

Varsayılan olarak .env içindeki DB_NAME veritabanını yedekler, ardından o veritabanının
14 günden eski yedeklerini temizler. Zamanlanmış görev (Windows Görev Zamanlayıcı) bu betiği
parametresiz çalıştırır.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJE = Path(__file__).resolve().parents[2]
SCRIPTS = PROJE / "scripts" / "backup"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database", default=os.getenv("DB_NAME"))
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args(argv)

    if not args.database:
        parser.error("Veritabani adi belirtilmedi: --database verin veya .env icinde DB_NAME tanimlayin.")

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "veritabani_yedekle.py"),
            "--database",
            args.database,
        ],
        check=True,
        cwd=PROJE,
    )

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "yedek_rotasyonu.py"),
            "--database",
            args.database,
            "--days",
            str(args.days),
            "--apply",
        ],
        check=True,
        cwd=PROJE,
    )

    print("Otomatik yedekleme ve rotasyon tamamlandi.")


if __name__ == "__main__":
    main()
