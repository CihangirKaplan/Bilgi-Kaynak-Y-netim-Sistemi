"""Oda Kullanımı ekranında çok günlük etkinlik gösterimi."""

from datetime import datetime, timedelta

import pytest

from client.oda_kullanimi_ekrani import (
    etkinlik_kayitlari,
    etkinlik_durumu_hesapla,
)


def gunluk_kayitlar():
    ilk = datetime(2026, 11, 23)
    return [
        {
            "etkinlik_id": 999,
            "oda_id": 1,
            "etkinlik_adi": "Çok Günlü Test Etkinliği",
            "katilimci_sayisi": 5,
            "iptal_edildi_mi": False,
            "baslangic_zamani": (
                ilk + timedelta(days=i, hours=14)
            ).isoformat(),
            "bitis_zamani": (
                ilk + timedelta(days=i, hours=16)
            ).isoformat(),
        }
        for i in range(5)
    ]


def test_bes_gun_bes_ayri_blok():
    bloklar = etkinlik_kayitlari(gunluk_kayitlar())

    assert len(bloklar) == 5

    for i, blok in enumerate(bloklar):
        gun = datetime(2026, 11, 23) + timedelta(days=i)

        assert blok["etkinlik"] is True
        assert blok["etkinlik_id"] == 999
        assert datetime.fromisoformat(
            blok["baslangic_zamani"]
        ) == gun.replace(hour=14)
        assert datetime.fromisoformat(
            blok["bitis_zamani"]
        ) == gun.replace(hour=16)

    print("PASS | Beş gün, beş ayrı 14.00-16.00 bloğu")


@pytest.mark.parametrize("saat,beklenen", [
    (datetime(2026, 11, 25, 13), "Planlandı"),
    (datetime(2026, 11, 25, 14), "Devam Ediyor"),
    (datetime(2026, 11, 25, 15), "Devam Ediyor"),
    (datetime(2026, 11, 25, 16), "Tamamlandı"),
    (datetime(2026, 11, 25, 19), "Tamamlandı"),
])
def test_gunluk_blok_durumu(saat, beklenen):
    kayit = gunluk_kayitlar()[2]

    assert etkinlik_durumu_hesapla(
        kayit, simdi=saat
    ) == beklenen


def test_iptal_durumu():
    kayit = gunluk_kayitlar()[2]
    kayit["iptal_edildi_mi"] = True

    assert etkinlik_durumu_hesapla(
        kayit,
        simdi=datetime(2026, 11, 25, 15),
    ) == "İptal Edildi"


def test_bloklar_geceye_tasmiyor():
    bloklar = etkinlik_kayitlari(gunluk_kayitlar())

    for blok in bloklar:
        bas = datetime.fromisoformat(blok["baslangic_zamani"])
        bit = datetime.fromisoformat(blok["bitis_zamani"])

        assert bas.date() == bit.date()
        assert bas.hour == 14
        assert bit.hour == 16

    print("PASS | Günlük bloklar geceye taşmıyor")
