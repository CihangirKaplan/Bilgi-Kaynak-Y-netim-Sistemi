from datetime import datetime

from client.oda_kullanimi_ekrani import (
    blok_haritasi,
    takvim_kayit_onceligi,
    etkinlik_durumu_hesapla,
)


def test_aktif_randevu_iptal_etkinlikten_once_gorunur():
    bas = "2026-11-18T10:00:00"
    bit = "2026-11-18T11:00:00"

    iptal = {
        "etkinlik": True,
        "iptal_edildi_mi": True,
        "oda_id": 1,
        "baslangic_zamani": bas,
        "bitis_zamani": bit,
    }

    randevu = {
        "oda_id": 1,
        "baslangic_zamani": bas,
        "bitis_zamani": bit,
        "durum": "PLANLANDI",
    }

    harita = blok_haritasi([iptal, randevu])
    anahtar = (1, datetime(2026, 11, 18).date(), 10)

    kayitlar = sorted(
        harita[anahtar],
        key=takvim_kayit_onceligi,
    )

    assert len(kayitlar) == 2
    assert kayitlar[0] is randevu
    assert kayitlar[1] is iptal


def test_iptal_etkinlik_tek_basina_gorunebilir():
    iptal = {
        "etkinlik": True,
        "iptal_edildi_mi": True,
    }
    assert takvim_kayit_onceligi(iptal) == 1


def test_oda_etkinligi_dort_durum():
    bas = datetime(2026, 11, 18, 10)
    bit = datetime(2026, 11, 18, 12)
    e = {
        "baslangic_zamani": bas.isoformat(),
        "bitis_zamani": bit.isoformat(),
        "iptal_edildi_mi": False,
    }

    assert etkinlik_durumu_hesapla(
        e, datetime(2026, 11, 18, 9)
    ) == "Planlandı"

    assert etkinlik_durumu_hesapla(
        e, datetime(2026, 11, 18, 11)
    ) == "Devam Ediyor"

    assert etkinlik_durumu_hesapla(
        e, datetime(2026, 11, 18, 13)
    ) == "Tamamlandı"

    e["iptal_edildi_mi"] = True
    assert etkinlik_durumu_hesapla(
        e, datetime(2026, 11, 18, 11)
    ) == "İptal Edildi"
