from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from server.modeller import RezervasyonOlusturModeli
from server.sunucu import cihaz_rezervasyonu_yap


@pytest.mark.parametrize("gun", [1, 7, 30])
def test_gecmis_tarihli_rezervasyon_reddedilir(gun):
    # Saat mesai içinde sabit (10:00-12:00): test günün hangi saatinde çalışırsa çalışsın 08:00-18:00 kuralına değil,
    # geçmiş tarih kuralına takılmalı.
    baslangic = (datetime.now() - timedelta(days=gun)).replace(hour=10, minute=0, second=0, microsecond=0)

    veri = RezervasyonOlusturModeli(
        cihaz_id=1,
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic + timedelta(hours=2),
    )

    with patch("server.sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(veri, kullanici_id=1)

    assert hata.value.status_code == 422
    assert "geçmişte" in hata.value.detail
    baglan.assert_not_called()


def test_saat_dilimli_gecmis_tarih_reddedilir():
    turkiye = timezone(timedelta(hours=3))
    baslangic = datetime.now(turkiye) - timedelta(hours=2)

    veri = RezervasyonOlusturModeli(
        cihaz_id=1,
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic + timedelta(hours=1),
    )

    with patch("server.sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(veri, kullanici_id=1)

    assert hata.value.status_code == 422
    baglan.assert_not_called()


def test_bitis_baslangictan_once_olamaz():
    baslangic = datetime.now() + timedelta(days=1)

    veri = RezervasyonOlusturModeli(
        cihaz_id=1,
        baslangic_zamani=baslangic,
        bitis_zamani=baslangic - timedelta(hours=1),
    )

    with patch("server.sunucu.psycopg2.connect") as baglan:
        with pytest.raises(HTTPException) as hata:
            cihaz_rezervasyonu_yap(veri, kullanici_id=1)

    assert hata.value.status_code == 422
    baglan.assert_not_called()
