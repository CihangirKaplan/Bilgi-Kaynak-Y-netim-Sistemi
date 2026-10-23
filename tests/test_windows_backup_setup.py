"""Windows otomatik yedekleme kurulum testleri."""

from unittest.mock import patch

from scripts.windows import kurulum


def test_windows_gorev_olusturma():
    with (
        patch.object(kurulum, "windows_mu", return_value=True),
        patch.object(kurulum.subprocess, "run") as calistir,
    ):
        kurulum.main()

    komut = calistir.call_args.args[0]

    assert komut[0] == "schtasks"
    assert "/Create" in komut
    assert "/SC" in komut
    assert "DAILY" in komut
    assert "/ST" in komut
    assert "09:00" in komut
    assert calistir.call_args.kwargs["check"] is True
