from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from modeller import GirisModeli
from sunucu import app, giris_yap
from guvenlik import (
    JWT_ALGORITHM,
    JWT_SECRET,
    access_token_olustur,
    token_dogrula,
)


def sahte_kullanici(
    hata_sayisi=0,
    kilit_bitis=None,
):
    return (
        5, "test_psikolog", "sahte_hash", 2,
        True, hata_sayisi, kilit_bitis,
        False, "PSIKOLOG"
    )


def test_besinci_hatali_giris_hesabi_kilitler():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = sahte_kullanici(
        hata_sayisi=4
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.parola_dogrula", return_value=False),
        patch("sunucu.denetim_kaydi_olustur") as audit,
    ):
        with pytest.raises(HTTPException) as hata:
            giris_yap(
                GirisModeli(
                    kullanici_adi="test_psikolog",
                    parola="hatali_parola"
                )
            )

    assert hata.value.status_code == 429

    guncelleme = [
        c for c in cursor.execute.call_args_list
        if "UPDATE kullanicilar SET basarisiz_giris_sayisi" in c.args[0]
    ]

    assert len(guncelleme) == 1
    assert guncelleme[0].args[1][0] == 5

    kilit_zamani = guncelleme[0].args[1][1]
    kalan = kilit_zamani - datetime.now()
    assert timedelta(minutes=14) < kalan <= timedelta(minutes=15)

    conn.commit.assert_called_once()
    assert audit.call_args.kwargs["olay_turu"] == "LOGIN_FAILED"


def test_kilitli_hesap_dogru_parolayla_bile_giremez():
    conn = MagicMock()
    conn.cursor.return_value.fetchone.return_value = sahte_kullanici(
        hata_sayisi=5,
        kilit_bitis=datetime.now() + timedelta(minutes=10),
    )

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.parola_dogrula") as parola_kontrol,
    ):
        with pytest.raises(HTTPException) as hata:
            giris_yap(
                GirisModeli(
                    kullanici_adi="test_psikolog",
                    parola="dogru_parola"
                )
            )

    assert hata.value.status_code == 429
    parola_kontrol.assert_not_called()
    conn.commit.assert_not_called()


def test_gecerli_token_kullanici_id_doner():
    token = access_token_olustur(5)
    assert token_dogrula(token) == 5


def test_suresi_dolmus_token_reddedilir():
    token = jwt.encode(
        {
            "sub": "5",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        token_dogrula(token)


def test_degistirilmis_token_reddedilir():
    token = jwt.encode(
        {
            "sub": "5",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "FARKLI_TEST_IMZA_ANAHTARI",
        algorithm=JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        token_dogrula(token)


def test_tokensiz_korumali_endpoint_reddedilir():
    with TestClient(app) as client:
        yanit = client.get("/api/korumali-test")

    assert yanit.status_code in (401, 403)


def test_kilit_suresi_dolunca_dogru_parolayla_giris():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        sahte_kullanici(
            hata_sayisi=5,
            kilit_bitis=datetime.now() - timedelta(minutes=1),
        ),
        (12,),  # Personel ID
    ]

    with (
        patch("sunucu.psycopg2.connect", return_value=conn),
        patch("sunucu.parola_dogrula", return_value=True),
        patch("sunucu.access_token_olustur", return_value="test-token"),
        patch("sunucu.denetim_kaydi_olustur") as audit,
    ):
        sonuc = giris_yap(
            GirisModeli(
                kullanici_adi="test_psikolog",
                parola="dogru_parola",
            )
        )

    assert sonuc["durum"] == "basarili"
    assert sonuc["access_token"] == "test-token"
    assert sonuc["personel_id"] == 12

    sorgular = cursor.execute.call_args_list
    assert any(
        "basarisiz_giris_sayisi = 0" in c.args[0]
        and "kilit_bitis_zamani = NULL" in c.args[0]
        for c in sorgular
    )

    assert audit.call_args.kwargs["olay_turu"] == "LOGIN"
    conn.commit.assert_called_once()
