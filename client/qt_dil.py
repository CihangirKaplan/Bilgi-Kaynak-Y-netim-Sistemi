"""TKYS için Qt'nin standart arayüz metinlerini Türkçeleştirir."""

from PySide6.QtCore import QLibraryInfo, QTranslator


def turkce_ceviriyi_yukle(app):
    """Qt Türkçe çevirisini QApplication üzerinde etkinleştirir."""
    if getattr(app, "_tkys_turkce_cevirici", None) is not None:
        return True

    klasor = QLibraryInfo.path(
        QLibraryInfo.LibraryPath.TranslationsPath
    )

    cevirici = QTranslator(app)

    if not cevirici.load("qtbase_tr", klasor):
        return False

    if not app.installTranslator(cevirici):
        return False

    # Çeviricinin uygulama boyunca bellekte kalmasını sağlar.
    app._tkys_turkce_cevirici = cevirici

    return True
