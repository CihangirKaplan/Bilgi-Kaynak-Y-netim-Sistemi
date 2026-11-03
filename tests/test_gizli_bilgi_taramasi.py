"""SEC-T10 - Secret Scan: depoda düz yazılı parola/anahtar bulunmamalı.

Git'in izlediği dosyalar taranır. Gizli bilgiler `.env` dosyasından okunmalıdır.
"""
import re
import subprocess
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]

TARANAN_UZANTILAR = {".py", ".md", ".sql", ".ini", ".txt", ".yml", ".yaml", ".bat", ".ps1", ".sh", ".cfg"}
ATLANAN_YOLLAR = ("tests/", "alembic/versions/")

GIZLI_AD = r"(?:db_pass(?:word)?|jwt_secret|secret_key|api_key|passwd|pg_?password)"

YASAK_DESENLER = {
    "gizli değişkene düz metin atanmış": re.compile(
        rf"(?i)\b{GIZLI_AD}\b\s*=\s*[\"'][^\"']+[\"']"
    ),
    "gizli ortam değişkeni için varsayılan değer verilmiş": re.compile(
        rf"(?i)getenv\(\s*[\"']{GIZLI_AD}[\"']\s*,\s*[\"'][^\"']+[\"']"
    ),
    "bağlantıda password= düz metin": re.compile(
        r"(?i)\bpassword\s*=\s*[\"'][^\"']+[\"']"
    ),
}


def izlenen_dosyalar():
    try:
        cikti = subprocess.run(
            ["git", "ls-files"], cwd=KOK, capture_output=True, text=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git bulunamadı veya bu klasör bir git deposu değil")
    return [KOK / satir for satir in cikti.splitlines() if satir]


def test_env_dosyasi_depoya_girmemis():
    izlenenler = [p.name for p in izlenen_dosyalar()]
    assert ".env" not in izlenenler, ".env dosyası git'e eklenmiş; gizli bilgiler sızar"


def test_depoda_duz_yazili_gizli_bilgi_yok():
    bulgular = []

    for yol in izlenen_dosyalar():
        goreli = yol.relative_to(KOK).as_posix()
        if yol.suffix.lower() not in TARANAN_UZANTILAR or goreli.startswith(ATLANAN_YOLLAR):
            continue
        try:
            metin = yol.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for numara, satir in enumerate(metin.splitlines(), start=1):
            for aciklama, desen in YASAK_DESENLER.items():
                if desen.search(satir):
                    bulgular.append(f"{goreli}:{numara}  [{aciklama}]  {satir.strip()[:80]}")

    assert not bulgular, "Düz yazılı gizli bilgi bulundu:\n" + "\n".join(bulgular)