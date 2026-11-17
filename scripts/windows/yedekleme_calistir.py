"""Windows zamanlanmış TKYS yedekleme görevi."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJE = Path(__file__).resolve().parents[2]
LOG_KLASORU = PROJE / "logs"
LOG_DOSYASI = LOG_KLASORU / "yedekleme.log"


def calistir():
    os.chdir(PROJE)
    load_dotenv(PROJE / ".env")

    LOG_KLASORU.mkdir(parents=True, exist_ok=True)

    komut = [
        sys.executable,
        str(PROJE / "scripts" / "backup" / "otomatik_yedekleme.py"),
    ]

    with LOG_DOSYASI.open("a", encoding="utf-8") as log:
        log.write(
            f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] "
            "Yedekleme başlatıldı.\n"
        )
        log.flush()

        try:
            sonuc = subprocess.run(
                komut,
                cwd=PROJE,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            log.write(
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                f"Yedekleme çıkış kodu: {sonuc.returncode}\n"
            )
            return sonuc.returncode
        except Exception as hata:
            log.write(
                f"[{datetime.now():%Y-%m-%d %H:%M:%S}] "
                f"Yedekleme başlatılamadı: {hata}\n"
            )
            return 1


if __name__ == "__main__":
    sys.exit(calistir())
