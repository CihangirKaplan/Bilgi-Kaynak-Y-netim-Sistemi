"""TKYS PostgreSQL veritabanı yedekleme aracı.

Varsayılan olarak uygulamanın kullandığı veritabanını (.env içindeki DB_NAME) yedekler;
başka bir veritabanı için --database verilebilir. Yedekleme yalnızca okur, veritabanını
değiştirmez. Dosya adı: <veritabani>_<YYYYMMDD>_<HHMMSS>_<mikrosaniye>.dump
"""

import argparse
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

YEDEK_KLASORU = Path(__file__).resolve().parents[1] / "backups"
GECERLI_AD = re.compile(r"^[A-Za-z0-9_]{1,63}$")


def veritabani_adi_dogrula(ad):
    """Dosya adına ve komut satırına güvenle girebilecek bir PostgreSQL adı olmalı."""
    if not ad or not GECERLI_AD.fullmatch(ad):
        raise ValueError("Veritabanı adı yalnızca harf, rakam ve alt çizgi içerebilir.")
    return ad


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--database",
        default=os.getenv("DB_NAME"),
        help="Yedeklenecek veritabanı (varsayılan: .env içindeki DB_NAME)",
    )
    args = parser.parse_args(argv)

    if not args.database:
        parser.error("Veritabanı adı belirtilmedi: --database verin veya .env içinde DB_NAME tanımlayın.")
    try:
        veritabani_adi_dogrula(args.database)
    except ValueError as hata:
        parser.error(str(hata))

    YEDEK_KLASORU.mkdir(parents=True, exist_ok=True)
    zaman = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    hedef = YEDEK_KLASORU / f"{args.database}_{zaman}.dump"

    ortam = os.environ.copy()
    ortam["PGPASSWORD"] = ortam["DB_PASSWORD"]

    pg_dump = os.getenv("PG_DUMP_PATH") or shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError(
            "pg_dump bulunamadi. PostgreSQL bin klasorunu PATH'e "
            "ekleyin veya PG_DUMP_PATH tanimlayin."
        )

    komut = [
        pg_dump,
        "--format=custom",
        "--no-password",
        "--host", ortam["DB_HOST"],
        "--port", ortam["DB_PORT"],
        "--username", ortam["DB_USER"],
        "--file", str(hedef),
        args.database,
    ]

    try:
        subprocess.run(
            komut,
            env=ortam,
            check=True,
            timeout=300,
        )
        if not hedef.is_file() or hedef.stat().st_size == 0:
            raise RuntimeError("Yedek dosyası boş veya oluşturulamadı.")
    except Exception:
        hedef.unlink(missing_ok=True)
        raise

    print(f"Yedek oluşturuldu: {hedef.name}")
    print(f"Veritabanı: {args.database}")
    print(f"Dosya boyutu: {hedef.stat().st_size} bayt")


if __name__ == "__main__":
    main()
