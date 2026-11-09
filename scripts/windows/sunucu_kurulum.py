"""TKYS sunucusunun Windows açılınca kendiliğinden başlaması için Görev Zamanlayıcı kurulumu.

Kurulum (YÖNETİCİ olarak açılmış PowerShell'de, proje klasöründe, sanal ortam etkinken):
    python scripts/windows/sunucu_kurulum.py              # bilgisayar açılınca (kimse giriş yapmasa da)
    python scripts/windows/sunucu_kurulum.py --oturum     # yalnızca bu kullanıcı giriş yapınca
    python scripts/windows/sunucu_kurulum.py --kaldir     # görevi siler

Görev "TKYS_Sunucu" adıyla oluşturulur ve scripts/windows/sunucu_baslat.py dosyasını çalıştırır.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

GOREV_ADI = "TKYS_Sunucu"


def windows_mu():
    return os.name == "nt"


def gorev_komutu(python_yolu, betik_yolu):
    """Görevin çalıştıracağı komut satırı."""
    return subprocess.list2cmdline([str(python_yolu), str(betik_yolu)])


def olusturma_komutu(komut, oturum_acilinca):
    """schtasks /Create argümanları. Varsayılan: açılışta, SYSTEM hesabıyla, 30 sn gecikmeyle."""
    arguman = ["schtasks", "/Create", "/TN", GOREV_ADI, "/TR", komut]
    if oturum_acilinca:
        arguman += ["/SC", "ONLOGON"]
    else:
        arguman += ["/SC", "ONSTART", "/DELAY", "0000:30", "/RU", "SYSTEM"]
    arguman += ["/RL", "HIGHEST", "/F"]
    return arguman


def main(argv=None):
    ayrac = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    secim = ayrac.add_mutually_exclusive_group()
    secim.add_argument("--oturum", action="store_true", help="Açılışta değil, kullanıcı giriş yapınca başlat")
    secim.add_argument("--kaldir", action="store_true", help="Görevi sil")
    args = ayrac.parse_args(argv)

    if not windows_mu():
        raise SystemExit("Bu kurulum yalnızca Windows'ta çalışır.")

    if args.kaldir:
        subprocess.run(["schtasks", "/Delete", "/TN", GOREV_ADI, "/F"], check=True)
        print(f"Windows görevi silindi: {GOREV_ADI}")
        return

    proje = Path(__file__).resolve().parents[2]
    betik = proje / "scripts" / "windows" / "sunucu_baslat.py"
    if not betik.is_file():
        raise SystemExit("Sunucu başlatma betiği bulunamadı.")
    if not (proje / ".env").is_file():
        raise SystemExit(".env dosyası bulunamadı. Önce sunucu kurulum kılavuzundaki 4. adımı tamamlayın.")

    komut = gorev_komutu(sys.executable, betik)
    subprocess.run(olusturma_komutu(komut, args.oturum), check=True)
    kip = "kullanıcı giriş yapınca" if args.oturum else "bilgisayar açılınca"
    print(f"Windows görevi oluşturuldu: {GOREV_ADI} ({kip} çalışır).")
    print("Hemen denemek için:  schtasks /Run /TN " + GOREV_ADI)
    print("Günlük kaydı: logs\\sunucu.log")


if __name__ == "__main__":
    main()
