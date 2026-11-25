"""Oturum açıkken hesabı ya da rolü pasife alınan kullanıcı: sunucu 403 verir, istemci oturumu sona erdirip giriş ekranına döner."""
import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest

import client.api_yoneticisi as api
from client.api_yoneticisi import PASIF_HESAP_MESAJLARI, oturum_kontrollu_istek, oturum_olaylari

BASLIKLAR = {"Authorization": "Bearer test-token"}


def _yanit(durum, detay):
    y = MagicMock(status_code=durum)
    y.json.return_value = {"detail": detay}
    return y


@pytest.fixture
def olaylar():
    kayit = []
    oturum_olaylari.token_reddedildi.connect(lambda token, neden: kayit.append((token, neden)))
    yield kayit
    oturum_olaylari.token_reddedildi.disconnect()


def _istek(yanit, basliklar=BASLIKLAR):
    with patch.object(api.requests, "request", return_value=yanit):
        return oturum_kontrollu_istek("GET", "http://x/api/yetkilerim", headers=basliklar)


@pytest.mark.parametrize("detay", sorted(PASIF_HESAP_MESAJLARI))
def test_pasife_alinan_hesabin_403_yaniti_oturumu_sonlandirir(detay, olaylar):
    yanit = _istek(_yanit(403, detay))
    assert yanit._tkys_oturum_reddedildi is True
    assert olaylar == [("test-token", "gecersiz")]                       # ana pencere "Oturumunuz geçersiz hâle gelmiştir" der ve giriş ekranına döner


def test_yetki_eksikligi_403_oturumu_kapatmaz(olaylar):
    yanit = _istek(_yanit(403, "Bu işlem için yetkiniz bulunmuyor."))
    assert getattr(yanit, "_tkys_oturum_reddedildi", False) is not True and olaylar == []


def test_pasif_hesap_mesaji_tokensiz_istekte_sayilmaz_giris_ekrani(olaylar):
    yanit = _istek(_yanit(403, "Kullanıcı hesabı aktif değil."), basliklar={})     # giriş isteği token taşımaz: oturum olayı doğmaz
    assert getattr(yanit, "_tkys_oturum_reddedildi", False) is not True and olaylar == []


def test_401_davranisi_degismedi(olaylar):
    _istek(_yanit(401, "Geçersiz token."))
    _istek(_yanit(401, "Token süresi dolmuş."))
    assert olaylar == [("test-token", "gecersiz"), ("test-token", "sure_doldu")]
    olaylar.clear()
    yanit = _istek(_yanit(401, "Kullanıcı adı veya parola hatalı."))           # oturum hatası olmayan 401 (ör. yanlış parola) oturumu kapatmaz
    assert getattr(yanit, "_tkys_oturum_reddedildi", False) is not True and olaylar == []


def test_mesajlar_sunucudaki_metinlerle_ayni():
    """İstemci ile sunucu mesajı ayrışırsa oturum sonlandırma sessizce çalışmaz olur."""
    os.environ.setdefault("JWT_SECRET", "t" * 40)
    from server.sunucu import ROL_PASIF_GIRIS_MESAJI
    kaynak = pathlib.Path(__file__).resolve().parents[2].joinpath("server", "sunucu.py").read_text(encoding="utf-8")
    assert ROL_PASIF_GIRIS_MESAJI in PASIF_HESAP_MESAJLARI
    assert "Kullanıcı hesabı aktif değil." in PASIF_HESAP_MESAJLARI and 'detail="Kullanıcı hesabı aktif değil."' in kaynak.replace("\n                ", "")
