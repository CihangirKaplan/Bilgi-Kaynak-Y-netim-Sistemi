import sys
import requests
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QListWidget, QVBoxLayout, QWidget, QMessageBox

class SpikeArayuz(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hafta 1 Gün 5 - Teknik Spike")
        self.resize(400, 300)

        self.btn = QPushButton("Sunucudan Veri Çek")
        self.liste = QListWidget()

        layout = QVBoxLayout()
        layout.addWidget(self.btn)
        layout.addWidget(self.liste)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.btn.clicked.connect(self.veri_yukle)

    def veri_yukle(self):
        self.liste.clear()
        try:
            # API bizim kendi laptopumuzda çalıştığı için localhost'a istek atıyoruz
            yanit = requests.get("http://localhost:8000/api/cihazlar")
            sonuc = yanit.json()
            
            if sonuc["durum"] == "basarili":
                for c in sonuc["veri"]:
                    self.liste.addItem(f"[{c['envanter_kodu']}] {c['cihaz_adi']} - {c['durum']}")
            else:
                QMessageBox.warning(self, "Hata", sonuc["mesaj"])
        except Exception as err:
            QMessageBox.critical(self, "Bağlantı Hatası", f"API'ye ulaşılamadı:\n{err}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = SpikeArayuz()
    pencere.show()
    sys.exit(app.exec())