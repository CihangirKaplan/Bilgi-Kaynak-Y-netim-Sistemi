from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt, QDate
import requests

class YeniBakimFormu(QDialog):
    """Yeni Cihaz Bakım Kaydı Formu"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        
        self.setWindowTitle("🛠️ Yeni Bakım Kaydı Ekle")
        self.setMinimumSize(500, 450)
        
        self.setObjectName("BakimKutusu")
        self.setStyleSheet("""
            QDialog#BakimKutusu { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-family: 'Segoe UI', Arial; font-size: 13px; font-weight: bold; background: transparent; }
            QLineEdit, QTextEdit, QComboBox, QDateEdit { 
                background-color: #FFFFFF; color: #2C3E50; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; font-family: 'Segoe UI', Arial; font-size: 13px;
            }
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus, QTextEdit:focus { border: 1px solid #3498DB; }
            QMessageBox { background-color: #FFFFFF; }
            QCalendarWidget QWidget { alternate-background-color: #EAECEE; }
        """)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.cmb_cihaz = QComboBox()
        self.dt_bakim = QDateEdit(QDate.currentDate())
        self.dt_bakim.setCalendarPopup(True)
        self.txt_yapan_kisi = QLineEdit()
        self.txt_yapan_kisi.setPlaceholderText("Örn: Biyomedikal Teknikeri Ahmet...")
        self.txt_maliyet = QLineEdit()
        self.txt_maliyet.setPlaceholderText("Örn: 1500.50")
        self.txt_islem = QTextEdit()
        self.txt_islem.setMaximumHeight(80)
        self.txt_islem.setPlaceholderText("Yapılan işlemleri belirtin...")

        form_layout.addRow("Bakım Yapılan Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Bakım Tarihi (*):", self.dt_bakim)
        form_layout.addRow("Bakımı Yapan Kişi (*):", self.txt_yapan_kisi)
        form_layout.addRow("Maliyet (₺):", self.txt_maliyet)
        form_layout.addRow("Yapılan İşlem (*):", self.txt_islem)

        layout.addLayout(form_layout)

        self.btn_kaydet = QPushButton("✅ Bakım Kaydını Kaydet")
        self.btn_kaydet.setStyleSheet("""
            QPushButton { background-color: #27AE60; color: white; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #229954; }
        """)
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

        self.verileri_yukle()

    def verileri_yukle(self):
        try:
            res_cihaz = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if res_cihaz.status_code == 200:
                cihazlar = res_cihaz.json()
                if cihazlar:
                    for c in cihazlar:
                        self.cmb_cihaz.addItem(f"{c['envanter_kodu']} - {c['cihaz_adi']}", c['cihaz_id'])
                else:
                    self.cmb_cihaz.addItem("Sistemde kayıtlı cihaz yok", None)
            else:
                self.cmb_cihaz.addItem("Cihazlar alınamadı", None)
        except Exception as e:
            QMessageBox.warning(self, "Bağlantı Hatası", "Cihazlar yüklenirken sunucuya ulaşılamadı.")

    def kaydet(self):
        cihaz_id = self.cmb_cihaz.currentData()
        yapan = self.txt_yapan_kisi.text().strip()
        islem = self.txt_islem.toPlainText().strip()
        maliyet_str = self.txt_maliyet.text().strip()

        if not cihaz_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir cihaz seçin.")
            return
        if not yapan or not islem:
            QMessageBox.warning(self, "Uyarı", "Lütfen yapan kişiyi ve yapılan işlemi boş bırakmayın.")
            return
            
        try:
            maliyet = float(maliyet_str.replace(",", ".")) if maliyet_str else 0.0
        except ValueError:
            QMessageBox.warning(self, "Uyarı", "Maliyet alanına sadece sayı giriniz (Örn: 1500.50).")
            return

        veri = {
            "cihaz_id": cihaz_id,
            "bakim_tarihi": self.dt_bakim.date().toString("yyyy-MM-dd"),
            "bakim_yapan_kisi": yapan,
            "yapilan_islem": islem,
            "maliyet": maliyet
        }

        try:
            res = requests.post(f"{self.api_url}/api/bakimlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 201:
                basari = QMessageBox(self)
                basari.setWindowTitle("Başarılı")
                basari.setText("✅ Bakım kaydı başarıyla eklendi!")
                basari.setStyleSheet("QMessageBox { background-color: #FFFFFF; } QLabel { color: #27AE60; font-size: 13px; font-weight: bold; } QPushButton { background-color: #27AE60; color: white; padding: 6px 15px; border-radius: 4px; font-weight: bold; }")
                basari.exec()
                self.accept()
            else:
                hata_detay = res.json().get("detail", "Bilinmeyen bir hata oluştu.")
                QMessageBox.warning(self, "İşlem Başarısız", hata_detay)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")


class BakimDuzenleFormu(QDialog):
    """Mevcut Bakım Kaydını Düzenleme Formu"""
    def __init__(self, api_url, token, bakim_verisi, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.bakim_verisi = bakim_verisi
        
        self.setWindowTitle("🛠️ Bakım Kaydını Düzenle")
        self.setMinimumSize(500, 450)
        
        self.setObjectName("BakimKutusu")
        self.setStyleSheet("""
            QDialog#BakimKutusu { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-family: 'Segoe UI', Arial; font-size: 13px; font-weight: bold; background: transparent; }
            QLineEdit, QTextEdit, QDateEdit { 
                background-color: #FFFFFF; color: #2C3E50; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; font-family: 'Segoe UI', Arial; font-size: 13px;
            }
            QDateEdit:focus, QLineEdit:focus, QTextEdit:focus { border: 1px solid #3498DB; }
            QLineEdit:read-only { background-color: #EAECEE; color: #7F8C8D; }
            QMessageBox { background-color: #FFFFFF; }
            QCalendarWidget QWidget { alternate-background-color: #EAECEE; }
        """)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        # Cihaz adı değiştirilemez (Mantıken bakım yapılmış bitmiş cihaza yapılmıştır)
        self.txt_cihaz = QLineEdit(self.bakim_verisi["cihaz_adi"])
        self.txt_cihaz.setReadOnly(True)
        
        # Eski tarihi takvime set et
        self.dt_bakim = QDateEdit(QDate.fromString(self.bakim_verisi["bakim_tarihi"][:10], "yyyy-MM-dd"))
        self.dt_bakim.setCalendarPopup(True)

        self.txt_yapan_kisi = QLineEdit(self.bakim_verisi["bakim_yapan_kisi"])
        self.txt_maliyet = QLineEdit(str(self.bakim_verisi["maliyet"]))
        
        self.txt_islem = QTextEdit(self.bakim_verisi["yapilan_islem"])
        self.txt_islem.setMaximumHeight(80)

        form_layout.addRow("Cihaz (Değiştirilemez):", self.txt_cihaz)
        form_layout.addRow("Bakım Tarihi (*):", self.dt_bakim)
        form_layout.addRow("Bakımı Yapan Kişi (*):", self.txt_yapan_kisi)
        form_layout.addRow("Maliyet (₺):", self.txt_maliyet)
        form_layout.addRow("Yapılan İşlem (*):", self.txt_islem)

        layout.addLayout(form_layout)

        self.btn_kaydet = QPushButton("💾 Değişiklikleri Kaydet")
        self.btn_kaydet.setStyleSheet("""
            QPushButton { background-color: #2980B9; color: white; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #2471A3; }
        """)
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

    def kaydet(self):
        yapan = self.txt_yapan_kisi.text().strip()
        islem = self.txt_islem.toPlainText().strip()
        maliyet_str = self.txt_maliyet.text().strip()

        if not yapan or not islem:
            QMessageBox.warning(self, "Uyarı", "Lütfen yapan kişiyi ve yapılan işlemi boş bırakmayın.")
            return
            
        try:
            maliyet = float(maliyet_str.replace(",", ".")) if maliyet_str else 0.0
        except ValueError:
            QMessageBox.warning(self, "Uyarı", "Maliyet alanına sadece sayı giriniz (Örn: 1500.50).")
            return

        veri = {
            "bakim_tarihi": self.dt_bakim.date().toString("yyyy-MM-dd"),
            "bakim_yapan_kisi": yapan,
            "yapilan_islem": islem,
            "maliyet": maliyet
        }

        try:
            res = requests.put(f"{self.api_url}/api/bakimlar/{self.bakim_verisi['bakim_id']}", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", "✅ Bakım kaydı başarıyla güncellendi!")
                self.accept()
            else:
                hata_detay = res.json().get("detail", "Bilinmeyen bir hata oluştu.")
                QMessageBox.warning(self, "İşlem Başarısız", hata_detay)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")


class BakimYonetimEkrani(QWidget):
    """Bakım Kayıtlarının Listelendiği Ana Ekran"""
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.bakim_detaylari = {}
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)

        ust_panel = QHBoxLayout()
        lbl_baslik = QLabel("🛠️ Cihaz Bakım Geçmişi")
        lbl_baslik.setStyleSheet("font-size: 20px; font-weight: bold; color: #2C3E50;")
        
        self.btn_yeni_bakim = QPushButton("+ Yeni Bakım Kaydı")
        self.btn_yeni_bakim.setStyleSheet("background-color: #2980B9; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px;")
        self.btn_yeni_bakim.setCursor(Qt.PointingHandCursor)
        self.btn_yeni_bakim.clicked.connect(self.yeni_bakim_ekle)

        self.btn_yenile = QPushButton("🔄 Yenile")
        self.btn_yenile.setStyleSheet("background-color: #7F8C8D; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px;")
        self.btn_yenile.setCursor(Qt.PointingHandCursor)
        self.btn_yenile.clicked.connect(self.verileri_yukle)

        ust_panel.addWidget(lbl_baslik)
        ust_panel.addStretch()
        ust_panel.addWidget(self.btn_yenile)
        ust_panel.addWidget(self.btn_yeni_bakim)

        layout.addLayout(ust_panel)

        self.tablo = QTableWidget()
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels(["Kayıt ID", "Cihaz", "Bakım Tarihi", "Yapan Kişi", "Maliyet (₺)", "İşlem Detayı", "İşlem"])
        
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tablo.horizontalHeader().setStretchLastSection(False) 
        
        self.tablo.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch) 
        self.tablo.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.tablo.setWordWrap(True)
        self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        # --- İŞTE BUTONU KURTARAN KOD BURASI ---
        # Satır boyu metne göre uzayabilir ama ASLA 50 pikselin altına inemez!
        self.tablo.verticalHeader().setMinimumSectionSize(50) 
        
        self.tablo.verticalHeader().setVisible(False)

        self.tablo.setAlternatingRowColors(True)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; alternate-background-color: #F2F4F4; color: #0A1F5C; } 
            QTableWidget::item { color: #0A1F5C; padding: 8px; }
            QHeaderView::section { background-color: #34495E; color: white; font-weight: bold; padding: 8px; border: none; }
        """)

        layout.addWidget(self.tablo)
        
        self.tablo.setColumnWidth(0, 70)
        self.tablo.setColumnWidth(1, 180)
        self.tablo.setColumnWidth(2, 100)
        self.tablo.setColumnWidth(3, 130)
        self.tablo.setColumnWidth(4, 110)

        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        self.bakim_detaylari.clear()
        try:
            res = requests.get(f"{self.api_url}/api/bakimlar", headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                bakimlar = res.json()
                for satir_indeks, b in enumerate(bakimlar):
                    self.tablo.insertRow(satir_indeks)
                    self.bakim_detaylari[b["bakim_id"]] = b # Tüm satır verisini hafızaya alıyoruz
                    
                    id_item = QTableWidgetItem(str(b["bakim_id"]))
                    id_item.setTextAlignment(Qt.AlignCenter)
                    
                    temiz_tarih = b["bakim_tarihi"][:10]
                    tarih_item = QTableWidgetItem(temiz_tarih)
                    tarih_item.setTextAlignment(Qt.AlignCenter)
                    
                    maliyet_degeri = float(b['maliyet'])
                    maliyet_metni = f"{maliyet_degeri:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    maliyet_item = QTableWidgetItem(f"{maliyet_metni} ₺")
                    maliyet_item.setTextAlignment(Qt.AlignCenter)

                    self.tablo.setItem(satir_indeks, 0, id_item)
                    self.tablo.setItem(satir_indeks, 1, QTableWidgetItem(b["cihaz_adi"]))
                    self.tablo.setItem(satir_indeks, 2, tarih_item)
                    self.tablo.setItem(satir_indeks, 3, QTableWidgetItem(b["bakim_yapan_kisi"]))
                    self.tablo.setItem(satir_indeks, 4, maliyet_item)
                    self.tablo.setItem(satir_indeks, 5, QTableWidgetItem(b["yapilan_islem"]))
                    
                    # --- DÜZENLE BUTONU EKLENİYOR ---
                    btn_duz = QPushButton("✎ Düzenle")
                    btn_duz.setStyleSheet("""
                        QPushButton { background-color: #F39C12; color: white; border-radius: 4px; padding: 5px; font-weight: bold; font-size: 11px; }
                        QPushButton:hover { background-color: #D68910; }
                    """)
                    btn_duz.setCursor(Qt.PointingHandCursor)
                    btn_duz.clicked.connect(lambda checked=False, b_id=b["bakim_id"]: self.bakim_duzenle_ac(b_id))
                    
                    btn_widget = QWidget()
                    btn_layout = QHBoxLayout(btn_widget)
                    btn_layout.setContentsMargins(5, 2, 5, 2)
                    btn_layout.setAlignment(Qt.AlignCenter)
                    btn_layout.addWidget(btn_duz)
                    
                    self.tablo.setCellWidget(satir_indeks, 6, btn_widget)
        except Exception as e:
            pass 

    def yeni_bakim_ekle(self):
        form = YeniBakimFormu(self.api_url, self.token, self)
        if form.exec():
            self.verileri_yukle() # Yenileme işlemi form kapandığında otomatik çalışır
            
    def bakim_duzenle_ac(self, bakim_id):
        secili_bakim = self.bakim_detaylari.get(bakim_id)
        if secili_bakim:
            form = BakimDuzenleFormu(self.api_url, self.token, secili_bakim, self)
            if form.exec():
                self.verileri_yukle() # Düzenleme bittiğinde tabloyu otomatik yenile