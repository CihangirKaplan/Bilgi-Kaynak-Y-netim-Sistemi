"""Çok günlük etkinliklerin durum etiketi testleri."""

from datetime import datetime

import pytest

from client.oda_etkinlikleri_ekrani import OdaEtkinlikleriEkrani


@pytest.mark.parametrize("simdi,beklenen", [
    (datetime(2026, 11, 22, 15), "Planlandı"),
    (datetime(2026, 11, 23, 13), "Planlandı"),
    (datetime(2026, 11, 23, 14), "Devam Ediyor"),
    (datetime(2026, 11, 23, 15), "Devam Ediyor"),
    (datetime(2026, 11, 23, 16), "Planlandı"),
    (datetime(2026, 11, 24, 10), "Planlandı"),
    (datetime(2026, 11, 24, 15), "Devam Ediyor"),
    (datetime(2026, 11, 24, 19), "Planlandı"),
    (datetime(2026, 11, 27, 15), "Devam Ediyor"),
    (datetime(2026, 11, 27, 16), "Tamamlandı"),
    (datetime(2026, 11, 28, 10), "Tamamlandı"),
])
def test_cok_gunluk_etkinlik_durumu(simdi, beklenen):
    etkinlik = {
        "baslangic_zamani": "2026-11-23T14:00:00",
        "bitis_zamani": "2026-11-27T16:00:00",
        "iptal_edildi_mi": False,
    }

    sonuc = OdaEtkinlikleriEkrani.etkinlik_durumu(
        None, etkinlik, simdi=simdi
    )
    assert sonuc == beklenen


def test_iptal_edilmis_etkinlik():
    etkinlik = {
        "baslangic_zamani": "2026-11-23T14:00:00",
        "bitis_zamani": "2026-11-27T16:00:00",
        "iptal_edildi_mi": True,
    }

    assert OdaEtkinlikleriEkrani.etkinlik_durumu(
        None, etkinlik,
        simdi=datetime(2026, 11, 24, 15),
    ) == "İptal Edildi"
