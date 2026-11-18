"""Çok günlük oda etkinliği zaman aralığı testleri."""

from datetime import datetime, timedelta

import pytest

from server.oda_etkinlikleri_modelleri import (
    etkinlik_gunluk_araliklari,
)


def test_bes_gun_her_gun_14_16():
    ilk = datetime(2026, 11, 23, 14)
    son = datetime(2026, 11, 27, 16)

    araliklar = etkinlik_gunluk_araliklari(ilk, son)

    assert len(araliklar) == 5

    for i, (baslangic, bitis) in enumerate(araliklar):
        gun = datetime(2026, 11, 23) + timedelta(days=i)

        assert baslangic == gun.replace(hour=14)
        assert bitis == gun.replace(hour=16)

        # Her günlük kayıt aynı takvim gününde bitmeli.
        assert baslangic.date() == bitis.date()

    # Geceyi kapsayan kesintisiz bir kayıt olmamalı.
    for onceki, sonraki in zip(araliklar, araliklar[1:]):
        assert onceki[1] < sonraki[0]


def test_tek_gunluk_etkinlik():
    araliklar = etkinlik_gunluk_araliklari(
        datetime(2026, 11, 23, 9),
        datetime(2026, 11, 23, 11),
    )

    assert len(araliklar) == 1


def test_mesai_sinirlari_kabul_edilir():
    araliklar = etkinlik_gunluk_araliklari(
        datetime(2026, 11, 23, 8),
        datetime(2026, 11, 27, 18),
    )

    assert len(araliklar) == 5


@pytest.mark.parametrize("ilk,son", [
    (
        datetime(2026, 11, 23, 7, 30),
        datetime(2026, 11, 27, 16),
    ),
    (
        datetime(2026, 11, 23, 14),
        datetime(2026, 11, 27, 19),
    ),
    (
        datetime(2026, 11, 23, 16),
        datetime(2026, 11, 27, 14),
    ),
    (
        datetime(2026, 11, 27, 14),
        datetime(2026, 11, 23, 16),
    ),
])
def test_gecersiz_aralik_reddedilir(ilk, son):
    with pytest.raises(ValueError):
        etkinlik_gunluk_araliklari(ilk, son)


def test_366_gunden_uzun_etkinlik_reddedilir():
    with pytest.raises(ValueError):
        etkinlik_gunluk_araliklari(
            datetime(2026, 11, 23, 14),
            datetime(2027, 11, 24, 16),
        )
