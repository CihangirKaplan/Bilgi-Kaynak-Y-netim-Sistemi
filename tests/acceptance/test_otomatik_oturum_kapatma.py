"""TKYS otomatik oturum kapatma ve JWT süre testleri."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt

from client.main_window import AnaPencere
from server.guvenlik import (
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    access_token_olustur,
)


def sahte_pencere(bitis_zamani, kapaniyor=False):
    return SimpleNamespace(
        _token_bitis_zamani=bitis_zamani,
        _oturum_kapatiliyor=kapaniyor,
        _oturum_zamanlayici=MagicMock(),
        _oturum_pencerelerini_temizle=MagicMock(),
        oturum_kapat=MagicMock(),
    )


def test_sure_dolmadiysa_oturum_kapanmaz():
    pencere = sahte_pencere(2000)

    with patch("client.main_window.time.time", return_value=1000):
        AnaPencere._oturum_suresini_kontrol_et(pencere)

    assert pencere._oturum_kapatiliyor is False
    pencere._oturum_zamanlayici.stop.assert_not_called()
    pencere.oturum_kapat.assert_not_called()


def test_sure_dolunca_uyari_verilir_ve_oturum_kapanir():
    pencere = sahte_pencere(1000)

    with (
        patch("client.main_window.time.time", return_value=1001),
        patch("client.main_window.QMessageBox.information") as uyari,
    ):
        AnaPencere._oturum_suresini_kontrol_et(pencere)

    assert pencere._oturum_kapatiliyor is True
    pencere._oturum_zamanlayici.stop.assert_called_once()
    pencere._oturum_pencerelerini_temizle.assert_called_once()
    pencere.oturum_kapat.assert_called_once()

    uyari.assert_called_once()
    assert "Oturum süreniz sona ermiştir" in uyari.call_args.args[2]


def test_oturum_zaten_kapaniyorsa_tekrar_islem_yapilmaz():
    pencere = sahte_pencere(1000, kapaniyor=True)

    with (
        patch("client.main_window.time.time", return_value=1001),
        patch("client.main_window.QMessageBox.information") as uyari,
    ):
        AnaPencere._oturum_suresini_kontrol_et(pencere)

    uyari.assert_not_called()
    pencere._oturum_zamanlayici.stop.assert_not_called()
    pencere.oturum_kapat.assert_not_called()


def test_jwt_gecerlilik_suresi_45_dakika():
    assert JWT_EXPIRE_MINUTES == 45

    token = access_token_olustur(42)

    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
    )

    assert payload["exp"] - payload["iat"] == 45 * 60
