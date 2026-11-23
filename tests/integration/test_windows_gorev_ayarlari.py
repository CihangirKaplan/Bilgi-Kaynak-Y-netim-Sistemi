"""Windows görevlerinin schtasks ile verilemeyen ayarları: sunucu görevinde 3 günlük süre sınırı kaldırılır ve görev kapanırsa
yeniden başlatılır; yedek görevi kaçırılırsa bilgisayar açılınca çalışır. Gerçek Windows görevi kullanılmaz, subprocess taklit edilir."""
from unittest.mock import MagicMock, patch

import pytest

from scripts.windows import kurulum, sunucu_kurulum


@pytest.mark.parametrize("modul", [kurulum, sunucu_kurulum])
def test_surekli_calisan_gorevde_sure_siniri_kaldirilir_ve_yeniden_baslatma_acilir(modul):
    betik = modul.gorev_ayari_komutu("TKYS_Sunucu", surekli_calisir=True)[-1]
    assert "Get-ScheduledTask -TaskName 'TKYS_Sunucu'" in betik and "Set-ScheduledTask -InputObject $g" in betik
    for ayar in ("ExecutionTimeLimit = 'PT0S'", "RestartCount = 3", "RestartInterval = 'PT1M'",
                 "StartWhenAvailable = $true", "DisallowStartIfOnBatteries = $false", "StopIfGoingOnBatteries = $false"):
        assert ayar in betik


def test_yedek_gorevinde_sure_siniri_ve_yeniden_baslatma_degistirilmez_kacirilan_gorev_calisir():
    betik = kurulum.gorev_ayari_komutu("TKYS_Otomatik_Yedekleme", surekli_calisir=False)[-1]
    assert "StartWhenAvailable = $true" in betik
    assert "ExecutionTimeLimit" not in betik and "RestartCount" not in betik


def test_sunucu_kurulumu_once_gorevi_olusturur_sonra_ayarlari_uygular(tmp_path):
    with (
        patch.object(sunucu_kurulum, "windows_mu", return_value=True),
        patch.object(sunucu_kurulum.Path, "is_file", return_value=True),
        patch.object(sunucu_kurulum.subprocess, "run", return_value=MagicMock(returncode=0)) as calistir,
    ):
        sunucu_kurulum.main([])
    olustur, ayar = (c.args[0] for c in calistir.call_args_list)
    assert olustur[:2] == ["schtasks", "/Create"] and "ONSTART" in olustur and "SYSTEM" in olustur
    assert ayar[0] == "powershell" and "ExecutionTimeLimit = 'PT0S'" in ayar[-1]


def test_yedek_kurulumu_once_gorevi_olusturur_sonra_kacirilan_gorev_ayarini_uygular():
    with (
        patch.object(kurulum, "windows_mu", return_value=True),
        patch.object(kurulum.subprocess, "run", return_value=MagicMock(returncode=0)) as calistir,
    ):
        kurulum.main()
    olustur, ayar = (c.args[0] for c in calistir.call_args_list)
    assert "05:00" in olustur and ayar[0] == "powershell" and "TKYS_Otomatik_Yedekleme" in ayar[-1]


def test_ayarlar_uygulanamazsa_kurulum_durmaz_elle_yapilacak_adim_yazilir(capsys):
    with patch.object(sunucu_kurulum.subprocess, "run", return_value=MagicMock(returncode=1)):
        assert sunucu_kurulum.gorev_ayarlarini_uygula("TKYS_Sunucu", surekli_calisir=True) is False
    assert "uzun sürerse durdur" in capsys.readouterr().out
