from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QPushButton, QMessageBox
import requests

class OgrenciEkleDialog(QDialog):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
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
        
        self.le_ogrenci_no = QLineEdit()
        self.le_ogrenci_no.setMaxLength(15)
        self.le_ogrenci_no.setPlaceholderText("Örn: 23100011036")
        
        self.cb_tur = QComboBox()
        self.cb_tur.addItem("Gönüllü Öğrenci", "GONULLU")
        self.cb_tur.addItem("Danışma Masası Öğrencisi", "DANISMA_MASASI")
        self.cb_tur.addItem("Asistan Öğrenci", "ASISTAN") # Asistan seçeneği eklendi

        self.le_telefon = QLineEdit()
        self.le_telefon.setMaxLength(11)
        self.le_telefon.setPlaceholderText("Örn: 05551234567")
        
        self.le_bolum = QLineEdit()
        self.le_sinif = QLineEdit()

        # Elemanları Forma Ekle
        form_layout.addRow("Ad Soyad (*):", self.le_ad_soyad)
        form_layout.addRow("Öğrenci No (*):", self.le_ogrenci_no)
        form_layout.addRow("Öğrenci Türü (*):", self.cb_tur)
        form_layout.addRow("Telefon:", self.le_telefon)
        form_layout.addRow("Bölüm:", self.le_bolum)
        form_layout.addRow("Sınıf:", self.le_sinif)

        layout.addLayout(form_layout)

        self.btn_kaydet = QPushButton("Öğrenciyi Kaydet")
        self.btn_kaydet.clicked.connect(self.kaydet_tiklandi)
        layout.addWidget(self.btn_kaydet)

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
            res = requests.post(f"{self.api_url}/api/ogrenci-ekle", json=payload, headers=headers)
            
            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Öğrenci sisteme başarıyla eklendi!")
                self.accept()
            elif res.status_code == 400:
                QMessageBox.warning(self, "Hata", res.json().get("detail", "Bu öğrenci numarası sistemde zaten var."))
            else:
                QMessageBox.critical(self, "Hata", "Öğrenci kaydedilemedi.")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")