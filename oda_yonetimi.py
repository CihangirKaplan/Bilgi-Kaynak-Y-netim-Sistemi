import sys
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, 
    QMessageBox, QApplication, QCheckBox, QLabel, QFrame
)
from PySide6.QtCore import Qt
from ui_components import StandartButon, StandartGirdi

# ======================================================================
#  ROOM-001: YENİ ODA EKLEME / DÜZENLEME FORMU
# ======================================================================
class OdaFormu(QWidget):
    def __init__(self, api_url, token, oda_id=None, eski_veriler=None):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.oda_id = oda_id
        self.eski_veriler = eski_veriler
        
        baslik = "Yeni Oda Ekle" if not self.oda_id else f"Oda Düzenle (ID: {self.oda_id})"
        self.setWindowTitle(f"ROOM-001 - {baslik}")
        self.resize(450, 300)
        self.setStyleSheet("background-color: #E8EDF2;") # main_window arka planına uyumlu gri/mavi ton
        
        self.init_ui()
        
        if self.oda_id and self.eski_veriler:
            self.eski_verileri_bas()

    def init_ui(self):
        # 1. Ana Layout
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(20, 20, 20, 20)
        
        # 2. Ana Kart (Beyaz Gövde)
        kart = QFrame()
        kart.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 12px;
                border: 1px solid #D0D7E5;
            }
        """)
        kart_layout = QVBoxLayout(kart)
        kart_layout.setContentsMargins(0, 0, 0, 0) # İçerik karta tam yapışsın (başlık için)
        kart_layout.setSpacing(0)
        
        # 3. Koyu Mavi Başlık (Header)
        ust_bar = QFrame()
        ust_bar.setStyleSheet("""
            QFrame {
                background-color: #0A1F5C;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        ust_layout = QHBoxLayout(ust_bar)
        ust_layout.setContentsMargins(20, 15, 20, 15)
        
        ikon_ve_baslik = "🏢 Yeni Oda Ekle" if not self.oda_id else "🏢 Odayı Düzenle"
        lbl_baslik = QLabel(ikon_ve_baslik)
        lbl_baslik.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        ust_layout.addWidget(lbl_baslik)
        kart_layout.addWidget(ust_bar)
        
        # 4. Form Alanı (İçerik)
        form_container = QWidget()
        form_container.setStyleSheet("background-color: transparent; border: none;")
        form_layout = QFormLayout(form_container)
        form_layout.setContentsMargins(25, 25, 25, 15)
        form_layout.setSpacing(15)

        lbl_stil = "color: #2C3E50; font-weight: bold; font-size: 13px; border: none;"

        # Oda Adı
        lbl_ad = QLabel("Oda Adı:")
        lbl_ad.setStyleSheet(lbl_stil)
        self.in_oda_adi = StandartGirdi("Örn: Terapi Odası 1")
        self.in_oda_adi.setMaxLength(50)
        form_layout.addRow(lbl_ad, self.in_oda_adi)

        # Kapasite
        lbl_kapasite = QLabel("Kapasite:")
        lbl_kapasite.setStyleSheet(lbl_stil)
        self.in_kapasite = StandartGirdi("Örn: 2")
        self.in_kapasite.setText("1")
        form_layout.addRow(lbl_kapasite, self.in_kapasite)
        
        # Checkbox
        self.chk_aktif = QCheckBox("Bu oda aktif olarak kullanılabilir.")
        self.chk_aktif.setChecked(True)
        self.chk_aktif.setStyleSheet("""
            QCheckBox {
                color: #2C3E50;
                font-size: 13px;
                font-weight: bold;
                border: none;
            }
        """)
        form_layout.addRow("", self.chk_aktif) # Label boş bırakıldı ki hiza korunsun
        
        kart_layout.addWidget(form_container)
        
        # 5. Alt Buton Alanı (Footer)
        buton_alani = QFrame()
        buton_alani.setStyleSheet("""
            QFrame {
                background-color: #F8F9FA;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                border-top: 1px solid #E9ECEF;
            }
        """)
        buton_layout = QHBoxLayout(buton_alani)
        buton_layout.setContentsMargins(20, 15, 20, 15)
        
        # İptal Butonu
        self.btn_iptal = StandartButon("İptal")
        self.btn_iptal.setStyleSheet("""
            QPushButton {
                background-color: #E2E8F0;
                color: #4A5568;
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #CBD5E0; }
        """)
        self.btn_iptal.clicked.connect(self.close)
        
        # Kaydet Butonu
        btn_metin = "Değişiklikleri Kaydet" if self.oda_id else "Odayı Sisteme Kaydet"
        self.btn_kaydet = StandartButon(btn_metin)
        self.btn_kaydet.setStyleSheet("""
            QPushButton {
                background-color: #1A56DB; /* BKYS Kurumsal Mavi */
                color: white;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #1545B0; }
        """)
        self.btn_kaydet.clicked.connect(self.odayi_kaydet)
        
        buton_layout.addStretch() # Butonları sağa yaslamak için
        buton_layout.addWidget(self.btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        
        kart_layout.addWidget(buton_alani)
        
        # Kartı ana ekrana ekle
        ana_layout.addWidget(kart)
        self.setLayout(ana_layout)

    def eski_verileri_bas(self):
        self.in_oda_adi.setText(self.eski_veriler.get("oda_adi", ""))
        self.in_kapasite.setText(str(self.eski_veriler.get("kapasite", 1)))
        self.chk_aktif.setChecked(self.eski_veriler.get("aktif_mi", True))

    def odayi_kaydet(self):
        oda_adi = self.in_oda_adi.text().strip()
        kapasite_str = self.in_kapasite.text().strip()
        
        if not oda_adi:
            QMessageBox.warning(self, "Eksik Veri", "Oda adı boş bırakılamaz!")
            return
            
        if not kapasite_str.isdigit() or int(kapasite_str) < 1:
            QMessageBox.warning(self, "Hatalı Veri", "Kapasite 1 veya daha büyük bir sayı olmalıdır!")
            return

        oda_verisi = {
            "oda_adi": oda_adi,
            "kapasite": int(kapasite_str),
            "aktif_mi": self.chk_aktif.isChecked()
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            if self.oda_id:
                cevap = requests.patch(f"{self.api_url}/api/odalar/{self.oda_id}", json=oda_verisi, headers=headers, timeout=5)
            else:
                cevap = requests.post(f"{self.api_url}/api/odalar", json=oda_verisi, headers=headers, timeout=5)

            if cevap.status_code in [200, 201]:
                QMessageBox.information(self, "Başarılı", "Oda bilgileri başarıyla kaydedildi!")
                self.close()
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Bu isimde bir oda zaten mevcut!")
            else:
                QMessageBox.warning(self, "Hata", f"İşlem başarısız (Kod: {cevap.status_code})")
                
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Zaman Aşımı", "Sunucuya bağlanılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
def odayi_kaydet(self):
        oda_adi = self.in_oda_adi.text().strip()
        kapasite_str = self.in_kapasite.text().strip()
        
        # 1. Frontend Validasyonları
        if not oda_adi:
            QMessageBox.warning(self, "Eksik Veri", "Oda adı boş bırakılamaz!")
            return
            
        if not kapasite_str.isdigit() or int(kapasite_str) < 1:
            QMessageBox.warning(self, "Hatalı Veri", "Kapasite 1 veya daha büyük bir sayı olmalıdır!")
            return

        # 2. Sunucuya Gönderilecek JSON Verisini Hazırla
        oda_verisi = {
            "oda_adi": oda_adi,
            "kapasite": int(kapasite_str),
            "aktif_mi": self.chk_aktif.isChecked()
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        
        # 3. Backend API'sine İstek At
        try:
            # Düzenleme mi yoksa yeni ekleme mi kontrolü
            if self.oda_id:
                # ODA DÜZENLEME (PATCH)
                cevap = requests.patch(f"{self.api_url}/api/odalar/{self.oda_id}", json=oda_verisi, headers=headers, timeout=5)
            else:
                # YENİ ODA EKLEME (POST)
                cevap = requests.post(f"{self.api_url}/api/odalar", json=oda_verisi, headers=headers, timeout=5)

            # 4. Sunucudan Gelen Cevabı İşle
            if cevap.status_code in [200, 201]:
                QMessageBox.information(self, "Başarılı", "Oda bilgileri başarıyla veritabanına kaydedildi!")
                self.close() # İşlem başarılıysa formu kapat
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Bu isimde bir oda zaten mevcut!")
            else:
                QMessageBox.warning(self, "Hata", f"İşlem başarısız (Kod: {cevap.status_code})\n{cevap.text}")
                
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Zaman Aşımı", "Sunucuya bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")
        except requests.exceptions.ConnectionError:
             QMessageBox.warning(self, "Bağlantı Hatası", "Sunucu kapalı olabilir. Backend'in (sunucu.py) çalıştığından emin olun.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen bir hata oluştu:\n{str(e)}")
# Sadece bu dosyayı test etmek için
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = OdaFormu(api_url="http://127.0.0.1:8000", token="TEST_TOKEN")
    pencere.show()
    sys.exit(app.exec())