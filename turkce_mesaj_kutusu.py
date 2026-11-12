"""TKYS mesaj kutularında standart butonların Türkçe gösterimi."""

from PySide6.QtWidgets import QMessageBox


BUTON_METINLERI = {
    QMessageBox.StandardButton.Ok: "Tamam",
    QMessageBox.StandardButton.Yes: "Evet",
    QMessageBox.StandardButton.No: "Hayır",
    QMessageBox.StandardButton.Cancel: "İptal",
    QMessageBox.StandardButton.Save: "Kaydet",
    QMessageBox.StandardButton.Close: "Kapat",
    QMessageBox.StandardButton.Apply: "Uygula",
    QMessageBox.StandardButton.Discard: "Vazgeç",
    QMessageBox.StandardButton.Retry: "Yeniden Dene",
    QMessageBox.StandardButton.Ignore: "Yoksay",
}


def butonlari_turkcelestir(kutu):
    """Mesaj kutusundaki mevcut standart butonların metinlerini düzenler."""
    for buton, metin in BUTON_METINLERI.items():
        dugme = kutu.button(buton)
        if dugme is not None:
            dugme.setText(metin)
    return kutu


def mesaj_kutusu(govde, baslik, mesaj, ikon, butonlar=None,
                 varsayilan=None):
    """Standart butonları Türkçe olan mesaj kutusu oluşturur."""
    kutu = QMessageBox(govde)
    kutu.setWindowTitle(baslik)
    kutu.setText(mesaj)
    kutu.setIcon(ikon)

    if butonlar is not None:
        kutu.setStandardButtons(butonlar)

    if varsayilan is not None:
        kutu.setDefaultButton(varsayilan)

    butonlari_turkcelestir(kutu)
    return kutu.exec()


def soru(govde, baslik, mesaj, butonlar=None, varsayilan=None):
    if butonlar is None:
        butonlar = QMessageBox.Yes | QMessageBox.No
    return mesaj_kutusu(
        govde, baslik, mesaj, QMessageBox.Question,
        butonlar, varsayilan
    )


def bilgi(govde, baslik, mesaj):
    return mesaj_kutusu(
        govde, baslik, mesaj, QMessageBox.Information,
        QMessageBox.Ok
    )


def uyari(govde, baslik, mesaj):
    return mesaj_kutusu(
        govde, baslik, mesaj, QMessageBox.Warning,
        QMessageBox.Ok
    )


def hata(govde, baslik, mesaj):
    return mesaj_kutusu(
        govde, baslik, mesaj, QMessageBox.Critical,
        QMessageBox.Ok
    )
