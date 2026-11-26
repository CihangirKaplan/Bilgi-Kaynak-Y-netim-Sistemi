"""Başlığın yanında duran küçük, sakin bilgi rozeti: göz simgesi + kısa etiket ("Görüntüleme sayfası").

Buradan işlem yapılmayan sayfalarda kullanıcıya sayfanın ne işe yaradığını gösterir. Ayrıntı rozete **tıklayınca** küçük bir
açıklama balonunda açılır; böylece sayfa kalabalıklaşmaz. (Uygulamada fare üzerine gelince açılan ipuçları kapalıdır, bu yüzden
açıklama ipucu değil, tıklamayla açılan balondur: bkz. client/ipucu_kapat.py.)
"""
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

ROZET_METNI = "Görüntüleme sayfası"       # işlem yapılmayan sayfaların başlığındaki rozet (hepsinde aynı ifade)
GOZ_SIMGESI = (Path(__file__).resolve().parent / "assets" / "tkys_goz.svg").as_posix()


class BilgiBalonu(QFrame):
    """Tıklanan öğenin hemen altında açılan küçük açıklama kutusu; dışarı tıklayınca ya da Esc ile kapanır, kendini siler."""

    def __init__(self, metin, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("bilgiBalonu")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet(
            "QFrame#bilgiBalonu { background: white; border: 1px solid #C7D9FB; border-radius: 10px; }"
            "QFrame#bilgiBalonu QLabel { background: transparent; border: none; color: #0F2552; font-size: 12px; }"
        )
        yerlesim = QVBoxLayout(self)
        yerlesim.setContentsMargins(14, 11, 14, 11)
        self.etiket = QLabel(metin)
        self.etiket.setWordWrap(True)
        self.etiket.setTextFormat(Qt.PlainText)
        self.etiket.setMaximumWidth(360)
        self.etiket.setMinimumWidth(280)
        yerlesim.addWidget(self.etiket)

    @classmethod
    def goster(cls, hedef, metin):
        """`hedef` öğenin altında balonu açar ve döndürür."""
        balon = cls(metin, hedef.window())
        balon.adjustSize()
        balon.move(hedef.mapToGlobal(QPoint(0, hedef.height() + 4)))
        balon.show()
        return balon


class BilgiRozeti(QFrame):
    def __init__(self, metin, aciklama, parent=None):
        super().__init__(parent)
        self.aciklama = aciklama
        self.setObjectName("bilgiRozeti")
        self.setStyleSheet(
            "QFrame#bilgiRozeti { background: #EEF4FF; border: none; border-radius: 11px; }"
            "QFrame#bilgiRozeti QLabel { background: transparent; border: none; color: #3B5BA9; font-size: 12px; font-weight: 700; }"
        )
        self.setAccessibleDescription(aciklama)
        self.setCursor(Qt.PointingHandCursor)
        yerlesim = QHBoxLayout(self)
        yerlesim.setContentsMargins(9, 3, 12, 3)
        yerlesim.setSpacing(6)
        self.simge = QLabel()
        self.simge.setObjectName("bilgiRozetiSimge")
        self.simge.setPixmap(self._simge_pixmap())
        self.etiket = QLabel(metin)
        yerlesim.addWidget(self.simge)
        yerlesim.addWidget(self.etiket)
        # Fare olayları rozete ulaşsın (tıklayınca açıklama balonu açılır).
        self.simge.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.etiket.setAttribute(Qt.WA_TransparentForMouseEvents)

    @staticmethod
    def _simge_pixmap(boyut=14):
        oran = 2.0                                           # keskin görünüm için çift çözünürlükte çizilir
        pixmap = QPixmap(int(boyut * oran), int(boyut * oran))
        pixmap.fill(Qt.transparent)
        boyayici = QPainter(pixmap)
        QSvgRenderer(GOZ_SIMGESI).render(boyayici)
        boyayici.end()
        pixmap.setDevicePixelRatio(oran)
        return pixmap

    def mousePressEvent(self, olay):
        BilgiBalonu.goster(self, self.aciklama)
        super().mousePressEvent(olay)


class TiklaninceAciklayanKutu(QFrame):
    """Takvimdeki randevu/rezervasyon/etkinlik kutusu: tıklanınca, kaydı nereden düzenleyeceğini söyleyen balon açar
    (bu sayfada kayıt değiştirilmez; sessizce hiçbir şey olmaması kullanıcıyı şaşırtıyordu)."""

    def __init__(self, aciklama, parent=None):
        super().__init__(parent)
        self.aciklama = aciklama
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, olay):
        BilgiBalonu.goster(self, self.aciklama)
        super().mousePressEvent(olay)
