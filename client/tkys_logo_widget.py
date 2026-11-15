from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QLabel


def sol_panel_logosu_kur(pencere):
    """Sol panel logosunu tiklanabilir ana sayfa butonuna cevirir."""

    kart = getattr(pencere, "logo_karti", None)

    if kart is None:
        return

    if kart.findChild(QPushButton, "tkysAnaSayfaLogosu"):
        return

    dosya = (
        Path(__file__).resolve().parent
        / "assets"
        / "tkys_travma_logo.png"
    )

    if not dosya.is_file():
        raise FileNotFoundError(f"Logo bulunamadi: {dosya}")

    logo = QIcon(str(dosya))

    if logo.isNull():
        raise ValueError("Logo yuklenemedi.")

    for etiket in kart.findChildren(QLabel):
        etiket.hide()

    yerlesim = kart.layout()

    if yerlesim is None:
        yerlesim = QHBoxLayout(kart)
    else:
        def temizle(duzen):
            while duzen.count():
                oge = duzen.takeAt(0)

                if oge.widget() is not None:
                    oge.widget().hide()

                if oge.layout() is not None:
                    temizle(oge.layout())

        temizle(yerlesim)

    yerlesim.setContentsMargins(4, 4, 4, 4)
    yerlesim.setSpacing(0)

    kart.setFixedHeight(100)

    kart.setStyleSheet("""
        QFrame#logo {
            background: transparent;
            border: none;
            border-radius: 0px;
        }
    """)

    buton = QPushButton(kart)
    buton.setObjectName("tkysAnaSayfaLogosu")
    buton.setToolTip("Ana Kontrol Paneline Git")
    buton.setCursor(Qt.PointingHandCursor)

    buton.setFixedSize(100, 92)
    buton.setIcon(logo)
    buton.setIconSize(QSize(88, 88))

    buton.setStyleSheet("""
        QPushButton#tkysAnaSayfaLogosu {
            background: transparent;
            border: none;
            border-radius: 10px;
            padding: 0;
        }

        QPushButton#tkysAnaSayfaLogosu:hover {
            background: #234F85;
        }
    """)

    buton.clicked.connect(pencere.ana_ekrana_don)

    yerlesim.addWidget(
        buton,
        0,
        Qt.AlignCenter
    )
