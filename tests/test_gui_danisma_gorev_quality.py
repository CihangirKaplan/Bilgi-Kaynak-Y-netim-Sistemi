"""
TKYS - QA-001 / GitHub Issue #186

Danisma masasi ogrenci ekrani:
Gorev baslatma ve bitirme GUI davranis testleri.

Gercek API veya PostgreSQL kullanilmaz.
"""

from unittest.mock import MagicMock, call, patch

import pytest

import danisma_masasi_ekrani as modul


EKRAN_SINIFI = next(
    sinif
    for sinif in vars(modul).values()
    if isinstance(sinif, type)
    and sinif.__module__ == modul.__name__
    and "gorev_baslat" in vars(sinif)
    and "gorev_bitir" in vars(sinif)
)


@pytest.fixture
def ortam():
    ekran = MagicMock()

    with patch(
        "danisma_masasi_ekrani.QMessageBox"
    ) as mesaj_kutusu:

        pencere = mesaj_kutusu.return_value

        vazgec = object()
        evet = object()

        pencere.addButton.side_effect = [
            vazgec,
            evet,
        ]

        yield (
            ekran,
            mesaj_kutusu,
            pencere,
            vazgec,
            evet,
        )


def test_gui_gorev_baslat_vazgec(ortam):
    ekran, mesaj, pencere, vazgec, evet = ortam

    pencere.clickedButton.return_value = vazgec

    EKRAN_SINIFI.gorev_baslat(ekran)

    ekran._istek.assert_not_called()
    ekran.yenile.assert_not_called()
    ekran._butonlari_ayarla.assert_not_called()


def test_gui_gorev_baslat_onayla(ortam):
    ekran, mesaj, pencere, vazgec, evet = ortam

    pencere.clickedButton.return_value = evet

    EKRAN_SINIFI.gorev_baslat(ekran)

    ekran._istek.assert_called_once_with(
        "POST",
        "/api/danisma/oturum/baslat",
    )

    ekran.yenile.assert_called_once_with()


def test_gui_aktif_gorev_yoksa_bitirme(ortam):
    ekran, mesaj, pencere, vazgec, evet = ortam

    ekran._istek.return_value = {
        "durum": "AKTIF_DEGIL"
    }

    EKRAN_SINIFI.gorev_bitir(ekran)

    ekran._istek.assert_called_once_with(
        "GET",
        "/api/danisma/oturum/aktif",
    )

    mesaj.warning.assert_called_once()
    ekran.yenile.assert_called_once_with()


def test_gui_gorev_bitir_vazgec(ortam):
    ekran, mesaj, pencere, vazgec, evet = ortam

    ekran._istek.return_value = {
        "durum": "AKTIF"
    }

    ekran._saniye_hesapla.return_value = 3660
    ekran._insan_suresi.return_value = (
        "1 saat 1 dakika"
    )

    pencere.clickedButton.return_value = vazgec

    EKRAN_SINIFI.gorev_bitir(ekran)

    pencere.setText.assert_called_once()

    onay_metni = pencere.setText.call_args.args[0]

    assert "1 saat 1 dakika" in onay_metni

    ekran._istek.assert_called_once_with(
        "GET",
        "/api/danisma/oturum/aktif",
    )

    ekran.yenile.assert_not_called()


def test_gui_gorev_bitir_onayla(ortam):
    ekran, mesaj, pencere, vazgec, evet = ortam

    ekran._istek.side_effect = [
        {"durum": "AKTIF"},
        {"calisilan_sure": "1 saat 1 dakika"},
    ]

    ekran._saniye_hesapla.return_value = 3660
    ekran._insan_suresi.return_value = (
        "1 saat 1 dakika"
    )

    pencere.clickedButton.return_value = evet

    EKRAN_SINIFI.gorev_bitir(ekran)

    assert ekran._istek.call_args_list == [
        call("GET", "/api/danisma/oturum/aktif"),
        call("PATCH", "/api/danisma/oturum/bitir"),
    ]

    onay_metni = pencere.setText.call_args.args[0]

    assert "1 saat 1 dakika" in onay_metni

    ekran.yenile.assert_called_once_with()

    mesaj.information.assert_called_once()

    bilgi_metni = mesaj.information.call_args.args[2]

    assert "1 saat 1 dakika" in bilgi_metni
