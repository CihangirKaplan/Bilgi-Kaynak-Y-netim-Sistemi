
import base64
import json
import os
import time
import requests
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
    oturum_olaylari,
)
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QMessageBox
)

API_URL = os.getenv("TKYS_API_URL", "http://127.0.0.1:8000")


class SifreDegistirEkrani(QWidget):
    sifre_degistirildi = Signal()
    iptal_edildi = Signal()

    def __init__(self, token):
        super().__init__()

        self.token = token
        self._oturum_kapatiliyor = False
        self._sifre_basariyla_degisti = False
        self._token_bitis_zamani = self._token_bitisini_oku()
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
                font-size: 12px;
                spacing: 10px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #7BA6F8;
                border-radius: 0px;
                background-color: white;
            }

            QCheckBox::indicator:checked {
                background-color: #2563EB;
                border: 2px solid #2563EB;
            }

            QCheckBox::indicator:hover {
                border: 2px solid #1D4ED8;
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
        tik_resmi = (
            Path(__file__).resolve().parent
            / "assets/ui/checkbox_checked.png"
        )

        self.goster.setStyleSheet(f"""
            QCheckBox::indicator:checked {{
                width: 16px;
                height: 16px;
                border: none;
                border-radius: 0px;
                background: transparent;
                image: url("{tik_resmi.as_posix()}");
            }}
        """)
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

        self._oturum_zamanlayici = QTimer(self)
        self._oturum_zamanlayici.setInterval(1000)
        self._oturum_zamanlayici.timeout.connect(
            self._oturum_suresini_kontrol_et
        )

        oturum_olaylari.token_reddedildi.connect(
            self._api_token_reddedildi
        )

        self._oturum_zamanlayici.start()
        QTimer.singleShot(
            0, self._oturum_suresini_kontrol_et
        )

    def _token_bitisini_oku(self):
        """JWT bitis zamanini istemci zamanlayicisi icin okur."""
        try:
            parca = self.token.split(".")[1]
            parca += "=" * (-len(parca) % 4)

            veri = json.loads(
                base64.urlsafe_b64decode(parca)
            )
            return int(veri["exp"])

        except (ValueError, TypeError, KeyError, IndexError):
            return 0

    def _oturum_suresini_kontrol_et(self):
        if self._oturum_kapatiliyor:
            return

        if time.time() >= self._token_bitis_zamani:
            self._oturum_sonlandir()

    def _api_token_reddedildi(self, token, neden):
        if token != self.token:
            return

        self._oturum_sonlandir(neden)

    def _oturum_sonlandir(self, neden="sure_doldu"):
        if (
            self._oturum_kapatiliyor
            or self._sifre_basariyla_degisti
        ):
            return

        self._oturum_nedeni = neden
        self._oturum_kapatiliyor = True
        self._oturum_zamanlayici.stop()
        self.kaydet_btn.setEnabled(False)

        QTimer.singleShot(0, self._oturum_uyarisi)

    def _oturum_uyarisi(self):
        if not self.isVisible():
            return

        mesaj = (
            "Oturum süreniz sona ermiştir.\n\n"
            if getattr(self, "_oturum_nedeni", "sure_doldu") == "sure_doldu"
            else "Oturumunuz geçersiz hâle gelmiştir.\n\n"
        )

        QMessageBox.information(
            self,
            "Oturum Sona Erdi",
            mesaj + "Uygulamayı kullanmaya devam etmek için "
            "lütfen yeniden giriş yapın.",
            QMessageBox.StandardButton.Ok
        )

        self.close()

    def sifreleri_goster(self, goster):
        mod = QLineEdit.Normal if goster else QLineEdit.Password

        self.eski_sifre.setEchoMode(mod)
        self.yeni_sifre.setEchoMode(mod)
        self.yeni_sifre_tekrar.setEchoMode(mod)

    def sifre_degistir(self):
        if self._oturum_kapatiliyor:
            return

        if time.time() >= self._token_bitis_zamani:
            self._oturum_sonlandir()
            return

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
            yanit = oturum_kontrollu_istek("POST",
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
            if oturum_hatasi_mi(yanit):
                return

            if yanit.status_code == 200:
                self._sifre_basariyla_degisti = True
                self._oturum_zamanlayici.stop()
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
            if not self._oturum_kapatiliyor:
                self.kaydet_btn.setEnabled(True)

    def closeEvent(self, event):
        self._oturum_zamanlayici.stop()

        try:
            oturum_olaylari.token_reddedildi.disconnect(
                self._api_token_reddedildi
            )
        except (TypeError, RuntimeError):
            pass

        if not self._sifre_basariyla_degisti:
            self.iptal_edildi.emit()

        super().closeEvent(event)

