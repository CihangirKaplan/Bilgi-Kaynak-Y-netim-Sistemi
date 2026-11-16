from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from server.sunucu import (
    rezervasyon_gorunen_durumu,
    rezervasyonlari_listele,
)
from client.cihaz_rezervasyon_ekranlari import RezervasyonYonetimEkrani


def test_rezervasyon_durumlari_dogru_hesaplanir():
    simdi = datetime.now()

    assert rezervasyon_gorunen_durumu(
        False, simdi + timedelta(hours=2), simdi
    ) == "Aktif"

    assert rezervasyon_gorunen_durumu(
        False, simdi - timedelta(hours=2), simdi
    ) == "Tamamlandı"

    assert rezervasyon_gorunen_durumu(
        True, simdi - timedelta(hours=2), simdi
    ) == "İptal Edildi"

    assert rezervasyon_gorunen_durumu(
        True, simdi + timedelta(hours=2), simdi
    ) == "İptal Edildi"


def test_rezervasyon_api_durumlari_dogru_dondurur():
    simdi = datetime.now()

    conn = MagicMock()
    cursor = conn.cursor.return_value

    cursor.fetchall.return_value = [
        (
            1, "CHZ-001", "EEG",
            simdi - timedelta(days=2),
            simdi - timedelta(days=1),
            False, "Oda-1", "Araştırma", "Pilot çalışma", 4, "Psikoloji",
        ),
        (
            2, "CHZ-002", "X-Ray",
            simdi + timedelta(hours=1),
            simdi + timedelta(hours=2),
            False, None, None, None, None, None,                       # oda ve proje bilgisi girilmemiş (LEFT JOIN: oda boş olabilir)
        ),
        (
            3, "CHZ-003", "EKG",
            simdi - timedelta(days=1),
            simdi + timedelta(hours=1),
            True, "Oda-2", "Test", "", 4, "Psikoloji",
        ),
    ]

    with patch("server.sunucu.psycopg2.connect", return_value=conn):
        sonuc = rezervasyonlari_listele(kullanici_id=1)

    assert [r["durum"] for r in sonuc] == [
        "Tamamlandı",
        "Aktif",
        "İptal Edildi",
    ]

    assert sonuc[0]["cihaz_id"] == "CHZ-001 - EEG"                       # eski alan değişmeden kalır (geriye uyumluluk)
    assert (sonuc[0]["envanter_kodu"], sonuc[0]["cihaz_adi"]) == ("CHZ-001", "EEG")
    assert (sonuc[0]["oda_adi"], sonuc[0]["proje_turu"], sonuc[0]["proje_adi_aciklamasi"]) == ("Oda-1", "Araştırma", "Pilot çalışma")
    assert sonuc[1]["oda_adi"] is None and sonuc[1]["proje_turu"] is None
    assert (sonuc[0]["bolum_id"], sonuc[0]["bolum_adi"]) == (4, "Psikoloji") and sonuc[1]["bolum_adi"] is None
    sorgu = str(cursor.execute.call_args.args[0])
    assert "LEFT JOIN bolumler" in sorgu and "LEFT JOIN odalar" in sorgu                                  # odası seçilmemiş rezervasyon listeden düşmemeli

    conn.close.assert_called_once()


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_tamamlanan_rezervasyonda_iptal_butonu_yok(qt_app):
    cevap = MagicMock()
    cevap.status_code = 200
    cevap.json.return_value = [
        {
            "rezervasyon_id": 1,
            "cihaz_id": "CHZ-001 - EEG",
            "baslangic_zamani": "2026-10-20T09:00:00",
            "bitis_zamani": "2026-10-20T10:00:00",
            "durum": "Tamamlandı",
        },
        {
            "rezervasyon_id": 2,
            "cihaz_id": "CHZ-002 - X-Ray",
            "baslangic_zamani": "2026-12-20T09:00:00",
            "bitis_zamani": "2026-12-20T10:00:00",
            "durum": "Aktif",
        },
        {
            "rezervasyon_id": 3,
            "cihaz_id": "CHZ-003 - EKG",
            "baslangic_zamani": "2026-10-21T09:00:00",
            "bitis_zamani": "2026-10-21T10:00:00",
            "durum": "İptal Edildi",
        },
    ]

    with patch(
        'client.cihaz_rezervasyon_ekranlari.oturum_kontrollu_istek',
        return_value=cevap,
    ), patch(
        'client.cihaz_rezervasyon_ekranlari.oturum_hatasi_mi',
        return_value=False,
    ):
        ekran = RezervasyonYonetimEkrani(
            "http://testserver",
            "test-token",
            yetkili_mi=True,
        )

    tablo = ekran.tablo

    assert tablo.rowCount() == 3

    assert tablo.item(0, 5).text() == "Tamamlandı"
    assert tablo.cellWidget(0, 6) is None

    assert tablo.item(1, 5).text() == "Aktif"
    assert tablo.cellWidget(1, 6) is not None

    assert tablo.item(2, 5).text() == "İptal Edildi"
    assert tablo.cellWidget(2, 6) is None

    ekran.close()
