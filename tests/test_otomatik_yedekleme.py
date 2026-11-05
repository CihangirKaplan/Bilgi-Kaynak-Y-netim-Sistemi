"""Otomatik yedekleme ve rotasyon testleri."""

import subprocess
from unittest.mock import call, patch

import pytest

from scripts import otomatik_yedekleme


def test_yedekleme_basariliysa_rotasyon_calisir():
    with patch.object(otomatik_yedekleme.subprocess, "run") as calistir:
        otomatik_yedekleme.main(["--database", "crkys"])

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
            otomatik_yedekleme.main(["--database", "crkys"])

    assert calistir.call_count == 1


def test_yedekleme_ve_rotasyon_ayni_veritabanina_uygulanir():
    with patch.object(otomatik_yedekleme.subprocess, "run") as calistir:
        otomatik_yedekleme.main(["--database", "crkys", "--days", "14"])

    yedek, rotasyon = (c.args[0] for c in calistir.call_args_list)
    assert yedek[yedek.index("--database") + 1] == "crkys"
    assert rotasyon[rotasyon.index("--database") + 1] == "crkys"
    assert rotasyon[rotasyon.index("--days") + 1] == "14"


def test_parametresiz_calisinca_env_deki_veritabani_yedeklenir(monkeypatch):
    monkeypatch.setenv("DB_NAME", "crkys")
    with patch.object(otomatik_yedekleme.subprocess, "run") as calistir:
        otomatik_yedekleme.main([])

    for c in calistir.call_args_list:
        komut = c.args[0]
        assert komut[komut.index("--database") + 1] == "crkys"


def test_veritabani_adi_yoksa_hicbir_komut_calismaz(monkeypatch):
    monkeypatch.delenv("DB_NAME", raising=False)
    with patch.object(otomatik_yedekleme.subprocess, "run") as calistir:
        with pytest.raises(SystemExit):
            otomatik_yedekleme.main([])
    calistir.assert_not_called()
