"""Windows Task Scheduler icin TKYS yedekleme kurulumu."""

import os
import subprocess
import sys
from pathlib import Path


def windows_mu():
    return os.name == "nt"


def main():
    if not windows_mu():
        raise SystemExit("Bu kurulum yalnizca Windows'ta calisir.")

    proje = Path(__file__).resolve().parents[2]
    script = proje / "scripts" / "otomatik_yedekleme.py"

    if not script.is_file():
        raise SystemExit("Otomatik yedekleme scripti bulunamadi.")

    gorev_adi = "TKYS_Otomatik_Yedekleme"
    komut = subprocess.list2cmdline([sys.executable, str(script)])

    subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN", gorev_adi,
            "/TR", komut,
            "/SC", "DAILY",
            "/ST", "09:00",
            "/F",
        ],
        check=True,
    )

    print(f"Windows gorevi olusturuldu: {gorev_adi}")


if __name__ == "__main__":
    main()
