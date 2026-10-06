import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QMessageBox, QLineEdit
from PySide6.QtCore import Qt

# DEV-003'te kendi ellerimizle yazdığımız özel bileşenleri (tuğlaları) çağırıyoruz!
from ui_components import StandartButon, StandartGirdi

class LoginEkrani(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BKYS - Sisteme Giriş")
        self.resize(400, 250)
        self.setStyleSheet("background-color: #F8F9FA;") 
        
        # Ekran yerleşimi (Her şeyi ekranın ortasına hizalayacağız)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        # 1. Başlık Alanı
        self.baslik = QLabel("<b>TRAVMA MERKEZİ<br>Bilgi ve Kaynak Yönetim Sistemi</b>")
        self.baslik.setStyleSheet("font-size: 18px; color: #0D3C7A;")
        self.baslik.setAlignment(Qt.AlignCenter)
        
        # 2. Kullanıcı Adı Girdisi (Kendi özel StandartGirdi'miz)
        self.kullanici_adi_input = StandartGirdi("Kullanıcı Adı...")
        
        # 3. Şifre Girdisi (Şifre yazarken *** çıkması için EchoMode ayarlıyoruz)
        self.sifre_input = StandartGirdi("Şifre...")
        self.sifre_input.setEchoMode(QLineEdit.Password) 
        
        self.giris_buton = StandartButon("Sisteme Giriş Yap")
        
        # Butona tıklanınca ne olacağını bağlıyoruz (Şimdilik sadece test fonksiyonuna gidiyor)
        self.giris_buton.clicked.connect(self.giris_yap_test)
        
        # Elemanları yukarıdan aşağıya ekrana diziyoruz
        layout.addWidget(self.baslik)
        layout.addSpacing(25) # Araya biraz boşluk (Nefes payı)
        layout.addWidget(self.kullanici_adi_input)
        layout.addWidget(self.sifre_input)
        layout.addSpacing(15)
        layout.addWidget(self.giris_buton)
        
        self.setLayout(layout)

    def giris_yap_test(self):
        # Butona basıldığında şimdilik çalışacak test fonksiyonu
        k_adi = self.kullanici_adi_input.text()
        sifre = self.sifre_input.text()
        
        # Ekranda küçük bir uyarı penceresi çıkaralım
        QMessageBox.information(self, "Bağlantı Testi", f"Giriş isteği alındı.\nKullanıcı: {k_adi}\n\n(Daha sonra Backend'e bağlanılacak)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = LoginEkrani()
    pencere.show()
    sys.exit(app.exec())