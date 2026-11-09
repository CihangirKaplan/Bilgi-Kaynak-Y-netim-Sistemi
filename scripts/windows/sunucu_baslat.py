"""TKYS sunucusunu başlatır ve kapanırsa yeniden başlatır.

Windows Görev Zamanlayıcı (scripts/windows/sunucu_kurulum.py) bilgisayar açılınca bu betiği çalıştırır.
Sırayla şunları yapar:
  1. PostgreSQL'in bağlantı kabul etmesini bekler (bilgisayar yeni açılmışsa veritabanı henüz hazır olmayabilir).
  2. uvicorn ile sunucuyu başlatır (varsayılan: tüm ağ arayüzleri, 8000 numaralı port).
  3. Sunucu beklenmedik şekilde kapanırsa kısa bir süre sonra yeniden başlatır.
Çıktılar logs/sunucu.log dosyasına yazılır (5 MB'ı aşınca yeni dosyaya geçilir).

Ayarlar .env ya da ortam değişkenleriyle verilir: TKYS_HOST (varsayılan 0.0.0.0), TKYS_PORT (varsayılan 8000).
Elle denemek için proje klasöründe:  python scripts/windows/sunucu_baslat.py
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJE = Path(__file__).resolve().parents[2]
LOG_KLASORU = PROJE / "logs"
LOG_DOSYASI = LOG_KLASORU / "sunucu.log"
LOG_ENIYI_BOYUT = 5 * 1024 * 1024          # 5 MB
VERITABANI_BEKLEME_SANIYE = 120
YENIDEN_BASLATMA_BEKLEME_SANIYE = 10


def ayarlar():
    """(host, port, veritabani_host, veritabani_port) — .env ve ortam değişkenlerinden."""
    host = os.getenv("TKYS_HOST", "0.0.0.0")
    try:
        port = int(os.getenv("TKYS_PORT", "8000"))
    except ValueError:
        raise SystemExit("TKYS_PORT sayı olmalıdır.")
    if not 1 <= port <= 65535:
        raise SystemExit("TKYS_PORT 1-65535 arasında olmalıdır.")
    db_host = os.getenv("DB_HOST") or "localhost"
    try:
        db_port = int(os.getenv("DB_PORT") or "5432")
    except ValueError:
        raise SystemExit("DB_PORT sayı olmalıdır.")
    return host, port, db_host, db_port


def sunucu_komutu(host, port):
    return [sys.executable, "-m", "uvicorn", "sunucu:app", "--host", host, "--port", str(port)]


def veritabani_hazir_mi(db_host, db_port, zaman_asimi=3):
    """PostgreSQL portu bağlantı kabul ediyor mu?"""
    try:
        with socket.create_connection((db_host, db_port), timeout=zaman_asimi):
            return True
    except OSError:
        return False


def veritabanini_bekle(db_host, db_port, en_fazla=VERITABANI_BEKLEME_SANIYE, bekle=time.sleep, simdi=time.monotonic):
    """Veritabanı hazır olunca True; süre dolarsa False döner."""
    bitis = simdi() + en_fazla
    while True:
        if veritabani_hazir_mi(db_host, db_port):
            return True
        if simdi() >= bitis:
            return False
        bekle(5)


def log_dosyasini_hazirla():
    """logs/ klasörünü açar; dosya çok büyüdüyse sunucu.log.1 olarak kenara alır."""
    LOG_KLASORU.mkdir(exist_ok=True)
    if LOG_DOSYASI.exists() and LOG_DOSYASI.stat().st_size > LOG_ENIYI_BOYUT:
        eski = LOG_DOSYASI.with_name(LOG_DOSYASI.name + ".1")
        if eski.exists():
            eski.unlink()
        LOG_DOSYASI.rename(eski)


def yaz(log, mesaj):
    log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {mesaj}\n")
    log.flush()


def calistir(maks_tur=None, bekle=time.sleep):
    """Sunucuyu çalıştırır; kapanırsa yeniden başlatır. maks_tur yalnızca testlerde kullanılır."""
    os.chdir(PROJE)                       # zamanlanmış görev başka bir klasörde başlatabilir
    load_dotenv(PROJE / ".env")
    host, port, db_host, db_port = ayarlar()
    tur = 0
    while maks_tur is None or tur < maks_tur:
        tur += 1
        log_dosyasini_hazirla()
        with open(LOG_DOSYASI, "a", encoding="utf-8") as log:
            if not veritabanini_bekle(db_host, db_port, bekle=bekle):
                yaz(log, f"Veritabanı ({db_host}:{db_port}) {VERITABANI_BEKLEME_SANIYE} saniyede hazır olmadı; sunucu yine de başlatılıyor.")
            yaz(log, f"Sunucu başlatılıyor: http://{host}:{port}")
            sonuc = subprocess.run(sunucu_komutu(host, port), cwd=PROJE, stdout=log, stderr=subprocess.STDOUT)
            yaz(log, f"Sunucu kapandı (çıkış kodu {sonuc.returncode}); {YENIDEN_BASLATMA_BEKLEME_SANIYE} saniye sonra yeniden başlatılacak.")
        bekle(YENIDEN_BASLATMA_BEKLEME_SANIYE)


if __name__ == "__main__":
    try:
        calistir()
    except KeyboardInterrupt:
        pass
