from unittest.mock import patch

import pytest
from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QApplication

from cihaz_rezervasyon_ekranlari import (
    YeniRezervasyonFormu,
    varsayilan_rezervasyon_zamanlari,
)


@pytest.mark.parametrize(
    "simdi, beklenen_tarih, beklenen_bas, beklenen_bit",
    [
        ("2026-11-04 07:10:00", "2026-11-04", "08:00", "09:00"),
        ("2026-11-04 10:57:00", "2026-11-04", "11:00", "12:00"),
        ("2026-11-04 11:00:00", "2026-11-04", "11:30", "12:30"),
        ("2026-11-04 17:29:00", "2026-11-04", "17:30", "18:30"),
        ("2026-11-04 17:50:00", "2026-11-05", "08:00", "09:00"),
    ],
)
def test_varsayilan_saatler(
    simdi, beklenen_tarih, beklenen_bas, beklenen_bit
):
    an = QDateTime.fromString(simdi, "yyyy-MM-dd HH:mm:ss")
    tarih, bas, bit = varsayilan_rezervasyon_zamanlari(an)

    assert tarih.toString("yyyy-MM-dd") == beklenen_tarih
    assert bas == beklenen_bas
    assert bit == beklenen_bit


def test_rezervasyon_formu_gelecek_saatle_acilir():
    app = QApplication.instance() or QApplication([])

    with patch.object(YeniRezervasyonFormu, "verileri_yukle"):
        form = YeniRezervasyonFormu("http://localhost:8000", "test-token")

    bas = QDateTime.fromString(
        form.dt_baslangic_tarih.date().toString("yyyy-MM-dd")
        + " " + form.cmb_baslangic_saat.currentText(),
        "yyyy-MM-dd HH:mm",
    )
    bit = QDateTime.fromString(
        form.dt_bitis_tarih.date().toString("yyyy-MM-dd")
        + " " + form.cmb_bitis_saat.currentText(),
        "yyyy-MM-dd HH:mm",
    )

    assert bas > QDateTime.currentDateTime()
    assert bit > bas
    form.close()
