from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QPushButton, QMessageBox,
                               QFrame, QLabel)
import requests
from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)

DANISMA_OGRENCISI_BILGISI = (
    "ℹ  Danışma Masası öğrencileri bu pencereden eklenemez. Danışma Masası görevleri için öğrencinin giriş hesabı "
    "gerekir; öğrenciyi “Kullanıcı & Personel” sayfasından “Danışma Öğrencisi” rolüyle oluşturun."
)


class OgrenciEkleDialog(QDialog):
    def __init__(self, api_url, token, parent=None, kullanici_sayfasi_acilabilir=False):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.sayfa_istendi = False      # "Kullanıcı & Personel sayfasına git" düğmesine basıldı mı (pencereyi açan ekran bakar)
        self.setWindowTitle("Yeni Öğrenci Ekle")
        self.setMinimumWidth(400)

        # Bembeyaz ve şık form tasarımı
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; }
            QLineEdit, QComboBox, QSpinBox {
                background-color: white;
                color: #2C3E50;
                padding: 6px;
                border: 1px solid #BDC3C7;
                border-radius: 4px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #3498DB;
                background-color: #FAFAFA;
            }
            QPushButton { background-color: #27AE60; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #2ECC71; }
        """)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Form Elemanları ve Kısıtlamalar
        self.le_ad_soyad = QLineEdit()
        self.le_ad_soyad.setMaxLength(100)       # veritabanı: ogrenciler.ad_soyad VARCHAR(100)

        self.le_ogrenci_no = QLineEdit()
        self.le_ogrenci_no.setMaxLength(15)
        self.le_ogrenci_no.setPlaceholderText("Öğrenci numarasını giriniz")

        self.cb_tur = QComboBox()
        self.cb_tur.addItem("Gönüllü Öğrenci", "GONULLU")
        self.cb_tur.addItem("Asistan Öğrenci", "ASISTAN")

        self.le_telefon = QLineEdit()
        self.le_telefon.setMaxLength(11)
        self.le_telefon.setPlaceholderText("Örn: 05551234567")

        self.le_bolum = QLineEdit()
        self.le_bolum.setMaxLength(100)          # veritabanı: ogrenciler.bolum VARCHAR(100)
        self.le_sinif = QLineEdit()
        self.le_sinif.setMaxLength(20)           # veritabanı: ogrenciler.sinif VARCHAR(20)

        # Elemanları Forma Ekle
        form_layout.addRow("Ad Soyad (*):", self.le_ad_soyad)
        form_layout.addRow("Öğrenci No (*):", self.le_ogrenci_no)
        form_layout.addRow("Öğrenci Türü (*):", self.cb_tur)
        form_layout.addRow("Telefon:", self.le_telefon)
        form_layout.addRow("Bölüm:", self.le_bolum)
        form_layout.addRow("Sınıf:", self.le_sinif)

        layout.addLayout(form_layout)

        # Danışma Masası öğrencisi giriş hesabı gerektirdiği için buradan eklenmez; kullanıcıyı doğru sayfaya yönlendiririz.
        self.bilgi_kutusu = QFrame()
        self.bilgi_kutusu.setStyleSheet(
            "QFrame { background: #FEF3C7; border: 1px solid #FDE68A; border-radius: 8px; }"
            "QLabel { background: transparent; color: #854D0E; font-size: 12px; font-weight: 600; border: none; }")
        bilgi_duzeni = QVBoxLayout(self.bilgi_kutusu)
        self.lbl_bilgi = QLabel(DANISMA_OGRENCISI_BILGISI)
        self.lbl_bilgi.setWordWrap(True)
        bilgi_duzeni.addWidget(self.lbl_bilgi)
        self.btn_kullanici_sayfasi = QPushButton("👥  Kullanıcı && Personel sayfasına git")   # düğmede tek & kısayol işaretidir, && yazılır
        self.btn_kullanici_sayfasi.setCursor(Qt.PointingHandCursor)
        self.btn_kullanici_sayfasi.setStyleSheet(
            "QPushButton { background-color: #F59E0B; color: white; font-weight: bold; padding: 8px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #D97706; }")
        self.btn_kullanici_sayfasi.clicked.connect(self._kullanici_sayfasina_git)
        self.btn_kullanici_sayfasi.setVisible(bool(kullanici_sayfasi_acilabilir))    # sayfaya yetkisi yoksa düğme gösterilmez
        bilgi_duzeni.addWidget(self.btn_kullanici_sayfasi)
        layout.addWidget(self.bilgi_kutusu)

        self.btn_kaydet = QPushButton("Öğrenciyi Kaydet")
        self.btn_kaydet.clicked.connect(self.kaydet_tiklandi)
        layout.addWidget(self.btn_kaydet)

    def _kullanici_sayfasina_git(self):
        """Pencereyi kapatır; sayfayı pencereyi açan ekran açar (sayfa_istendi işaretine bakarak)."""
        self.sayfa_istendi = True
        self.reject()

    def kaydet_tiklandi(self):
        ad_soyad = self.le_ad_soyad.text().strip()
        ogrenci_no = self.le_ogrenci_no.text().strip()
        telefon = self.le_telefon.text().strip()

        # 1. Boş Alan Kontrolü
        if not ad_soyad or not ogrenci_no:
            QMessageBox.warning(self, "Uyarı", "Yıldızlı (*) alanların doldurulması zorunludur.")
            return

        # 2. Öğrenci Numarası Kontrolü (Sadece Rakam Olmalı)
        if not ogrenci_no.isdigit():
            QMessageBox.warning(self, "Uyarı", "Öğrenci numarası sadece rakamlardan oluşmalıdır. Harf giremezsiniz!")
            return

        # 3. Telefon Kontrolü (Eğer doldurulduysa kurallara uymak zorunda)
        if telefon:
            if not telefon.isdigit():
                QMessageBox.warning(self, "Uyarı", "Telefon numarasına harf veya boşluk giremezsiniz. Sadece rakam olmalıdır!")
                return
            if len(telefon) != 11:
                QMessageBox.warning(self, "Uyarı", "Telefon numarası tam 11 haneli olmalıdır.\n(Örn: 05551234567)")
                return
            if not telefon.startswith("0"):
                QMessageBox.warning(self, "Uyarı", "Telefon numarası '0' ile başlamalıdır.")
                return

        # Her şey kurallara uygunsa veritabanı için paketi hazırla
        payload = {
            "ad_soyad": ad_soyad,
            "ogrenci_numarasi": ogrenci_no,
            "telefon": telefon,
            "tur": self.cb_tur.currentData(),
            "bolum": self.le_bolum.text().strip(),
            "sinif": self.le_sinif.text().strip()
        }

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            res = oturum_kontrollu_istek("POST", f"{self.api_url}/api/ogrenci-ekle", json=payload, headers=headers)
            if oturum_hatasi_mi(res):
                return

            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Öğrenci sisteme başarıyla eklendi!")
                self.accept()
            elif res.status_code == 400:
                QMessageBox.warning(self, "Hata", res.json().get("detail", "Bu öğrenci numarası sistemde zaten var."))
            else:
                QMessageBox.critical(self, "Hata", "Öğrenci kaydedilemedi.")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")