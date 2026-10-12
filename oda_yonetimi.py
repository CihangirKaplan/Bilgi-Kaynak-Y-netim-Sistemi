import sys
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, 
    QMessageBox, QApplication, QCheckBox
)
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
        self.resize(350, 200)
        self.setStyleSheet("background-color: #F8F9FA;")
        
        self.init_ui()
        
        if self.oda_id and self.eski_veriler:
            self.eski_verileri_bas()

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # VARCHAR(50) kuralına uygun olarak MaxLength sınırı eklendi
        self.in_oda_adi = StandartGirdi("Oda Adı (Örn: Terapi Odası 1)")
        self.in_oda_adi.setMaxLength(50) 
        form_layout.addRow("Oda Adı:", self.in_oda_adi)

        self.in_kapasite = StandartGirdi("Kapasite (Örn: 2)")
        self.in_kapasite.setText("1")
        form_layout.addRow("Kapasite:", self.in_kapasite)
        
        self.chk_aktif = QCheckBox("Bu oda aktif olarak kullanılabilir.")
        self.chk_aktif.setChecked(True)
        self.chk_aktif.setStyleSheet("color: black; font-weight: bold;")
        form_layout.addRow("Durum:", self.chk_aktif)

        layout.addLayout(form_layout)
        
        buton_layout = QHBoxLayout()
        if self.oda_id:
            self.btn_kaydet = StandartButon("Değişiklikleri Kaydet")
            self.btn_kaydet.setStyleSheet("background-color: #f39c12; color: white; border-radius: 6px; padding: 10px; font-weight: bold;")
        else:
            self.btn_kaydet = StandartButon("Odayı Sisteme Kaydet")
            
        self.btn_kaydet.clicked.connect(self.odayi_kaydet)
        buton_layout.addWidget(self.btn_kaydet)
        
        layout.addLayout(buton_layout)
        self.setLayout(layout)

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
            elif cevap.status_code == 409: # UNIQUE hatası kontrolü
                QMessageBox.warning(self, "Çakışma", "Bu isimde bir oda zaten mevcut!")
            else:
                QMessageBox.warning(self, "Hata", f"İşlem başarısız (Kod: {cevap.status_code})")
                
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Zaman Aşımı", "Sunucuya bağlanılamadı.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

# Sadece bu dosyayı test etmek için
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = OdaFormu(api_url="http://127.0.0.1:8000", token="TEST_TOKEN")
    pencere.show()
    sys.exit(app.exec())