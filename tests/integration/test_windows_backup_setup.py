"""Windows otomatik yedekleme kurulum testleri."""

from unittest.mock import patch

from scripts.windows import kurulum


def test_windows_gorev_olusturma():
    with (
        patch.object(kurulum, "windows_mu", return_value=True),
        patch.object(kurulum.subprocess, "run") as calistir,
    ):
        kurulum.main()

    komut = calistir.call_args_list[0].args[0]                   # 1. çağrı görevi oluşturur, 2. çağrı ayarlarını düzenler

    assert komut[0] == "schtasks"
    assert "/Create" in komut
    assert "/SC" in komut
    assert "DAILY" in komut
    assert "/ST" in komut
    assert "05:00" in komut
    assert "/RU" in komut
    assert "SYSTEM" in komut
    assert calistir.call_args_list[0].kwargs["check"] is True
