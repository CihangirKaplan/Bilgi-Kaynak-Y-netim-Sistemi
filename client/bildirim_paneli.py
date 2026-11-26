from collections import OrderedDict

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea,
    QGraphicsDropShadowEffect, QLayout
)

from client.bildirim_ikonlari import (
    AMBER, GRI, MAVI, YESIL, bildirim_ikonu, cizgi_ikonu, emojisiz, grup_basligi, ikon_boyutu,
)
from client.ikon_kutusu import ikon_pixmap


def _ikonlu_baslik(ikon, renk, metin, stil):
    """Küçük çizgi ikon + yazı (emoji yok)."""
    kap = QWidget()
    satir = QHBoxLayout(kap)
    satir.setContentsMargins(0, 0, 0, 0)
    satir.setSpacing(8)
    resim = QLabel()
    resim.setPixmap(ikon_pixmap(ikon, renk, 16))
    resim.setFixedSize(16, 16)
    satir.addWidget(resim)
    yazi = QLabel(metin)
    yazi.setStyleSheet(stil)
    satir.addWidget(yazi)
    satir.addStretch()
    return kap


class BildirimPaneli(QFrame):
    """TKYS merkezi bildirim acilir paneli."""

    def __init__(self, bildirimler, toplam, hata, sayfa_ac, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._sayfa_ac = sayfa_ac
        self.setObjectName("bildirimPaneli")
        self.setFixedWidth(440)

        self.setStyleSheet("""
            QFrame#bildirimPaneli {
                background: transparent;
                border: none;
            }
            QFrame#bildirimKart {
                background: #FFFFFF;
                border: 1px solid #DCE5F2;
                border-radius: 14px;
            }
            QScrollArea {
                background: white;
                border: none;
            }
            QPushButton#bildirimSatiri {
                background: #F5F8FE;
                color: #102A56;
                border: 1px solid #E5ECF7;
                border-radius: 9px;
                padding: 12px;
                text-align: left;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#bildirimSatiri:hover {
                background: #E7F0FF;
                border-color: #B7CCF0;
            }
            QPushButton#bildirimKapat {
                background: transparent;
                color: #6B7FA8;
                border: none;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton#bildirimKapat:hover {
                color: #102A56;
            }
        """)

        dis = QVBoxLayout(self)
        dis.setContentsMargins(12, 12, 12, 12)
        dis.setSpacing(0)

        kart = QFrame(self)
        kart.setObjectName("bildirimKart")
        dis.addWidget(kart)

        golge = QGraphicsDropShadowEffect(self)
        golge.setBlurRadius(20)
        golge.setOffset(0, 3)
        golge.setColor(QColor(20, 43, 77, 45))
        kart.setGraphicsEffect(golge)

        ana = QVBoxLayout(kart)
        ana.setContentsMargins(16, 14, 16, 14)
        ana.setSpacing(12)

        baslik_satiri = QHBoxLayout()

        baslik = _ikonlu_baslik(
            "bell", MAVI, f"Bildirimler ({toplam})",
            "color: #102A56; font-size: 16px; font-weight: 800;"
        )
        baslik_satiri.addWidget(baslik)
        baslik_satiri.addStretch()

        kapat = QPushButton()
        kapat.setIcon(cizgi_ikonu("close", "#6B7FA8", 14))
        kapat.setIconSize(QSize(14, 14))
        kapat.setObjectName("bildirimKapat")
        kapat.setFixedWidth(28)
        kapat.setCursor(Qt.PointingHandCursor)
        kapat.clicked.connect(self.close)
        baslik_satiri.addWidget(kapat)

        ana.addLayout(baslik_satiri)

        aciklama = QLabel(f"{toplam} bildirim işlem bekliyor" if toplam
                         else "Bekleyen bildirim bulunmuyor")
        aciklama.setStyleSheet(
            "color: #6B7FA8; font-size: 12px;"
        )
        ana.addWidget(aciklama)

        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        kaydirma.setFrameShape(QFrame.NoFrame)

        icerik = QWidget()
        liste = QVBoxLayout(icerik)
        liste.setSizeConstraint(QLayout.SetMinAndMaxSize)
        liste.setContentsMargins(0, 2, 4, 2)
        liste.setSpacing(8)

        gruplar = OrderedDict()

        for grup, metin, hedef in bildirimler:
            gruplar.setdefault(grup, []).append((metin, hedef))

        satir_sayisi = 0

        for grup, satirlar in gruplar.items():
            if grup == "Danışma Masası":
                satirlar = self._ogrenci_bildirimlerini_grupla(satirlar)

            baslik_metni, grup_ikonu, grup_rengi = grup_basligi(grup)

            grup_baslik = _ikonlu_baslik(
                grup_ikonu, GRI, baslik_metni,
                "color: #5072A6; font-size: 11px; font-weight: 800; padding: 8px 0 4px 0;"
            )
            liste.addWidget(grup_baslik)

            for metin, hedef in satirlar:
                temiz, ikon_adi, ikon_rengi = bildirim_ikonu(grup, metin)
                buton = QPushButton(f"{temiz}   →")
                buton.setIcon(cizgi_ikonu(ikon_adi, ikon_rengi))
                buton.setIconSize(ikon_boyutu())
                buton.setObjectName("bildirimSatiri")
                buton.setMinimumHeight(45)
                buton.setToolTip(metin)
                buton.setCursor(Qt.PointingHandCursor)

                buton.clicked.connect(
                    lambda _=False, h=hedef: self._git(h)
                )

                liste.addWidget(buton)
                satir_sayisi += 1

        if not bildirimler:
            bos = _ikonlu_baslik(
                "circle-check", YESIL, "Bekleyen bildirim yok.",
                "color: #16803C; font-size: 13px;"
            )
            bos.layout().setContentsMargins(14, 14, 14, 14)
            liste.addWidget(bos)

        if hata:
            uyari = _ikonlu_baslik(
                "warning", AMBER, "Bazı bildirimler yüklenemedi.",
                "color: #B45309; font-size: 12px;"
            )
            uyari.layout().setContentsMargins(10, 10, 10, 10)
            liste.addWidget(uyari)

        kaydirma.setWidget(icerik)

        liste.activate()
        icerik.adjustSize()

        icerik_yuksekligi = icerik.sizeHint().height()

        # Az bildirimde kompakt, çok bildirimde kaydırılabilir.
        kaydirma.setFixedHeight(
            min(340, max(50, icerik_yuksekligi + 6))
        )

        ana.addWidget(kaydirma)

        dis.activate()
        self.adjustSize()

    @staticmethod
    def _ogrenci_bildirimlerini_grupla(satirlar):
        """Ayni ogrencinin bekleyen gorevlerini tek satirda toplar."""

        gruplar = OrderedDict()
        digerleri = []

        for metin, hedef in satirlar:
            temiz, _ = emojisiz(metin)
            if " — Görev onayı bekliyor" in temiz:
                ad = temiz.split(
                    " — Görev onayı bekliyor", 1
                )[0]

                anahtar = (ad, hedef)
                gruplar[anahtar] = gruplar.get(anahtar, 0) + 1
            else:
                digerleri.append((metin, hedef))

        sonuc = []

        for (ad, hedef), adet in gruplar.items():
            if adet == 1:
                metin = f"{ad} — Görev onayı bekliyor"
            else:
                metin = f"{ad} — {adet} görev onay bekliyor"

            sonuc.append((metin, hedef))

        return sonuc + digerleri

    def _git(self, hedef):
        self.close()
        self._sayfa_ac(hedef)
