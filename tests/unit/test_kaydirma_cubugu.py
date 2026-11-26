"""Tüm uygulamada tek, belirgin kaydırma çubuğu (dikey + yatay); sayfalara özel ince çubuk kuralları kalmadı."""
import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from client.sayfa_tema import KAYDIRMA_CUBUGU_STILI, TABLO_STILI


def test_cubuk_stili_dikey_ve_yatay_ve_yeterince_kalin():
    for yon in ("vertical", "horizontal"):
        assert f"QScrollBar:{yon}" in KAYDIRMA_CUBUGU_STILI and f"::handle:{yon}:hover" in KAYDIRMA_CUBUGU_STILI
    assert int(re.search(r"QScrollBar:vertical \{[^}]*width: (\d+)px", KAYDIRMA_CUBUGU_STILI).group(1)) >= 12


def test_baska_dosyada_cubuk_kurali_tanimlanmaz():
    assert "QScrollBar" not in TABLO_STILI
    for yol in Path("client").glob("*.py"):
        if yol.name == "sayfa_tema.py":
            continue
        assert "QScrollBar" not in yol.read_text(encoding="utf-8"), yol.name


def test_ana_pencere_ve_giris_ortak_stili_kullanir():
    import client.main_window as mw
    assert KAYDIRMA_CUBUGU_STILI in mw.STIL
    assert "KAYDIRMA_CUBUGU_STILI" in Path("client/login_ekrani.py").read_text(encoding="utf-8")
