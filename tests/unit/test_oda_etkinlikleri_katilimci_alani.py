"""Oda etkinliği katılımcı sayısı alanının arayüz testleri."""

from PySide6.QtWidgets import QApplication, QLineEdit

from client.oda_etkinlikleri_ekrani import OdaEtkinlikFormu


ODALAR = [{"oda_id": 1, "oda_adi": "Görüşme Odası"}]

PERSONELLER = [{
    "personel_id": 1,
    "kullanici_adi": "test_personel",
    "personel_kodu": "TEST-001",
}]


def test_katilimci_alani_bos_ve_sayisal():
    app = QApplication.instance() or QApplication([])
    form = OdaEtkinlikFormu(ODALAR, PERSONELLER)

    try:
        assert isinstance(form.katilimci, QLineEdit)
        assert form.katilimci.text() == ""
        assert form.katilimci.placeholderText() == "Örn. 12"
        assert form.veri()["katilimci_sayisi"] is None

        form.katilimci.setText("12")
        assert form.katilimci.hasAcceptableInput()
        assert form.veri()["katilimci_sayisi"] == 12

        for gecersiz in ("0", "-3", "100001", "abc"):
            form.katilimci.setText(gecersiz)
            assert not form.katilimci.hasAcceptableInput()

        form.katilimci.clear()
        assert form.veri()["katilimci_sayisi"] is None
    finally:
        form.close()


def test_mevcut_etkinlik_katilimci_sayisi_gorunur():
    app = QApplication.instance() or QApplication([])

    kayit = {
        "oda_id": 1,
        "organize_eden_personel_id": 1,
        "etkinlik_adi": "Eğitim Semineri",
        "katilimci_sayisi": 25,
        "gunler": [{
            "baslangic_zamani": "2048-06-15T10:00:00",
            "bitis_zamani": "2048-06-15T11:00:00",
        }],
    }

    form = OdaEtkinlikFormu(ODALAR, PERSONELLER, kayit=kayit)

    try:
        assert form.katilimci.text() == "25"
        assert form.veri()["katilimci_sayisi"] == 25

        form.katilimci.clear()
        assert form.veri()["katilimci_sayisi"] is None
    finally:
        form.close()
