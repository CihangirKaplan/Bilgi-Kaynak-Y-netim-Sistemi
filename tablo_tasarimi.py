"""Bakım / kalibrasyon gibi liste ekranlarının ortak görünümü ve yardımcı bileşenleri."""
import datetime
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
                               QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
                               QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

SATIR_YUKSEKLIK = 54

TABLO_STIL = """
    QTableWidget { background: white; border: none; font-size: 13px; color: #0F2552; }
    QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #EEF2FA; }
    QTableWidget::item:selected { background: #EEF4FF; color: #0F2552; }
    QHeaderView::section { background: #F3F7FF; color: #6B7FA8; padding: 12px 10px;
                           font-size: 11px; font-weight: 800; border: none; }
"""

# Form pencerelerinin (Yeni / Düzenle) ortak görünümü
FORM_STIL = """
    QDialog { background: #F4F7FC; }
    QLabel { color: #1E3A8A; font-size: 13px; font-weight: 700; background: transparent; }
    QLineEdit, QComboBox, QDateEdit, QTextEdit {
        background: white; color: #0F2552; border: 1px solid #C7D9FB;
        border-radius: 10px; padding: 9px 12px; font-size: 13px;
    }
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTextEdit:focus { border: 2px solid #3B82F6; }
    QLineEdit:read-only { background: #EAF0FA; color: #6B7FA8; }
    QComboBox QAbstractItemView { background: white; color: #0F2552;
        selection-background-color: #2563EB; selection-color: white; }
    QCalendarWidget QWidget { alternate-background-color: #EAF0FA; color: #0F2552; }
    QPushButton#kaydet { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #1D4ED8, stop:1 #3B82F6);
        color: white; border: none; border-radius: 10px; padding: 12px; font-size: 14px; font-weight: 800; }
    QPushButton#kaydet:hover { background: #1E40AF; }
"""

ARAMA_STIL = """
    QLineEdit { background: #F3F7FF; border: 1px solid #DCE6FA; border-radius: 12px;
                padding: 10px 14px; font-size: 13px; color: #0F2552; min-width: 260px; }
    QLineEdit:focus { border: 1px solid #3B82F6; background: white; }
"""


def tablo_olustur(kolonlar):
    tablo = QTableWidget(0, len(kolonlar))
    tablo.setHorizontalHeaderLabels(kolonlar)
    tablo.horizontalHeader().setHighlightSections(False)
    tablo.verticalHeader().setVisible(False)
    tablo.verticalHeader().setDefaultSectionSize(SATIR_YUKSEKLIK)
    tablo.setEditTriggers(QTableWidget.NoEditTriggers)
    tablo.setSelectionBehavior(QTableWidget.SelectRows)
    tablo.setSelectionMode(QTableWidget.SingleSelection)
    tablo.setFocusPolicy(Qt.NoFocus)
    tablo.setShowGrid(False)
    tablo.setWordWrap(True)
    tablo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tablo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    tablo.setStyleSheet(TABLO_STIL)
    return tablo


def metin_item(metin, ortala=False, kalin=False, renk=None):
    item = QTableWidgetItem(metin)
    if ortala:
        item.setTextAlignment(Qt.AlignCenter)
    if kalin:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    if renk:
        item.setForeground(QColor(renk))
    return item


