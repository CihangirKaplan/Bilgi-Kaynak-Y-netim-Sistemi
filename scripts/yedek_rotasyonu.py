"""TKYS eski veritabani yedeklerini temizleme araci."""

import argparse
import time
from pathlib import Path

YEDEK_KLASORU = Path(__file__).resolve().parents[1] / "backups"
DOSYA_DESENI = "crkys_alembic_test_*.dump"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if args.days < 1:
        parser.error("Saklama suresi en az 1 gun olmalidir.")

    if not YEDEK_KLASORU.exists():
        print("Yedek klasoru bulunamadi.")
        return

    simdi = time.time()
    esik = simdi - args.days * 86400

    eski_dosyalar = [
        dosya
        for dosya in YEDEK_KLASORU.glob(DOSYA_DESENI)
        if dosya.is_file()
        and not dosya.is_symlink()
        and dosya.stat().st_mtime < esik
    ]

    if not eski_dosyalar:
        print("Temizlenecek eski yedek bulunamadi.")
        return

    for dosya in eski_dosyalar:
        if args.apply:
            dosya.unlink()
            print(f"Silindi: {dosya.name}")
        else:
            print(f"Silinecek: {dosya.name}")

    if not args.apply:
        print("Onizleme: hicbir dosya silinmedi.")


if __name__ == "__main__":
    main()
