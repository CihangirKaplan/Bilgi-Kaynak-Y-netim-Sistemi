import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel

# ==========================================
# 1. ORTAK BİLEŞEN: STANDART BUTON
# ==========================================
class StandartButon(QPushButton):
    def __init__(self, metin):
        super().__init__(metin)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1A73E8; 
                color: white;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #1557B0; 
            }
            QPushButton:pressed {
                background-color: #0D3C7A; 
            }
        """)

# ==========================================
# 2. ORTAK BİLEŞEN: STANDART METİN KUTUSU
# ==========================================
class StandartGirdi(QLineEdit):
    def __init__(self, placeholder_metni):
        super().__init__()
        self.setPlaceholderText(placeholder_metni)
        self.setStyleSheet("""
            QLineEdit {
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                padding: 8px;
                font-size: 14px;
                background-color: #ffffff;
                color: #000000; 
            }
            QLineEdit:focus {
                border: 2px solid #1A73E8; 
            }
        """)

# ==========================================
# 3. TEST EKRANI (Bileşenleri Görmek İçin)
# ==========================================
class UITestEkrani(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BKYS - DEV-003 UI Testi")
        self.resize(350, 200)
        
        self.setStyleSheet("background-color: #F8F9FA;")
        
        layout = QVBoxLayout()
        
        self.baslik = QLabel("<b>Cihaz Modülü (Ön İzleme)</b>")
        self.baslik.setStyleSheet("font-size: 18px; color: #0D3C7A; padding-bottom: 10px;")
        
        self.cihaz_adi_input = StandartGirdi("Cihaz Adı Giriniz (Örn: MRI)...")
        self.kaydet_buton = StandartButon("Sisteme Kaydet")
        
        layout.addWidget(self.baslik)
        layout.addWidget(self.cihaz_adi_input)
        layout.addWidget(self.kaydet_buton)
        
        self.setLayout(layout)

# Dosya direkt çalıştırılırsa test ekranını aç
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = UITestEkrani()
    pencere.show()
    sys.exit(app.exec())