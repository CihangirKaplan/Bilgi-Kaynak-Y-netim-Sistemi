import turkce_mesaj_kutusu as tmk

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
from parola_kurallari import kural_durumlari, tum_kurallar_saglandi_mi, guc_hesapla
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QCheckBox, QMessageBox, QHBoxLayout, QSizePolicy
)

API_URL = os.getenv("TKYS_API_URL", "http://127.0.0.1:8000")


class SifreDegistirEkrani(QWidget):
    sifre_degistirildi = Signal()
    iptal_edildi = Signal()

    def __init__(self, token, ilk_giris=True):
        super().__init__()

        self.ilk_giris = ilk_giris
        self.token = token
        self._oturum_kapatiliyor = False
        self._sifre_basariyla_degisti = False
        self._token_bitis_zamani = self._token_bitisini_oku()
        self.setWindowTitle(
            "TKYS - İlk Giriş Şifre Değiştirme"
            if ilk_giris else "TKYS - Şifremi Değiştir"
        )



        self.setFixedSize(475, 535)
        self.setObjectName("sifrePencere")

        self.setStyleSheet("""
            QWidget#sifrePencere {
                background: #F7FAFD;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #243653;
            }
            QLineEdit {
                background: #FFFFFF;
                border: 1px solid #CBD9EC;
                border-radius: 8px;
                color: #243653;
                padding: 0px 13px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #2682FF;
            }
            QFrame#parolaBilgi {
                background: #FFFFFF;
                border: 1px solid #DCE6F4;
                border-radius: 9px;
            }
            QCheckBox {
                background: transparent;
                color: #405572;
                font-size: 12px;
                spacing: 8px;
            }
            QPushButton {
                border-radius: 8px;
                font-size: 13px;
                font-weight: 700;
                min-height: 39px;
            }
            QPushButton#vazgec {
                background: #FFFFFF;
                border: 1px solid #CBD9EC;
                color: #405572;
            }
            QPushButton#vazgec:hover {
                background: #EEF4FC;
                border: 1px solid #89B6FA;
            }
            QPushButton#kaydetSifre {
                background: #0866F5;
                border: 1px solid #0866F5;
                color: #FFFFFF;
            }
            QPushButton#kaydetSifre:hover {
                background: #0054D6;
            }
            QPushButton#kaydetSifre:disabled {
                background: #B7C8E1;
                border: 1px solid #B7C8E1;
                color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(23, 19, 23, 19)
        layout.setSpacing(7)

        baslik = QLabel(
            "İlk Giriş - Şifre Değiştirme"
            if self.ilk_giris else "Şifremi Değiştir"
        )
        baslik.setStyleSheet(
            "font-size: 17px; font-weight: 800; color: #142E60;"
        )
        layout.addWidget(baslik)

        aciklama = QLabel(
            "Devam etmek için geçici şifrenizi değiştirin."
            if self.ilk_giris
            else "Hesap güvenliğiniz için şifrenizi güncelleyin."
        )
        aciklama.setStyleSheet(
            "font-size: 12px; color: #7185A5;"
        )
        layout.addWidget(aciklama)
        layout.addSpacing(10)

        def etiket(metin):
            yazi = QLabel(metin)
            yazi.setStyleSheet(
                "font-size: 12px; font-weight: 700; color: #243653;"
            )
            return yazi

        layout.addWidget(etiket("Mevcut Şifre"))
        self.eski_sifre = QLineEdit()
        self.eski_sifre.setPlaceholderText(
            "Geçici şifrenizi girin"
            if self.ilk_giris else "Mevcut şifrenizi girin"
        )
        self.eski_sifre.setEchoMode(QLineEdit.Password)
        self.eski_sifre.setFixedHeight(40)
        layout.addWidget(self.eski_sifre)

        layout.addSpacing(5)

        layout.addWidget(etiket("Yeni Şifre"))
        self.yeni_sifre = QLineEdit()
        self.yeni_sifre.setPlaceholderText("Yeni şifrenizi girin")
        self.yeni_sifre.setEchoMode(QLineEdit.Password)
        self.yeni_sifre.setFixedHeight(40)
        layout.addWidget(self.yeni_sifre)

        layout.addSpacing(5)

        layout.addWidget(etiket("Yeni Şifre Tekrar"))
        self.yeni_sifre_tekrar = QLineEdit()
        self.yeni_sifre_tekrar.setPlaceholderText(
            "Yeni şifrenizi tekrar girin"
        )
        self.yeni_sifre_tekrar.setEchoMode(QLineEdit.Password)
        self.yeni_sifre_tekrar.setFixedHeight(40)
        layout.addWidget(self.yeni_sifre_tekrar)

        layout.addSpacing(12)

        bilgi_kutusu = QFrame()
        bilgi_kutusu.setObjectName("parolaBilgi")
        bilgi_layout = QVBoxLayout(bilgi_kutusu)
        bilgi_layout.setContentsMargins(12, 7, 12, 7)
        bilgi_layout.setSpacing(2)

        bilgi_baslik = QLabel("Parola gereksinimleri")
        bilgi_baslik.setStyleSheet(
            "font-size: 12px; font-weight: 700; color: #243653;"
        )
        bilgi_baslik.setFixedHeight(20)
        bilgi_layout.addWidget(bilgi_baslik)

        self.kural_satirlari = []
        for _ in range(3):
            satir = QLabel("")
            satir.setFixedHeight(19)
            satir.setStyleSheet(
                "font-size: 11px; color: #7085A3;"
            )
            bilgi_layout.addWidget(satir)
            self.kural_satirlari.append(satir)

        self.guc_lbl = QLabel("")
        self.guc_lbl.setFixedHeight(19)
        bilgi_layout.addWidget(self.guc_lbl)

        # Eski QLabel referansı korunuyor;
        # görselde yalnızca ayrı kural satırları kullanılıyor.
        self.kural_lbl = QLabel("")
        self.kural_lbl.hide()

        bilgi_layout.setContentsMargins(12, 7, 12, 7)
        bilgi_layout.setSpacing(2)
        self.parola_bilgi_kutusu = bilgi_kutusu
        bilgi_kutusu.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Fixed
        )
        bilgi_kutusu.setMinimumHeight(0)
        bilgi_kutusu.setMaximumHeight(167)

        layout.addWidget(bilgi_kutusu)
        layout.addSpacing(10)

        self.goster = QCheckBox("Şifreleri göster")

        tik_resmi = (
            Path(__file__).resolve().parent
            / "assets/ui/checkbox_checked.png"
        )

        self.goster.setStyleSheet(f"""
            QCheckBox {{
                color: #516B91;
                font-size: 12px;
                spacing: 9px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid #96B0D1;
                border-radius: 5px;
                background: #FFFFFF;
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid #3578D4;
                background: #F0F6FF;
            }}
            QCheckBox::indicator:checked {{
                background: #1554B7;
                border: 1px solid #1554B7;
                image: url("{tik_resmi.as_posix()}");
            }}
        """)

        self.goster.toggled.connect(self.sifreleri_goster)
        layout.addWidget(self.goster)

        self.hata_lbl = QLabel("")
        self.hata_lbl.setWordWrap(True)
        self.hata_lbl.setStyleSheet(
            "font-size: 11px; color: #DC2626;"
        )
        layout.addWidget(self.hata_lbl)


        butonlar = QHBoxLayout()
        butonlar.setSpacing(10)

        self.btn_vazgec = QPushButton("Vazgeç")
        self.btn_vazgec.setObjectName("vazgec")
        self.btn_vazgec.clicked.connect(self.close)

        self.kaydet_btn = QPushButton("Şifreyi Güncelle")
        self.kaydet_btn.setObjectName("kaydetSifre")
        self.kaydet_btn.clicked.connect(self.sifre_degistir)

        butonlar.addWidget(self.btn_vazgec)
        butonlar.addWidget(self.kaydet_btn)
        layout.addLayout(butonlar)

        self.eski_sifre.setFocus()

        for alan in (self.eski_sifre, self.yeni_sifre, self.yeni_sifre_tekrar):
            alan.textChanged.connect(self._kurallari_guncelle)
        self._kurallari_guncelle()

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

        tmk.bilgi(
            self,
            "Oturum Sona Erdi",
            mesaj + "Uygulamayı kullanmaya devam etmek için "
            "lütfen yeniden giriş yapın."
        )

        self.close()

    def _kurallari_guncelle(self, *_):
        """Kural listesini ve güç göstergesini yazdıkça günceller; düğme yalnızca tüm kurallar sağlanınca açılır."""
        eski = self.eski_sifre.text().strip()
        yeni = self.yeni_sifre.text().strip()
        tekrar = self.yeni_sifre_tekrar.text().strip()

        kurallar = [
            (metin, saglandi)
            for metin, saglandi in kural_durumlari(yeni, tekrar, eski)
            if "72 bayt" not in metin
        ]

        if len(kurallar) != 3:
            raise ValueError(
                f"Beklenen 3 parola kuralı yerine {len(kurallar)} bulundu."
            )

        for satir, (metin, saglandi) in zip(
            self.kural_satirlari, kurallar
        ):
            satir.setText(
                ("✔  " if saglandi else "○  ") + metin
            )
            renk = "#15803D" if saglandi else "#7085A3"
            satir.setStyleSheet(
                f"font-size: 11px; color: {renk};"
            )

        self.kural_lbl.setText(
            "\n".join(metin for metin, _ in kurallar)
        )

        puan, etiket = guc_hesapla(yeni)
        renkler = {0: "#B91C1C", 1: "#B45309", 2: "#1D4ED8", 3: "#15803D"}
        self.guc_lbl.setText(f"Şifre gücü: {etiket}" if etiket else "")
        self.guc_lbl.setVisible(bool(etiket))
        self.guc_lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {renkler[puan]};")

        self._kaydet_butonunu_ayarla()

    def _kaydet_butonunu_ayarla(self):
        hazir = tum_kurallar_saglandi_mi(
            self.yeni_sifre.text().strip(), self.yeni_sifre_tekrar.text().strip(), self.eski_sifre.text().strip()
        ) and bool(self.eski_sifre.text().strip())
        self.kaydet_btn.setEnabled(not self._oturum_kapatiliyor)

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
            self.hata_lbl.setText(
                "⚠ Lütfen tüm şifre alanlarını doldurun."
            )
            return

        if yeni != tekrar:
            self.hata_lbl.setText(
                "⚠ Yeni şifreler birbiriyle eşleşmiyor."
            )
            return

        if eski == yeni:
            self.hata_lbl.setText(
                "⚠ Yeni şifreniz mevcut şifrenizden farklı olmalıdır."
            )
            return

        if len(yeni) < 8:
            self.hata_lbl.setText(
                "⚠ Yeni şifreniz en az 8 karakter olmalıdır."
            )
            return

        if len(yeni.encode("utf-8")) > 72:
            self.hata_lbl.setText(
                "⚠ Yeni şifreniz en fazla 72 bayt olabilir."
            )
            return

        if not tum_kurallar_saglandi_mi(yeni, tekrar, eski):
            self.hata_lbl.setText(
                "⚠ Yeni şifreniz parola gereksinimlerini karşılamıyor."
            )
            return

        self.hata_lbl.clear()

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

                self.hata_lbl.setText("⚠ " + detay)

        except requests.exceptions.RequestException:
            self.hata_lbl.setText("Sunucuya bağlanılamadı.")
        finally:
            if not self._oturum_kapatiliyor:
                self._kaydet_butonunu_ayarla()

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

