"""TKYS eski veritabanı yedeklerini temizleme aracı.

Yalnızca seçilen veritabanının yedeklerini siler (varsayılan: .env içindeki DB_NAME).
Dosya adı tam olarak <veritabani>_<YYYYMMDD>_<HHMMSS>_<mikrosaniye>.dump biçiminde
olmalıdır; başka veritabanlarının yedeklerine ve elle konmuş dosyalara dokunulmaz.
Varsayılan davranış önizlemedir; silmek için --apply gerekir.
"""

import argparse
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

YEDEK_KLASORU = Path(__file__).resolve().parents[1] / "backups"
GECERLI_AD = re.compile(r"^[A-Za-z0-9_]{1,63}$")


def dosya_deseni(veritabani):
    return re.compile(rf"^{re.escape(veritabani)}_\d{{8}}_\d{{6}}_\d{{6}}\.dump$")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--database",
        default=os.getenv("DB_NAME"),
        help="Yedekleri temizlenecek veritabanı (varsayılan: .env içindeki DB_NAME)",
    )
    args = parser.parse_args(argv)

    if args.days < 1:
        parser.error("Saklama suresi en az 1 gun olmalidir.")
    if not args.database or not GECERLI_AD.fullmatch(args.database):
        parser.error("Gecerli bir veritabani adi gerekli: --database verin veya .env icinde DB_NAME tanimlayin.")

    if not YEDEK_KLASORU.exists():
        print("Yedek klasoru bulunamadi.")
        return

    desen = dosya_deseni(args.database)
    esik = time.time() - args.days * 86400

    eski_dosyalar = [
        dosya
        for dosya in YEDEK_KLASORU.iterdir()
        if desen.fullmatch(dosya.name)
        and dosya.is_file()
        and not dosya.is_symlink()
        and dosya.stat().st_mtime < esik
    ]

    if not eski_dosyalar:
        print("Temizlenecek eski yedek bulunamadi.")
        return

    for dosya in sorted(eski_dosyalar):
        if args.apply:
            dosya.unlink()
            print(f"Silindi: {dosya.name}")
        else:
            print(f"Silinecek: {dosya.name}")

    if not args.apply:
        print("Onizleme: hicbir dosya silinmedi.")


if __name__ == "__main__":
    main()
