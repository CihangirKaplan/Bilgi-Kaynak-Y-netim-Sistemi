"""Liste sayfalarının ortak görünümü (renkler, düğmeler, giriş kutuları, tablo, özet kartı, durum etiketi).

Ana pencerenin (`main_window.STIL`) renk ve yazı diliyle uyumludur: lacivert başlıklar, açık mavi zemin, beyaz yuvarlak kartlar.
Bir sayfa `liste_sayfasi_stili()` çıktısını kendi `setStyleSheet`'ine verir ve nesne adlarını aşağıdaki gibi kullanır:

    baslik / altBaslik            sayfa başlığı ve açıklaması
    kart                          beyaz yuvarlak çerçeve (süzgeç alanı, tablo kartı)
    birincil / hayalet / tehlike  düğme türleri
    ozetKart / ozetEtiket / ozetDeger / ozetSerit   özet kartları
    rozet                         küçük sayaç etiketi
    altBilgi                      kart altındaki açıklama satırı
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QStyle, QStyledItemDelegate,
    QStyleOptionViewItem, QVBoxLayout,
)

LACIVERT = "#0A1F5C"
METIN = "#0F2552"
SOLUK = "#6B7FA8"
MAVI = "#1D4ED8"
CIZGI = "#E3EAF5"

# Durum adı -> (yazı rengi, zemin rengi). Ana sayfadaki durum etiketleriyle aynı renk ailesi.
DURUM_RENKLERI = {
    "Planlandı": ("#1D4ED8", "#DBEAFE"),
    "Devam Ediyor": ("#B45309", "#FEF3C7"),
    "Tamamlandı": ("#15803D", "#DCFCE7"),
    "İptal Edildi": ("#B91C1C", "#FEE2E2"),
}
VARSAYILAN_DURUM_RENGI = ("#475569", "#E2E8F0")

TABLO_STILI = f"""
QTableWidget {{ background: white; border: none; font-size: 13px; color: {METIN}; outline: 0; }}
QTableWidget::item {{ padding: 6px 12px; border-bottom: 1px solid #EEF2FA; }}
QTableWidget::item:selected {{ background: #EEF4FF; color: {METIN}; }}
QTableWidget::item:hover {{ background: #F7FAFF; }}
QHeaderView::section {{ background: #F3F7FF; color: {SOLUK}; padding: 12px 12px; font-size: 11px; font-weight: 800;
                       border: none; border-bottom: 1px solid #E3EAF5; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C5D3EE; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #9FB6E3; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


def liste_sayfasi_stili():
    """Bir liste sayfasının tamamı için stil metni (nesne adlarıyla çalışır; sayfadaki başka pencereleri bozmaz)."""
    return f"""
QLabel#baslik {{ font-size: 24px; font-weight: 800; color: {LACIVERT}; }}
QLabel#altBaslik {{ font-size: 13px; color: {SOLUK}; }}
QLabel#altBilgi {{ font-size: 12px; color: {SOLUK}; }}
QLabel#kartBaslik {{ font-size: 16px; font-weight: 800; color: {LACIVERT}; }}
QLabel#etiket {{ font-size: 12px; font-weight: 700; color: {SOLUK}; }}
QLabel#rozet {{ background: #EEF4FF; color: #3B5BA9; border-radius: 11px; font-size: 11px; font-weight: 800; padding: 4px 12px; }}

QFrame#kart, QFrame#ozetKart {{ background: white; border: none; border-radius: 16px; }}
QFrame#ozetSerit {{ border: none; border-radius: 2px; }}
QLabel#ozetEtiket {{ font-size: 12px; font-weight: 700; color: {SOLUK}; }}
QLabel#ozetDeger {{ font-size: 30px; font-weight: 800; }}

QLineEdit, QComboBox, QDateEdit {{
    background: white; color: {METIN}; border: 1px solid #C7D9FB; border-radius: 10px; padding: 8px 12px; min-height: 22px;
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {{ border: 1px solid #93B4F5; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 2px solid #2563EB; padding: 7px 11px; }}
QComboBox {{ min-width: 120px; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: white; color: {METIN}; selection-background-color: #2563EB; selection-color: white;
                               border: 1px solid #C7D9FB; outline: none; }}

QPushButton {{ border-radius: 10px; padding: 9px 16px; font-size: 13px; font-weight: 700; }}
QPushButton#hayalet {{ background: #F1F5FD; color: {LACIVERT}; border: 1px solid #D1DFF3; }}
QPushButton#hayalet:hover {{ background: #E3EDFF; border: 1px solid #93B4F5; }}
QPushButton#birincil {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6); color: white; border: none; }}
QPushButton#birincil:hover {{ background: #1E40AF; }}
QPushButton#birincil:pressed {{ background: #172554; }}
QPushButton#tehlike {{ background: white; color: #B91C1C; border: 1px solid #FECACA; }}
QPushButton#tehlike:hover {{ background: #FEE2E2; border: 1px solid #F87171; }}
QPushButton#yesil {{ background: #16803C; color: white; border: none; }}
QPushButton#yesil:hover {{ background: #126A31; }}
QPushButton#kucuk {{ background: #E9F1FF; color: #2457A2; border: none; border-radius: 8px; padding: 0; min-height: 0; font-size: 12px; }}
QPushButton#kucuk:hover {{ background: #D4E5FF; }}
QPushButton#hayalet:disabled, QPushButton#birincil:disabled, QPushButton#tehlike:disabled, QPushButton#yesil:disabled {{
    background: #F4F6FA; color: #A3B1CE; border: 1px solid #E8EDF6; }}
QLabel#bosMesaj {{ font-size: 15px; font-weight: 700; color: #8A9BC0; padding: 40px; }}
"""


def dialog_stili():
    """Ekleme/düzenleme pencereleri için stil metni (liste sayfasıyla aynı renk ve kutu dili).

    Nesne adları: formBaslik, ipucu, hata (yazılar); oturumSatiri (beyaz satır kartı); birincil / tehlike (düğmeler).
    Adsız düğme "hayalet" görünür; böylece yalnızca ana işlem (Kaydet, Ekle) öne çıkar.
    """
    return f"""
QDialog {{ background: #F4F7FD; }}
QLabel {{ color: {METIN}; font-size: 13px; background: transparent; }}
QLabel#formBaslik {{ font-size: 16px; font-weight: 800; color: {LACIVERT}; }}
QLabel#ipucu {{ font-size: 12px; color: {SOLUK}; }}
QLabel#hata {{ font-size: 12px; font-weight: 700; color: #B91C1C; }}
QLabel#alanAdi {{ font-size: 13px; font-weight: 700; color: {SOLUK}; }}
QLabel#onizleme {{ font-size: 13px; font-weight: 700; color: {MAVI}; background: #EEF4FF; border-radius: 10px; padding: 8px 12px; }}

QLineEdit, QComboBox, QDateEdit, QTimeEdit {{
    background: white; color: {METIN}; border: 1px solid #C7D9FB; border-radius: 10px; padding: 7px 12px; min-height: 22px;
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTimeEdit:hover {{ border: 1px solid #93B4F5; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {{ border: 2px solid #2563EB; padding: 6px 11px; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: white; color: {METIN}; selection-background-color: #2563EB; selection-color: white;
                               border: 1px solid #C7D9FB; outline: none; }}

QFrame#oturumSatiri {{ background: white; border: 1px solid #E3EAF5; border-radius: 12px; }}
QCheckBox {{ color: {METIN}; font-size: 13px; font-weight: 600; spacing: 6px; background: transparent; }}

QPushButton {{ background: #F1F5FD; color: {LACIVERT}; border: 1px solid #D1DFF3; border-radius: 10px;
               padding: 9px 16px; font-size: 13px; font-weight: 700; }}
QPushButton:hover {{ background: #E3EDFF; border: 1px solid #93B4F5; }}
QPushButton:disabled {{ background: #F4F6FA; color: #A3B1CE; border: 1px solid #E8EDF6; }}
QPushButton#birincil {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6); color: white; border: none; }}
QPushButton#birincil:hover {{ background: #1E40AF; }}
QPushButton#birincil:disabled {{ background: #C9D6EE; color: white; border: none; }}
QPushButton#tehlike {{ background: white; color: #B91C1C; border: 1px solid #FECACA; }}
QPushButton#tehlike:hover {{ background: #FEE2E2; border: 1px solid #F87171; }}
"""


def golge(widget, blur=26, alpha=26, dy=5):
    """Kartlara ana pencereyle aynı yumuşak gölgeyi verir."""
    etki = QGraphicsDropShadowEffect(widget)
    etki.setBlurRadius(blur)
    etki.setOffset(0, dy)
    etki.setColor(QColor(10, 31, 92, alpha))
    widget.setGraphicsEffect(etki)


def kart_olustur(ad="kart"):
    kart = QFrame()
    kart.setObjectName(ad)
    golge(kart)
    return kart


def ozet_karti_olustur(etiket, renk):
    """Sol kenarında renkli şerit olan özet kartı. (kart, değer_etiketi) döner; değeri `degeri.setText(...)` ile güncelle."""
    kart = kart_olustur("ozetKart")
    yatay = QHBoxLayout(kart)
    yatay.setContentsMargins(16, 14, 18, 14)
    yatay.setSpacing(14)

    serit = QFrame()
    serit.setObjectName("ozetSerit")
    serit.setFixedWidth(4)
    serit.setStyleSheet(f"QFrame#ozetSerit {{ background: {renk}; }}")
    yatay.addWidget(serit)

    dikey = QVBoxLayout()
    dikey.setSpacing(2)
    yazi = QLabel(etiket)
    yazi.setObjectName("ozetEtiket")
    deger = QLabel("0")
    deger.setObjectName("ozetDeger")
    deger.setStyleSheet(f"QLabel#ozetDeger {{ color: {renk}; }}")
    dikey.addWidget(yazi)
    dikey.addWidget(deger)
    yatay.addLayout(dikey, 1)
    return kart, deger


class DurumRozetiDelegate(QStyledItemDelegate):
    """Durum hücresini renkli, yuvarlak bir etiket olarak çizer.

    Hücrenin metni değişmez (sıralama, arama ve testler eskisi gibi çalışır); yalnızca çizim değişir. Tanımsız durum gri çizilir.
    """

    def __init__(self, renkler=None, parent=None):
        super().__init__(parent)
        self.renkler = renkler or DURUM_RENKLERI

    def renk_bul(self, index, metin):
        """(yazı rengi, zemin rengi). Alt sınıflar, rengi hücre metni yerine başka bir veriden (ör. işlem kodu) bulabilir."""
        return self.renkler.get(metin, VARSAYILAN_DURUM_RENGI)

    def paint(self, painter, option, index):
        metin = str(index.data(Qt.DisplayRole) or "")
        secenek = QStyleOptionViewItem(option)
        self.initStyleOption(secenek, index)
        secenek.text = ""                                           # zemin ve seçim rengi stile çizdirilir, etiketi biz çizeriz
        stil = secenek.widget.style() if secenek.widget else QApplication.style()
        stil.drawControl(QStyle.CE_ItemViewItem, secenek, painter, secenek.widget)
        if not metin:
            return

        yazi_rengi, zemin = self.renk_bul(index, metin)
        yazi = QFont(option.font)
        yazi.setPixelSize(12)
        yazi.setBold(True)
        olcu = QFontMetrics(yazi)
        genislik = min(olcu.horizontalAdvance(metin) + 24, option.rect.width() - 16)
        yukseklik = olcu.height() + 8
        sol = option.rect.left() + 12
        ust = option.rect.top() + (option.rect.height() - yukseklik) / 2
        kutu = QRectF(sol, ust, max(genislik, 24), yukseklik)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(zemin))
        painter.drawRoundedRect(kutu, yukseklik / 2, yukseklik / 2)
        painter.setPen(QColor(yazi_rengi))
        painter.setFont(yazi)
        painter.drawText(kutu, Qt.AlignCenter, olcu.elidedText(metin, Qt.ElideRight, int(kutu.width() - 12)))
        painter.restore()

    def sizeHint(self, option, index):
        boyut = super().sizeHint(option, index)
        boyut.setWidth(boyut.width() + 24)
        return boyut
