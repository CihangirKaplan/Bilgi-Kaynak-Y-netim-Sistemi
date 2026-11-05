from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from sunucu import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def sahte_hiz_siniri():
    """API birim testleri gercek veritabanina baglanmaz."""
    with patch("sunucu.hiz_siniri_kontrol") as kontrol:
        yield kontrol


CAPTCHA_ID = "a" * 32

GIRIS_VERISI = {
    "kullanici_adi": "test_kullanici",
    "parola": "test_parola",
    "captcha_id": CAPTCHA_ID,
    "guvenlik_kodu": "73942",
}


def test_captcha_endpointi_gorsel_dondurur():
    beklenen = {
        "captcha_id": CAPTCHA_ID,
        "gorsel_base64": "ornek_gorsel",
        "gecerlilik_saniye": 120,
    }

    with patch(
        "sunucu.captcha_olustur",
        return_value=beklenen,
    ) as olustur:
        cevap = client.get("/api/captcha")

    assert cevap.status_code == 200
    assert cevap.json() == beklenen
    olustur.assert_called_once()


def test_captcha_olmadan_giris_yapilamaz():
    with patch("sunucu.giris_yap") as normal_giris:
        cevap = client.post(
            "/api/login",
            json={
                "kullanici_adi": "test_kullanici",
                "parola": "test_parola",
            },
        )

    assert cevap.status_code == 422
    normal_giris.assert_not_called()


def test_yanlis_captcha_parola_kontrolune_gecmez():
    with (
        patch(
            "sunucu.captcha_dogrula",
            side_effect=HTTPException(
                status_code=400,
                detail="Güvenlik kodu hatalı.",
            ),
        ) as dogrula,
        patch("sunucu.giris_yap") as normal_giris,
    ):
        cevap = client.post(
            "/api/login",
            json=GIRIS_VERISI,
        )

    assert cevap.status_code == 400
    dogrula.assert_called_once()
    normal_giris.assert_not_called()


def test_dogru_captcha_normal_girise_izin_verir():
    with (
        patch("sunucu.captcha_dogrula") as dogrula,
        patch(
            "sunucu.giris_yap",
            return_value={
                "durum": "basarili",
                "mesaj": "Giriş başarılı.",
            },
        ) as normal_giris,
    ):
        cevap = client.post(
            "/api/login",
            json=GIRIS_VERISI,
        )

    assert cevap.status_code == 200
    assert cevap.json()["durum"] == "basarili"

    dogrula.assert_called_once()
    normal_giris.assert_called_once()

    gelen_model = normal_giris.call_args.args[0]

    assert gelen_model.kullanici_adi == "test_kullanici"
    assert gelen_model.parola == "test_parola"


def test_captcha_hiz_siniri_asildiginda_429(sahte_hiz_siniri):
    sahte_hiz_siniri.side_effect = HTTPException(
        status_code=429,
        detail="Çok fazla istek.",
        headers={"Retry-After": "60"},
    )

    with patch("sunucu.captcha_olustur") as olustur:
        cevap = client.get("/api/captcha")

    assert cevap.status_code == 429
    assert cevap.headers["Retry-After"] == "60"
    olustur.assert_not_called()

    assert sahte_hiz_siniri.call_args.args[-1] == "captcha"


def test_login_hiz_siniri_asildiginda_429(sahte_hiz_siniri):
    sahte_hiz_siniri.side_effect = HTTPException(
        status_code=429,
        detail="Çok fazla giriş denemesi.",
        headers={"Retry-After": "60"},
    )

    with (
        patch("sunucu.captcha_dogrula") as dogrula,
        patch("sunucu.giris_yap") as giris,
    ):
        cevap = client.post(
            "/api/login",
            json=GIRIS_VERISI,
        )

    assert cevap.status_code == 429
    assert cevap.headers["Retry-After"] == "60"

    dogrula.assert_not_called()
    giris.assert_not_called()

    assert sahte_hiz_siniri.call_args.args[-1] == "login"


def test_eksik_login_verisi_hiz_sinirina_dahildir(sahte_hiz_siniri):
    cevap = client.post(
        "/api/login",
        json={"kullanici_adi": "test"},
    )

    assert cevap.status_code == 422
    sahte_hiz_siniri.assert_called_once()
    assert sahte_hiz_siniri.call_args.args[-1] == "login"


def test_eksik_login_verisi_429_ile_engellenir(sahte_hiz_siniri):
    sahte_hiz_siniri.side_effect = HTTPException(
        status_code=429,
        detail="Çok fazla istek.",
        headers={
            "Retry-After": "60",
            "X-TKYS-RateLimit": "1",
        },
    )

    with patch("sunucu.giris_yap") as normal_giris:
        cevap = client.post(
            "/api/login",
            json={"kullanici_adi": "test"},
        )

    assert cevap.status_code == 429
    assert cevap.headers["Retry-After"] == "60"
    normal_giris.assert_not_called()


def test_gecerli_login_tek_kez_sayilir(sahte_hiz_siniri):
    with (
        patch("sunucu.captcha_dogrula"),
        patch(
            "sunucu.giris_yap",
            return_value={"durum": "basarili"},
        ),
    ):
        cevap = client.post(
            "/api/login",
            json=GIRIS_VERISI,
        )

    assert cevap.status_code == 200
    sahte_hiz_siniri.assert_called_once()
