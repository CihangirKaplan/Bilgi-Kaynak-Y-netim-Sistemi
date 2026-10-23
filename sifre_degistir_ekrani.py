
import requests

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox
)

API_URL = "http://127.0.0.1:8000"


class SifreDegistirEkrani(QWidget):
    sifre_degistirildi = Signal()
    iptal_edildi = Signal()

    def __init__(self, token):
        super().__init__()

        self.token = token
        self.setWindowTitle("TKYS - İlk Giriş Şifre Değiştirme")
        self.setFixedSize(480, 490)

        self.setStyleSheet("""
            QWidget {
                background-color: #EAF0FA;
                font-family: Arial;
            }
            QFrame {
                background-color: white;
                border-radius: 18px;
            }
            QLabel {
                color: #0A1F5C;
                background: transparent;
            }
            QLineEdit {
                background: #F3F7FF;
                color: #0A1F5C;
                border: 1px solid #D5E2FB;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton {
                background: #1D4ED8;
                color: white;
                border-radius: 8px;
                padding: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1E40AF;
            }
            QCheckBox {
                background: transparent;
                color: #0A1F5C;
            }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(30, 30, 30, 30)

        kart = QFrame()
        layout = QVBoxLayout(kart)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)

        baslik = QLabel("İlk Giriş - Şifre Değiştirme")
        baslik.setStyleSheet("font-size: 20px; font-weight: bold;")
        baslik.setAlignment(Qt.AlignCenter)
        layout.addWidget(baslik)

        aciklama = QLabel(
            "Güvenliğiniz için geçici şifrenizi değiştirmeniz gerekiyor."
        )
        aciklama.setWordWrap(True)
        aciklama.setAlignment(Qt.AlignCenter)
        layout.addWidget(aciklama)

        self.eski_sifre = QLineEdit()
        self.eski_sifre.setPlaceholderText("Mevcut geçici şifre")
        self.eski_sifre.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.eski_sifre)

        self.yeni_sifre = QLineEdit()
        self.yeni_sifre.setPlaceholderText("Yeni şifre (en az 8 karakter)")
        self.yeni_sifre.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.yeni_sifre)

        self.yeni_sifre_tekrar = QLineEdit()
        self.yeni_sifre_tekrar.setPlaceholderText("Yeni şifre tekrar")
        self.yeni_sifre_tekrar.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.yeni_sifre_tekrar)

        self.goster = QCheckBox("Şifreleri göster")
        self.goster.toggled.connect(self.sifreleri_goster)
        layout.addWidget(self.goster)

        self.hata_lbl = QLabel("")
        self.hata_lbl.setWordWrap(True)
        self.hata_lbl.setStyleSheet("color: #B91C1C;")
        layout.addWidget(self.hata_lbl)

        self.kaydet_btn = QPushButton("ŞİFREMİ DEĞİŞTİR")
        self.kaydet_btn.clicked.connect(self.sifre_degistir)
        layout.addWidget(self.kaydet_btn)

        ana_layout.addWidget(kart)
        self.eski_sifre.setFocus()

    def sifreleri_goster(self, goster):
        mod = QLineEdit.Normal if goster else QLineEdit.Password

        self.eski_sifre.setEchoMode(mod)
        self.yeni_sifre.setEchoMode(mod)
        self.yeni_sifre_tekrar.setEchoMode(mod)

    def sifre_degistir(self):
        eski = self.eski_sifre.text().strip()
        yeni = self.yeni_sifre.text().strip()
        tekrar = self.yeni_sifre_tekrar.text().strip()

        if not eski or not yeni or not tekrar:
            self.hata_lbl.setText("Tüm alanları doldurmalısınız.")
            return

        if yeni != tekrar:
            self.hata_lbl.setText("Yeni şifreler eşleşmiyor.")
            return

        if len(yeni) < 8:
            self.hata_lbl.setText("Yeni şifre en az 8 karakter olmalıdır.")
            return

        self.kaydet_btn.setEnabled(False)

        try:
            yanit = requests.post(
                f"{API_URL}/api/sifre-degistir",
                headers={
                    "Authorization": f"Bearer {self.token}"
                },
                json={
                    "eski_parola": eski,
                    "yeni_parola": yeni,
                    "yeni_parola_tekrar": tekrar
                },
                timeout=10
            )

            if yanit.status_code == 200:
                self.eski_sifre.clear()
                self.yeni_sifre.clear()
                self.yeni_sifre_tekrar.clear()
                self.sifre_degistirildi.emit()
            else:
                try:
                    detay = yanit.json().get("detail", "Şifre değiştirilemedi.")
                    if not isinstance(detay, str):
                        detay = "Şifre değiştirilemedi."
                except ValueError:
                    detay = "Sunucudan geçersiz yanıt alındı."

                self.hata_lbl.setText(detay)

        except requests.exceptions.RequestException:
            self.hata_lbl.setText("Sunucuya bağlanılamadı.")
        finally:
            self.kaydet_btn.setEnabled(True)

    def closeEvent(self, event):
        self.iptal_edildi.emit()
        super().closeEvent(event)

