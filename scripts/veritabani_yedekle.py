"""TKYS PostgreSQL veritabanı yedekleme aracı."""

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TEST_DB = "crkys_alembic_test"
YEDEK_KLASORU = Path(__file__).resolve().parents[1] / "backups"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=TEST_DB)
    args = parser.parse_args()

    if args.database != TEST_DB:
        parser.error("Şimdilik yalnızca test veritabanı yedeklenebilir.")

    YEDEK_KLASORU.mkdir(parents=True, exist_ok=True)
    zaman = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    hedef = YEDEK_KLASORU / f"{args.database}_{zaman}.dump"

    ortam = os.environ.copy()
    ortam["PGPASSWORD"] = ortam["DB_PASSWORD"]

    komut = [
        "pg_dump",
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
    print(f"Dosya boyutu: {hedef.stat().st_size} bayt")


if __name__ == "__main__":
    main()
