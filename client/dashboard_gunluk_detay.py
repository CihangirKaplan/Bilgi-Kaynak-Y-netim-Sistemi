"""Ana Kontrol Paneli günlük özet ayrıntı penceresi."""

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
)

from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    api_hata_mesaji,
)


class GunlukDetayPenceresi(QDialog):
    def __init__(self, api_url, token, tur, gun=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TKYS - Günlük Kayıt Ayrıntıları")
        self.resize(880, 530)
        self.setMinimumSize(650, 360)

        self.setStyleSheet("""
            QDialog { background: #FFFFFF; }
            QLabel { color: #0A1F5C; }
            QTableWidget {
                border: 1px solid #DBE6F4;
                background: #FFFFFF;
                color: #0F2552;
                gridline-color: #E7EEF8;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #F3F7FF;
                color: #6B7FA8;
                padding: 10px;
                font-weight: 800;
                border: none;
            }
            QPushButton {
                background: #E9F2FE;
                color: #185D9E;
                border: 1px solid #CDDEF4;
                border-radius: 8px;
                padding: 8px 17px;
                font-weight: 700;
            }
        """)

        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(22, 20, 22, 20)
        duzen.setSpacing(13)

        self.baslik = QLabel("Kayıt Ayrıntıları")
        self.baslik.setStyleSheet(
            "font-size: 18px; font-weight: 800;"
        )
        duzen.addWidget(self.baslik)

        self.aciklama = QLabel("Kayıtlar yükleniyor...")
        self.aciklama.setStyleSheet(
            "color: #6B7FA8; font-size: 12px;"
        )
        duzen.addWidget(self.aciklama)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(4)
        self.tablo.setHorizontalHeaderLabels(
            ["Kayıt No", "Bilgi", "Tarih / Saat", "Durum"]
        )
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        duzen.addWidget(self.tablo)

        alt = QHBoxLayout()
        self.bilgi = QLabel("")
        self.bilgi.setStyleSheet(
            "color: #7185A0; font-size: 12px;"
        )
        alt.addWidget(self.bilgi)
        alt.addStretch()

        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        alt.addWidget(kapat)
        duzen.addLayout(alt)

        try:
            parametreler = {"tur": tur}
            if gun:
                parametreler["gun"] = gun

            yanit = oturum_kontrollu_istek(
                "GET",
                f"{api_url.rstrip('/')}"
                "/api/yonetim-raporlari/gunluk-detay",
                headers={"Authorization": f"Bearer {token}"},
                params=parametreler,
                timeout=15,
            )

            if yanit.status_code != 200:
                self.aciklama.setText(
                    api_hata_mesaji(yanit=yanit)
                )
                self.tablo.hide()
                return

            veri = yanit.json()
            self.baslik.setText(veri["baslik"])
            self.aciklama.setText(
                f"Kapsam: {veri['kapsam']} · "
                f"Rapor tarihi: {veri['gun']}"
            )

            satirlar = veri["satirlar"]
            self.tablo.setHorizontalHeaderLabels(
                veri["sutunlar"]
            )
            self.tablo.setRowCount(len(satirlar))

            for i, satir in enumerate(satirlar):
                for j, deger in enumerate(satir):
                    oge = QTableWidgetItem(str(deger))
                    self.tablo.setItem(i, j, oge)

            if not satirlar:
                self.bilgi.setText(
                    "Bu kapsamda kayıt bulunmuyor."
                )
            elif len(satirlar) >= veri["sinir"]:
                self.bilgi.setText(
                    f"İlk {veri['sinir']} kayıt gösteriliyor."
                )
            else:
                self.bilgi.setText(
                    f"{len(satirlar)} kayıt gösteriliyor."
                )

        except requests.RequestException as hata:
            self.aciklama.setText(
                api_hata_mesaji(hata=hata)
            )
            self.tablo.hide()
        except (KeyError, ValueError, TypeError):
            self.aciklama.setText(
                "Ayrıntı verileri beklenen biçimde alınamadı."
            )
            self.tablo.hide()
