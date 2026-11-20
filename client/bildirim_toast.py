"""TKYS - Başarı bildirimi (toast): ekranın altında kısa süre görünüp kendiliğinden kaybolur.

Sık yapılan işlemlerden sonra çıkan "Kaydedildi → Tamam'a bas" pencerelerinin yerine kullanılır; kullanıcının akışını
bölmez, tıklama gerektirmez. Hata ve uyarılar (QMessageBox.warning/critical) olduğu gibi pencere olarak kalır: onlar okunmalı.
"""
from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QGraphicsOpacityEffect, QLabel, QWidget

STIL = (
    "QLabel { background: #14532D; color: white; border-radius: 12px; padding: 12px 22px; "
    "font-size: 13px; font-weight: 700; }"
)
SURE_MS = 2800
ALT_BOSLUK = 36


def _ana_pencere(pencere):
    """Bildirimin bağlanacağı üst pencere. Form (QDialog) kapanırken bildirim yok olmasın diye formun sahibi pencere seçilir."""
    aday = pencere
    while aday is not None and isinstance(aday, QDialog) and aday.parentWidget() is not None:
        aday = aday.parentWidget().window()
    if aday is None or isinstance(aday, QDialog):
        etkin = QApplication.activeWindow()
        if etkin is not None and not isinstance(etkin, QDialog):
            return etkin
        for ust in QApplication.topLevelWidgets():
            if ust.isVisible() and not isinstance(ust, QDialog):
                return ust
        return aday
    return aday.window()


def basari_bildirimi(pencere, mesaj, sure_ms=SURE_MS):
    """Ana pencerenin altında ortalanmış kısa bildirim gösterir; yeni bildirim eskisinin yerini alır. Etiketi döndürür (test için)."""
    ust = _ana_pencere(pencere) if isinstance(pencere, QWidget) else None
    if ust is None:
        return None
    eski = getattr(ust, "_tkys_toast", None)
    if eski is not None:
        eski.hide()
        eski.deleteLater()

    etiket = QLabel(str(mesaj), ust)
    etiket.setObjectName("tkysToast")
    etiket.setStyleSheet(STIL)
    etiket.setAlignment(Qt.AlignCenter)
    etiket.setWordWrap(True)
    etiket.setAttribute(Qt.WA_TransparentForMouseEvents)
    etiket.setMaximumWidth(max(320, int(ust.width() * 0.7)))
    etiket.adjustSize()
    etiket.move(max((ust.width() - etiket.width()) // 2, 0), max(ust.height() - etiket.height() - ALT_BOSLUK, 0))
    efekt = QGraphicsOpacityEffect(etiket)
    etiket.setGraphicsEffect(efekt)
    etiket.show()
    etiket.raise_()

    anim = QPropertyAnimation(efekt, b"opacity", etiket)
    anim.setDuration(350)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.finished.connect(etiket.deleteLater)
    QTimer.singleShot(sure_ms, anim.start)
    etiket._animasyon = anim
    ust._tkys_toast = etiket
    return etiket
