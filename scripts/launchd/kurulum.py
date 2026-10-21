"""TKYS macOS otomatik yedekleme gorevi kurulumu."""

import os
import plistlib
import shutil
import sys
from pathlib import Path

PROJE = Path(__file__).resolve().parents[2]
SCRIPT = PROJE / "scripts" / "otomatik_yedekleme.py"
HEDEF = Path.home() / "Library" / "LaunchAgents" / "tr.edu.tkys.backup.plist"

def main():
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise SystemExit("pg_dump bulunamadi. PostgreSQL PATH ayarini kontrol edin.")

    yapilandirma = {
        "Label": "tr.edu.tkys.backup",
        "ProgramArguments": [sys.executable, str(SCRIPT)],
        "WorkingDirectory": str(PROJE),
        "EnvironmentVariables": {
            "PATH": str(Path(pg_dump).resolve().parent)
            + os.pathsep
            + "/usr/bin:/bin:/usr/sbin:/sbin"
        },
        "StartCalendarInterval": {"Hour": 9, "Minute": 0},
        "StandardOutPath": "/tmp/tkys-backup.log",
        "StandardErrorPath": "/tmp/tkys-backup-error.log",
    }

    HEDEF.parent.mkdir(parents=True, exist_ok=True)
    with HEDEF.open("wb") as dosya:
        plistlib.dump(yapilandirma, dosya)

    print(f"Yapilandirma olusturuldu: {HEDEF}")
    print("Gorev henuz launchd sistemine yuklenmedi.")

if __name__ == "__main__":
    main()
