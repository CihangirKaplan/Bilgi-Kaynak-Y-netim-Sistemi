"""Randevu saat kuralı: saat başı 09:00-15:00 arasında başlar, tam 1 saat sürer (istemcideki saat listesiyle aynı)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from server.modeller import RandevuOlusturModeli, RandevuGuncelleModeli
from server.sunucu import randevu_guncelle


def randevu_verisi(bas, bit):
    return {
        "danisan_kod_id": "DAN-2026-0001",
        "psikolog_id": 1,
        "oda_id": 1,
        "baslangic_zamani": f"2026-11-19T{bas}:00",
        "bitis_zamani": f"2026-11-19T{bit}:00",
    }


@pytest.mark.parametrize("bas,bit", [
    ("09:00", "10:00"),
    ("12:00", "13:00"),
    ("15:00", "16:00"),
])
def test_mesai_icinde_randevu_kabul_edilir(bas, bit):
    model = RandevuOlusturModeli.model_validate(
        randevu_verisi(bas, bit)
    )
    assert model.baslangic_zamani < model.bitis_zamani


@pytest.mark.parametrize("bas,bit", [
    ("08:00", "09:00"),       # ilk saatten önce
    ("16:00", "17:00"),       # son başlangıç saatinden sonra
    ("17:00", "18:00"),
    ("18:00", "19:00"),
    ("07:30", "09:00"),
    ("10:00", "10:00"),       # süre sıfır
    ("09:30", "10:30"),       # saat başı değil
    ("10:00", "11:30"),       # 1 saatten uzun
    ("10:00", "12:00"),
    ("10:00", "10:30"),       # 1 saatten kısa
])
def test_mesai_disinda_randevu_reddedilir(bas, bit):
    with pytest.raises(ValidationError):
        RandevuOlusturModeli.model_validate(
            randevu_verisi(bas, bit)
        )


def test_farkli_gunlere_yayilan_randevu_reddedilir():
    veri = randevu_verisi("17:00", "18:00")
    veri["bitis_zamani"] = "2026-11-20T09:00:00"

    with pytest.raises(ValidationError):
        RandevuOlusturModeli.model_validate(veri)


def test_yalnizca_bitis_1900_yapilirsa_guncelleme_reddedilir():
    """Mevcut 10:00-11:00 randevusu 10:00-19:00 yapılamaz."""
    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchone.side_effect = [
        (1,),  # İlk sorguda mevcut oda ID
        (
            "DAN-2026-0001",
            1, 1,
            datetime(2026, 11, 19, 10),
            datetime(2026, 11, 19, 11),
            "PLANLANDI",
            "YUZ_YUZE",
            None,
        ),
        ("ADMIN",),
    ]

    guncelleme = RandevuGuncelleModeli(
        bitis_zamani=datetime(2026, 11, 19, 19)
    )

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        with pytest.raises(HTTPException) as hata:
            randevu_guncelle(
                randevu_id=1,
                guncelleme=guncelleme,
                kullanici_id=1,
            )

    assert hata.value.status_code == 422
    assert "1 saat" in str(hata.value.detail)

    sorgular = [
        cagri.args[0].strip().upper()
        for cagri in cursor.execute.call_args_list
    ]

    assert not any(
        sorgu.startswith("UPDATE RANDEVULAR")
        for sorgu in sorgular
    )
    conn.commit.assert_not_called()


def test_sunucu_kurali_istemcideki_saat_listesiyle_ayni():
    """Ekranın sunduğu saatlerle sunucunun kabul ettiği saatler birebir aynı olmalı (biri değişirse bu test düşer)."""
    from client.randevu_ekranlari import SAAT_LISTESI
    from server.modeller import RANDEVU_ILK_SAAT, RANDEVU_SON_BASLANGIC_SAATI

    beklenen = [f"{saat:02d}:00" for saat in range(RANDEVU_ILK_SAAT, RANDEVU_SON_BASLANGIC_SAATI + 1)]
    assert SAAT_LISTESI == beklenen

    for saat in SAAT_LISTESI:                                  # ekrandaki her saat sunucuda geçerli
        bas = int(saat[:2])
        RandevuOlusturModeli.model_validate(randevu_verisi(saat, f"{bas + 1:02d}:00"))


def test_eski_mesai_penceresindeki_ama_ekranda_olmayan_saatler_reddedilir():
    """Önceki kural 08:00-18:00 arasındaki her dakikayı kabul ediyordu; artık yalnızca ekrandaki saatler geçerli."""
    for bas, bit in (("08:00", "09:00"), ("08:30", "10:00"), ("17:00", "18:00")):
        with pytest.raises(ValidationError):
            RandevuOlusturModeli.model_validate(randevu_verisi(bas, bit))