def hap(metin, renk, arka, ipucu=None):
    """Tabloya konacak renkli durum 'hapı' (hücre widget'ı)."""
    lbl = QLabel(metin)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 12px; "
                      f"font-size: 11px; font-weight: 800; padding: 5px 12px;")
    if ipucu:
        lbl.setToolTip(ipucu)
    kap = QWidget()
    lay = QHBoxLayout(kap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.addStretch()
    lay.addWidget(lbl)
    lay.addStretch()
    return kap


def _ikon_buton(simge, ipucu, renk, arka, arka_hover, tikla):
    b = QPushButton(simge)
    b.setToolTip(ipucu)
    b.setCursor(Qt.PointingHandCursor)
    b.setFixedSize(34, 34)
    b.setStyleSheet(
        f"QPushButton {{ background: {arka}; color: {renk}; border: none; border-radius: 10px; "
        f"font-size: 15px; }} QPushButton:hover {{ background: {arka_hover}; }}")
    b.clicked.connect(tikla)
    return b


def islem_butonlari(duzenle_fn, sil_fn):
    """Satır sonu için ✎ (düzenle) ve 🗑 (sil) ikon butonları."""
    kap = QWidget()
    lay = QHBoxLayout(kap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.setSpacing(8)
    lay.addStretch()
    lay.addWidget(_ikon_buton("✎", "Düzenle", "#B45309", "#FEF3C7", "#FDE68A", duzenle_fn))
    lay.addWidget(_ikon_buton("🗑", "Sil", "#B91C1C", "#FEE2E2", "#FECACA", sil_fn))
    lay.addStretch()
    return kap


def sil_onayi(parent, baslik, mesaj):
    """Silmeden önce onay ister. Evet denirse True döner."""
    kutu = QMessageBox(parent)
    kutu.setIcon(QMessageBox.Warning)
    kutu.setWindowTitle(baslik)
    kutu.setText(mesaj)
    kutu.setInformativeText("Bu işlem geri alınamaz.")
    evet = kutu.addButton("Evet, sil", QMessageBox.DestructiveRole)
    kutu.addButton("Vazgeç", QMessageBox.RejectRole)
    kutu.setDefaultButton(kutu.buttons()[-1])
    kutu.setStyleSheet("QLabel { color: #0F2552; font-size: 13px; } QPushButton { padding: 8px 18px; }")
    kutu.exec()
    return kutu.clickedButton() is evet


def sayi_cipi(yazi, renk="#1D4ED8", arka="#DBEAFE"):
    c = QLabel(yazi)
    c.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 12px; "
                    f"font-size: 12px; font-weight: 800; padding: 6px 14px;")
    return c


def tarih_goster(deger):
    """'2026-11-10T00:00:00' / '2026-11-10' -> '10.11.2026'. Boşsa '—'."""
    if not deger or str(deger) == "Belirtilmedi":
        return "—"
    metin = str(deger)[:10]
    try:
        return datetime.date.fromisoformat(metin).strftime("%d.%m.%Y")
    except ValueError:
        return metin


def kalan_gun_hapi(deger):
    """Bir bitiş/son tarih için renkli hap döner: gecikmiş kırmızı, 30 gün içinde sarı, ötesi yeşil.

    Dönen değer: (widget, durum) — durum 'gecmis' | 'yaklasiyor' | 'iyi' | 'yok'
    """
    try:
        hedef = datetime.date.fromisoformat(str(deger)[:10])
    except (ValueError, TypeError):
        return hap("Belirtilmedi", "#6B7280", "#F3F4F6"), "yok"
    kalan = (hedef - datetime.date.today()).days
    tarih = hedef.strftime("%d.%m.%Y")
    if kalan < 0:
        return hap(f"{tarih}  ·  {-kalan} gün gecikti", "#991B1B", "#FEE2E2"), "gecmis"
    if kalan <= 30:
        yazi = "bugün" if kalan == 0 else f"{kalan} gün kaldı"
        return hap(f"{tarih}  ·  {yazi}", "#854D0E", "#FEF3C7"), "yaklasiyor"
    return hap(f"{tarih}  ·  {kalan} gün", "#166534", "#DCFCE7"), "iyi"


def sayfa_basligi(baslik, alt_baslik, arama_kutusu, yenile_butonu, cipler):
    """Ekranın üstündeki beyaz araç çubuğu kartı."""
    kart = QFrame()
    kart.setObjectName("kart")
    ana = QVBoxLayout(kart)
    ana.setContentsMargins(22, 18, 22, 16)
    ana.setSpacing(12)

    ust = QHBoxLayout()
    metinler = QVBoxLayout()
    metinler.setSpacing(0)
    b = QLabel(baslik)
    b.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")
    a = QLabel(alt_baslik)
    a.setStyleSheet("font-size: 12px; color: #6B7FA8;")
    metinler.addWidget(b)
    metinler.addWidget(a)
    ust.addLayout(metinler)
    ust.addStretch()
    arama_kutusu.setStyleSheet(ARAMA_STIL)
    ust.addWidget(arama_kutusu)
    ust.addWidget(yenile_butonu)
    ana.addLayout(ust)

    alt = QHBoxLayout()
    alt.setSpacing(10)
    for c in cipler:
        alt.addWidget(c)
    alt.addStretch()
    ana.addLayout(alt)
    return kart


def yenile_butonu_olustur(tikla):
    b = QPushButton("⟳  Yenile")
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet("QPushButton { background: #EEF4FF; color: #1D4ED8; border: 1px solid #C7D9FB; "
                    "border-radius: 12px; padding: 10px 18px; font-size: 13px; font-weight: 700; } "
                    "QPushButton:hover { background: #DBEAFE; }")
    b.clicked.connect(tikla)
    return b


def bos_mesaj_olustur(metin):
    lbl = QLabel(metin)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("font-size: 14px; color: #8A9BC0; padding: 60px;")
    lbl.hide()
    return lbl