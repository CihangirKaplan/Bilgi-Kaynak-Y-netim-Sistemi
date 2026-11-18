from datetime import datetime
import pytest

from client.oda_etkinlikleri_ekrani import OdaEtkinlikleriEkrani


@pytest.mark.parametrize("simdi,beklenen", [
    (datetime(2026, 11, 23, 13, 30), "Devam Ediyor"),
    (datetime(2026, 11, 24, 13, 30), "Planlandı"),
    (datetime(2026, 11, 25, 13, 30), "Devam Ediyor"),
    (datetime(2026, 11, 26, 15, 30), "Planlandı"),
    (datetime(2026, 11, 27, 15, 30), "Devam Ediyor"),
    (datetime(2026, 11, 27, 16, 0), "Tamamlandı"),
])
def test_bagimsiz_gun_durumlari(simdi, beklenen):
    etkinlik = {
        "baslangic_zamani": "2026-11-23T13:00:00",
        "bitis_zamani": "2026-11-27T16:00:00",
        "iptal_edildi_mi": False,
        "gunler": [
            {
                "baslangic_zamani": "2026-11-23T13:00:00",
                "bitis_zamani": "2026-11-23T14:00:00",
            },
            {
                "baslangic_zamani": "2026-11-25T13:00:00",
                "bitis_zamani": "2026-11-25T14:00:00",
            },
            {
                "baslangic_zamani": "2026-11-27T15:00:00",
                "bitis_zamani": "2026-11-27T16:00:00",
            },
        ],
    }

    assert OdaEtkinlikleriEkrani.etkinlik_durumu(
        None, etkinlik, simdi=simdi
    ) == beklenen
