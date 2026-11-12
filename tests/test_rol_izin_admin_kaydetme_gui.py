import turkce_mesaj_kutusu as tmk
import inspect
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import rol_izin_diyaloglari as modul


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def duzenleme_sinifi():
    for _, sinif in inspect.getmembers(modul, inspect.isclass):
        if (
            sinif.__module__ == modul.__name__
            and "matris_verisi"
            in inspect.signature(sinif.__init__).parameters
        ):
            return sinif

    raise AssertionError("İzin düzenleme sınıfı bulunamadı.")


def diyalog_olustur(roller):
    sinif = duzenleme_sinifi()

    return sinif(
        "http://localhost:8000",
        "test-token",
        17,
        roller,
        {
            "izinler": [
                {
                    "izin_id": 17,
                    "izin_adi": "RANDEVU_DUZENLE",
                    "gorunen_ad": "Randevu Düzenle",
                }
            ],
            "rol_izin_map": {},
        },
    )


def test_diger_rol_duzenlenirken_admin_izni_korunur(qt_app):
    roller = [
        {"rol_id": 7, "rol_adi": "ADMIN"},
        {"rol_id": 2, "rol_adi": "PSIKOLOG"},
        {"rol_id": 3, "rol_adi": "MEMUR"},
    ]

    pencere = diyalog_olustur(roller)

    assert 7 not in pencere.rol_checkboxlar

    pencere.rol_checkboxlar[2].setChecked(True)
    pencere.rol_checkboxlar[3].setChecked(False)

    with patch.object(modul.requests, "put") as istek:
        with patch.object(tmk, "bilgi"):
            istek.return_value.status_code = 200
            pencere.kaydet()

    payload = istek.call_args.kwargs["json"]

    assert set(payload["verilen_rol_idleri"]) == {7, 2}
    assert 3 not in payload["verilen_rol_idleri"]


def test_admin_rolu_yuklenmezse_kaydetme_engellenir(qt_app):
    roller = [
        {"rol_id": 2, "rol_adi": "PSIKOLOG"},
    ]

    pencere = diyalog_olustur(roller)

    with patch.object(modul.requests, "put") as istek:
        with patch.object(tmk, "uyari") as uyari:
            pencere.kaydet()

    istek.assert_not_called()
    uyari.assert_called_once()
