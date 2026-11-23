"""Yedek dosyası izinleri: yedek parola özetleri ve kişisel veri içerir, Linux/macOS'ta yalnızca sahibi okuyabilmelidir."""
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.backup import veritabani_yedekle

posix = pytest.mark.skipif(sys.platform == "win32", reason="Windows'ta izinler klasörden devralınır; chmod anlamsız")
ORTAM = {"DB_HOST": "h", "DB_PORT": "5432", "DB_USER": "u", "DB_PASSWORD": "p", "PG_DUMP_PATH": "/bin/true"}


@posix
def test_yedek_izinleri_yalnizca_sahibine_acilir(tmp_path):
    dosya = tmp_path / "yedek.dump"
    dosya.write_bytes(b"x")
    os.chmod(dosya, 0o644)
    veritabani_yedekle.yedek_izinlerini_kisitla(dosya, 0o600)
    assert stat.S_IMODE(dosya.stat().st_mode) == 0o600


def test_izin_degistirilemezse_yedek_engellenmez(tmp_path):
    veritabani_yedekle.yedek_izinlerini_kisitla(tmp_path / "yok.dump", 0o600)      # OSError sessizce yutulur


@posix
def test_yedekleme_dosyayi_kisitli_olusturur_ve_umask_i_geri_verir(tmp_path, monkeypatch):
    yedek_klasoru = tmp_path / "yedekler"
    monkeypatch.setattr(veritabani_yedekle, "YEDEK_KLASORU", yedek_klasoru)
    for ad, deger in ORTAM.items():
        monkeypatch.setenv(ad, deger)
    gorulen = {}

    def sahte_pg_dump(komut, **kwargs):
        mevcut = os.umask(0)
        os.umask(mevcut)
        gorulen["umask"] = mevcut
        Path(komut[komut.index("--file") + 1]).write_bytes(b"yedek")           # pg_dump'ın oluşturduğu dosya (umask'a tabi)

    onceki = os.umask(0o022)
    os.umask(onceki)
    with patch.object(veritabani_yedekle.subprocess, "run", side_effect=sahte_pg_dump):
        veritabani_yedekle.main(["--database", "ornek"])

    assert gorulen["umask"] == 0o077                                           # pg_dump çalışırken kısıtlı umask
    sonra = os.umask(0)
    os.umask(sonra)
    assert sonra == onceki                                                     # sonra eski umask geri verilir
    (yedek,) = list(yedek_klasoru.iterdir())
    assert stat.S_IMODE(yedek.stat().st_mode) == 0o600
    assert stat.S_IMODE(yedek_klasoru.stat().st_mode) == 0o700                 # klasörü biz oluşturduk


@posix
def test_var_olan_yedek_klasorunun_izinlerine_dokunulmaz(tmp_path, monkeypatch):
    klasor = tmp_path / "paylasimli"
    klasor.mkdir()
    os.chmod(klasor, 0o755)
    monkeypatch.setattr(veritabani_yedekle, "YEDEK_KLASORU", klasor)
    for ad, deger in ORTAM.items():
        monkeypatch.setenv(ad, deger)
    with patch.object(veritabani_yedekle.subprocess, "run",
                      side_effect=lambda komut, **k: Path(komut[komut.index("--file") + 1]).write_bytes(b"y")):
        veritabani_yedekle.main(["--database", "ornek"])
    assert stat.S_IMODE(klasor.stat().st_mode) == 0o755
