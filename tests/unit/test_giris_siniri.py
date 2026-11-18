from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from server import giris_siniri
from server.modeller import GirisModeli
from server.sunucu import giris_yap


def istek(adres="10.0.0.5"):
    return SimpleNamespace(client=SimpleNamespace(host=adres), headers={"x-forwarded-for": "1.2.3.4"})


def test_anahtar_ip_ozeti_olur_ham_adres_saklanmaz():
    anahtar = giris_siniri.istemci_anahtari(istek("10.0.0.5"))
    assert len(anahtar) == 64 and "10.0.0.5" not in anahtar
    assert anahtar == giris_siniri.istemci_anahtari(istek("10.0.0.5"))
    assert anahtar != giris_siniri.istemci_anahtari(istek("10.0.0.6"))


def test_sahte_forwarded_header_anahtari_degistirmez():
    a = SimpleNamespace(client=SimpleNamespace(host="10.0.0.5"), headers={"x-forwarded-for": "1.1.1.1"})
    b = SimpleNamespace(client=SimpleNamespace(host="10.0.0.5"), headers={"x-forwarded-for": "2.2.2.2"})
    assert giris_siniri.istemci_anahtari(a) == giris_siniri.istemci_anahtari(b)


@pytest.mark.parametrize("request_nesnesi", [None, SimpleNamespace(client=None), SimpleNamespace(client=SimpleNamespace(host=""))])
def test_adres_bilinmiyorsa_sinir_uygulanmaz(request_nesnesi):
    assert giris_siniri.istemci_anahtari(request_nesnesi) is None
    with patch("server.giris_siniri.psycopg2.connect") as baglan:
        assert giris_siniri.engel_suresi({}, None) == 0
        giris_siniri.basarisiz_girisi_kaydet({}, None)
        baglan.assert_not_called()


def test_veritabani_hatasinda_giris_engellenmez():
    with patch("server.giris_siniri.psycopg2.connect", side_effect=RuntimeError("db yok")):
        assert giris_siniri.engel_suresi({}, "a" * 64) == 0
        giris_siniri.basarisiz_girisi_kaydet({}, "a" * 64)      # hata fırlatmaz


def test_engel_suresi_sorgudan_gelir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = (120,)
    with patch("server.giris_siniri.psycopg2.connect", return_value=conn):
        assert giris_siniri.engel_suresi({}, "a" * 64) == 120
    conn.cursor.return_value.fetchone.return_value = None
    with patch("server.giris_siniri.psycopg2.connect", return_value=conn):
        assert giris_siniri.engel_suresi({}, "a" * 64) == 0


def test_sinir_asilinca_giris_429_ve_retry_after_doner_veritabani_sorgulanmaz():
    with patch("server.giris_siniri.engel_suresi", return_value=90), \
         patch("server.sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            giris_yap(GirisModeli(kullanici_adi="x", parola="y"), istek())
    assert hata.value.status_code == 429 and hata.value.headers["Retry-After"] == "90"
    baglan.assert_not_called()


def test_var_olmayan_kullanici_basarisiz_deneme_olarak_sayilir():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = None       # kullanıcı yok
    with patch("server.giris_siniri.engel_suresi", return_value=0), \
         patch("server.giris_siniri.basarisiz_girisi_kaydet") as kaydet, \
         patch("server.sunucu.psycopg2.connect", return_value=conn), \
         patch("server.sunucu.denetim_kaydi_olustur"):
        with pytest.raises(HTTPException) as hata:
            giris_yap(GirisModeli(kullanici_adi="yok", parola="y"), istek())
    assert hata.value.status_code == 401
    kaydet.assert_called_once()
