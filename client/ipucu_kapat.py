"""Uygulama genelinde fare üzerine gelince açılan ipucu kutularını (tooltip) kapatır.

Tek bir olay süzgeciyle çalışır: ekranlardaki setToolTip çağrılarına dokunmak gerekmez, sonradan eklenen ipuçları da
otomatik kapsanır. İstisna yoktur; Qt ipucu kutusunu doğrudan göstermek de yasaktır (bir test kaynağı tarar).
"""
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget


class _IpucuSusturucu(QObject):
    def eventFilter(self, nesne, olay):
        # True dönmek olayı tüketir: ipucu kutusu açılmaz.
        return olay.type() == QEvent.ToolTip and isinstance(nesne, QWidget)


_SUSTURUCU = None


def ipuclarini_kapat():
    """Süzgeci bir kez kurar (tekrar çağrılması zararsızdır)."""
    global _SUSTURUCU
    uygulama = QApplication.instance()
    if uygulama is None or _SUSTURUCU is not None:
        return
    _SUSTURUCU = _IpucuSusturucu(uygulama)
    uygulama.installEventFilter(_SUSTURUCU)
