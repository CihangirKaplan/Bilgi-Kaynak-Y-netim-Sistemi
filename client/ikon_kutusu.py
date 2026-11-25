"""Ana sayfadaki renkli zeminli çizgi ikonlar (kart ve hızlı erişim simgeleri).

Yan menüyle aynı çizgi ikon kayıt defterini (tkys_sidebar_refined.PATHS) kullanır; renkli emoji yerine her bilgisayarda aynı
görünen, yan menüyle uyumlu SVG ikon çizer.
"""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from client.tkys_sidebar_refined import PATHS

# Hızlı erişim sayfa adı -> (ikon, ikon rengi, zemin rengi)
HIZLI_ERISIM_IKONLARI = {
    "Randevu Yönetimi": ("calendar", "#1D4ED8", "#DBEAFE"),
    "Öğrenciler": ("users", "#6D28D9", "#EDE9FE"),
    "Danışma Masası Yönetimi": ("clipboard", "#B45309", "#FEF3C7"),
    "Cihaz Rezervasyonu": ("pin", "#15803D", "#DCFCE7"),
    "Yönetim Raporları ve İstatistikler": ("chart", "#0E7490", "#CFFAFE"),
}
VARSAYILAN_IKON = ("file", "#1D4ED8", "#DBEAFE")


def _svg(tur, renk, kalinlik=1.8):
    govde = PATHS.get(tur, PATHS["file"])
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="' + renk
        + f'" stroke-width="{kalinlik}" stroke-linecap="round" stroke-linejoin="round">' + govde + "</svg>"
    )


def renkli_ikon_pixmap(tur, renk, zemin, kutu=46, ikon_boyutu=22, yaricap=14):
    """Yuvarlak köşeli yumuşak renkli zemin üzerinde ortalanmış çizgi ikon (yüksek çözünürlüklü)."""
    olcek = 2
    pixmap = QPixmap(kutu * olcek, kutu * olcek)
    pixmap.fill(Qt.transparent)
    boyayici = QPainter(pixmap)
    boyayici.setRenderHint(QPainter.Antialiasing)
    boyayici.setPen(Qt.NoPen)
    boyayici.setBrush(QColor(zemin))
    boyayici.drawRoundedRect(QRectF(0, 0, kutu * olcek, kutu * olcek), yaricap * olcek, yaricap * olcek)
    pay = (kutu - ikon_boyutu) / 2 * olcek
    QSvgRenderer(QByteArray(_svg(tur, renk).encode("utf-8"))).render(
        boyayici, QRectF(pay, pay, ikon_boyutu * olcek, ikon_boyutu * olcek))
    boyayici.end()
    pixmap.setDevicePixelRatio(olcek)
    return pixmap


def ikon_pixmap(tur, renk, boyut=18):
    """Zeminsiz çizgi ikon."""
    olcek = 2
    pixmap = QPixmap(boyut * olcek, boyut * olcek)
    pixmap.fill(Qt.transparent)
    boyayici = QPainter(pixmap)
    boyayici.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(QByteArray(_svg(tur, renk).encode("utf-8"))).render(boyayici, QRectF(0, 0, boyut * olcek, boyut * olcek))
    boyayici.end()
    pixmap.setDevicePixelRatio(olcek)
    return pixmap
