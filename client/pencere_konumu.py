"""Açılan ikinci pencereleri (form, iletişim kutusu, uyarı) ana pencerenin SAĞ İÇERİK alanının tam ortasına yerleştirir.

Sol menü açık ya da dar olsa da pencere, menünün sağındaki alanın ortasında açılır; ekranın dışına taşmaz. Uygulama genelinde
tek bir olay süzgeciyle çalışır: ayrı ayrı pencerelerde kod gerekmez, sonradan eklenen pencereler de otomatik kapsanır.
Açılır menüler, ipuçları ve açılır liste kutuları (Popup/ToolTip) dokunulmaz.
"""
import weakref

from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget


class _Ortalayici(QObject):
    def __init__(self):
        super().__init__()
        self._ana = None
        self._referans = None
        self._kurulu = False

    def tani(self, ana, referans):
        """ana: ana pencere; referans: içerik alanı bileşenini döndüren çağrılabilir (menü daralınca boyutu değişir)."""
        self._ana = weakref.ref(ana)
        self._referans = referans
        uygulama = QApplication.instance()
        if uygulama is not None and not self._kurulu:
            uygulama.installEventFilter(self)
            self._kurulu = True

    def _ana_pencere(self):
        ana = self._ana() if self._ana is not None else None
        try:
            if ana is None or not ana.isVisible() or ana.isMinimized():
                return None
        except RuntimeError:        # Qt nesnesi silinmiş
            return None
        return ana

    def eventFilter(self, nesne, olay):
        if olay.type() == QEvent.Show and isinstance(nesne, QWidget) and nesne.isWindow():
            if self.ortala(nesne):
                QTimer.singleShot(0, lambda n=nesne: self._gecikmeli(n))   # çerçeve boyutu kesinleşince düzelt
        elif olay.type() == QEvent.Resize and isinstance(nesne, QWidget) and nesne.isWindow() and nesne.isVisible():
            # Pencere açıldıktan sonra içeriği değişip büyürse (ör. rol seçilince yetki özeti açılır) ekranın altına taşmasın.
            if nesne.property("tkys_ortalandi") and not nesne.property("tkys_ortalama_bekliyor"):
                nesne.setProperty("tkys_ortalama_bekliyor", True)
                QTimer.singleShot(0, lambda n=nesne: self._boyut_degisti(n))
        return False

    def _boyut_degisti(self, pencere):
        try:
            pencere.setProperty("tkys_ortalama_bekliyor", False)
            if pencere.isVisible():
                self.ortala(pencere)
        except RuntimeError:
            pass

    def _gecikmeli(self, pencere):
        try:
            if pencere.isVisible():
                self.ortala(pencere)
        except RuntimeError:
            pass

    def ortala(self, pencere):
        """Pencereyi içerik alanının ortasına taşır. Taşıdıysa True."""
        ana = self._ana_pencere()
        if ana is None or pencere is ana:
            return False
        if pencere.windowType() not in (Qt.Dialog, Qt.Window) or pencere.property("ortalama_kapali"):
            return False
        try:
            alan = self._referans() if self._referans is not None else ana
            if alan is None or not alan.isVisible():
                alan = ana
            merkez = alan.mapToGlobal(alan.rect().center())
            cerceve = pencere.frameGeometry()
            sol = merkez.x() - cerceve.width() // 2
            ust = merkez.y() - cerceve.height() // 2
            ekran = QGuiApplication.screenAt(merkez) or ana.screen()
            if ekran is not None:                      # pencere ekranın dışına taşmasın
                a = ekran.availableGeometry()
                if cerceve.height() > a.height() * 0.75:     # ekranı neredeyse dolduran pencere: üstte ve altta eşit boşluk kalsın
                    ust = a.top() + (a.height() - cerceve.height()) // 2
                sol = max(a.left(), min(sol, a.right() - cerceve.width() + 1))
                ust = max(a.top(), min(ust, a.bottom() - cerceve.height() + 1))
            pencere.move(QPoint(sol, ust))
            pencere.setProperty("tkys_ortalandi", True)
            return True
        except RuntimeError:
            return False


_ORTALAYICI = _Ortalayici()


def ana_pencereyi_tanit(ana, referans=None):
    _ORTALAYICI.tani(ana, referans)


def ortala(pencere):
    """Boyutu sonradan değişen pencereyi yeniden ortalar."""
    return _ORTALAYICI.ortala(pencere)
