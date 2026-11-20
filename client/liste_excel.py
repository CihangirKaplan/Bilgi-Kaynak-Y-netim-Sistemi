"""TKYS - Liste sayfalarından Excel (.xlsx) aktarımı.

Cihaz Envanteri, Öğrenciler ve Danışanlar gibi liste sayfaları ekranda o an görünen (aramaya/süzgeçlere uyan) satırları
tek tıkla Excel'e aktarır. Dosya, raporlarla aynı biçimdedir: 'Özet' sayfası (aktarım zamanı, süzgeçler, satır sayısı)
ve tablonun kendisi. Metin hücreleri formül olarak yorumlanmaz (formül enjeksiyonuna karşı).
"""
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QPushButton

from client.rapor_excel_genel import excel_olustur

EXCEL_DUGME_STILI = (
    "QPushButton { background: #ECFDF3; color: #166534; border: 1px solid #BBF7D0; border-radius: 12px; "
    "padding: 10px 18px; font-size: 13px; font-weight: 700; } "
    "QPushButton:hover { background: #DCFCE7; } "
    "QPushButton:disabled { background: #F1F5F9; color: #94A3B8; border-color: #E2E8F0; }"
)


def excel_dugmesi_olustur(tikla):
    """Yenile düğmesinin yanına konan, yeşil 'Excel'e Aktar' düğmesi."""
    dugme = QPushButton("⬇  Excel'e Aktar")
    dugme.setCursor(Qt.PointingHandCursor)
    dugme.setStyleSheet(EXCEL_DUGME_STILI)
    dugme.clicked.connect(lambda *_: tikla())
    return dugme


def dosya_adi_olustur(onek, simdi=None):
    return f"{onek}_{(simdi or datetime.now()).strftime('%Y%m%d_%H%M')}.xlsx"


def listeyi_excele_aktar(pencere, baslik, onek, kolonlar, satirlar, filtre_ozeti=(), sayfa_adi="Liste", aciklama=""):
    """Görünen satırları kullanıcının seçtiği .xlsx dosyasına yazar. Başarılıysa dosya yolunu, aksi halde None döndürür.

    kolonlar: [(başlık, sayı/tarih biçimi veya None)]; satirlar: değer listeleri; filtre_ozeti: [(ad, değer)].
    """
    satirlar = [list(s) for s in satirlar]
    if not satirlar:
        QMessageBox.information(pencere, "Excel'e Aktar", "Aktarılacak kayıt yok. Arama ya da süzgeçleri kontrol edin.")
        return None

    dosya_yolu, _ = QFileDialog.getSaveFileName(pencere, "Listeyi Kaydet", dosya_adi_olustur(onek), "Excel Dosyası (*.xlsx)")
    if not dosya_yolu:
        return None
    if not dosya_yolu.lower().endswith(".xlsx"):
        dosya_yolu += ".xlsx"

    try:
        excel_olustur(
            dosya_yolu,
            baslik,
            aciklama or f"{baslik} sayfasında ekranda görünen kayıtlar.",
            list(filtre_ozeti),
            [("Aktarılan Kayıt", len(satirlar), "Ekranda görünen ve Excel'e yazılan satır sayısı.")],
            [(sayfa_adi, list(kolonlar), satirlar, f"{baslik} - ekrandaki sütunlar ve kayıtlar.")],
        )
    except OSError as hata:
        QMessageBox.warning(
            pencere, "Kaydedilemedi",
            f"Dosya kaydedilemedi. Aynı adlı dosya Excel'de açık olabilir ya da klasöre yazma izniniz olmayabilir.\n{hata}",
        )
        return None
    QMessageBox.information(pencere, "Excel'e Aktar", f"{len(satirlar)} kayıt kaydedildi:\n{dosya_yolu}")
    return dosya_yolu
