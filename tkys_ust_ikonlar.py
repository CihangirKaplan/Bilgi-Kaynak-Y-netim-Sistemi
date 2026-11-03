
from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

IKONLAR = {
    "bell": (
        '<path fill="#E8F1FF" d="M18 8a6 6 0 0 0-12 0'
        'c0 7-3 7-3 9h18c0-2-3-2-3-9Z"/>'
        '<path d="M10 21h4"/>'
    ),
    "home": (
        '<path d="m3 10 9-7 9 7v11h-7v-7h-4v7H3z"/>'
    ),
    "user": (
        '<circle cx="12" cy="7.5" r="4"/>'
        '<path d="M4.5 21v-2a7.5 7.5 0 0 1 15 0v2"/>'
    ),
}

IKONLAR["bell_outline"] = IKONLAR["bell"].replace(
    'fill="#E8F1FF"', 'fill="none"'
)

def ust_pixmap(ad, boyut=20):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'viewBox="0 0 24 24" fill="none" '
        'stroke="#E8F1FF" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round">'
        + IKONLAR[ad] + '</svg>'
    )

    pixmap = QPixmap(boyut * 2, boyut * 2)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    QSvgRenderer(
        QByteArray(svg.encode("utf-8"))
    ).render(painter)
    painter.end()

    pixmap.setDevicePixelRatio(2)
    return pixmap

def ust_ikonu(ad):
    return QIcon(ust_pixmap(ad))
