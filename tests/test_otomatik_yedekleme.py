"""Otomatik yedekleme ve rotasyon testleri."""

import subprocess
from unittest.mock import call, patch

import pytest

from scripts import otomatik_yedekleme


def test_yedekleme_basariliysa_rotasyon_calisir():
    with patch.object(otomatik_yedekleme.subprocess, "run") as calistir:
        otomatik_yedekleme.main()

    assert calistir.call_count == 2

    ilk_komut = calistir.call_args_list[0].args[0]
    ikinci_komut = calistir.call_args_list[1].args[0]

    assert "veritabani_yedekle.py" in ilk_komut[1]
    assert "yedek_rotasyonu.py" in ikinci_komut[1]
    assert "--apply" in ikinci_komut
    assert all(
        c.kwargs["check"] is True
        for c in calistir.call_args_list
    )


def test_yedekleme_basarisizsa_rotasyon_calismaz():
    with patch.object(
        otomatik_yedekleme.subprocess,
        "run",
        side_effect=subprocess.CalledProcessError(1, ["pg_dump"]),
    ) as calistir:
        with pytest.raises(subprocess.CalledProcessError):
            otomatik_yedekleme.main()

    assert calistir.call_count == 1
