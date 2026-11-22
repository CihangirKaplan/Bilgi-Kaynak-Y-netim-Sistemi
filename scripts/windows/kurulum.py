"""Windows Task Scheduler icin TKYS yedekleme kurulumu."""

import os
import subprocess
import sys
from pathlib import Path


def windows_mu():
    return os.name == "nt"


def gorev_ayari_komutu(gorev_adi, surekli_calisir):
    """schtasks'ın veremediği görev ayarlarını PowerShell ile düzenleyen komut.

    schtasks ile oluşturulan görevde varsayılan olarak "3 günden uzun sürerse durdur" ve "pilde çalışma" ayarları açıktır.
    Kaçırılan görev bilgisayar açılınca çalıştırılır; sürekli çalışan görevde süre sınırı kaldırılır ve görev
    hata verip kapanırsa 1 dakika arayla 3 kez yeniden başlatılır."""
    ayarlar = [
        "$s.StartWhenAvailable = $true",
        "$s.DisallowStartIfOnBatteries = $false",
        "$s.StopIfGoingOnBatteries = $false",
    ]
    if surekli_calisir:
        ayarlar += ["$s.ExecutionTimeLimit = 'PT0S'", "$s.RestartCount = 3", "$s.RestartInterval = 'PT1M'"]
    betik = (
        f"$g = Get-ScheduledTask -TaskName '{gorev_adi}'; $s = $g.Settings; "
        + "; ".join(ayarlar)
        + "; Set-ScheduledTask -InputObject $g | Out-Null"
    )
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", betik]


def gorev_ayarlarini_uygula(gorev_adi, surekli_calisir):
    """Ayarları uygular; başarısız olursa görev yine çalışır, ama elle yapılacak adım ekrana yazılır."""
    sonuc = subprocess.run(gorev_ayari_komutu(gorev_adi, surekli_calisir), check=False)
    if sonuc.returncode != 0:
        print(
            "UYARI: Görev ayarları uygulanamadı. Görev Zamanlayıcı'da görevi açıp Ayarlar sekmesinde "
            "'Görev şundan uzun sürerse durdur' kutusunu kaldırın ve 'Zamanlanmış başlatma kaçırılırsa hemen çalıştır' kutusunu işaretleyin."
        )
        return False
    return True


def main():
    if not windows_mu():
        raise SystemExit("Bu kurulum yalnizca Windows'ta calisir.")

    proje = Path(__file__).resolve().parents[2]
    script = proje / "scripts" / "windows" / "yedekleme_calistir.py"

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
            "/ST", "05:00",
            "/RU", "SYSTEM",
            "/RL", "HIGHEST",
            "/F",
        ],
        check=True,
    )

    # Bilgisayar 05.00'te kapalıysa yedek, açıldığında alınır.
    gorev_ayarlarini_uygula(gorev_adi, surekli_calisir=False)

    print(f"Windows gorevi olusturuldu: {gorev_adi}")


if __name__ == "__main__":
    main()
