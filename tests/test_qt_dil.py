"""Merkezi Qt Türkçe çeviri sistemi testleri."""

import os
import subprocess
import sys
from pathlib import Path


def test_yeni_mesaj_kutulari_otomatik_turkce():
    kod = """
from PySide6.QtWidgets import QApplication, QMessageBox
from qt_dil import turkce_ceviriyi_yukle

app = QApplication([])

assert turkce_ceviriyi_yukle(app)
cevirici = app._tkys_turkce_cevirici

assert turkce_ceviriyi_yukle(app)
assert app._tkys_turkce_cevirici is cevirici

beklenen = {
    QMessageBox.StandardButton.Yes: "Evet",
    QMessageBox.StandardButton.No: "Hayır",
    QMessageBox.StandardButton.Ok: "Tamam",
    QMessageBox.StandardButton.Cancel: "İptal",
    QMessageBox.StandardButton.Save: "Kaydet",
}

for tur, metin in beklenen.items():
    kutu = QMessageBox()
    kutu.setStandardButtons(tur)
    gercek = kutu.button(tur).text().replace("&", "")
    assert gercek == metin, (tur.name, gercek)

print("Merkezi Türkçe çeviri başarılı")
"""

    proje = Path(__file__).resolve().parents[1]
    ortam = os.environ.copy()
    ortam["QT_QPA_PLATFORM"] = "offscreen"

    sonuc = subprocess.run(
        [sys.executable, "-c", kod],
        cwd=proje,
        env=ortam,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
    assert "Merkezi Türkçe çeviri başarılı" in sonuc.stdout
