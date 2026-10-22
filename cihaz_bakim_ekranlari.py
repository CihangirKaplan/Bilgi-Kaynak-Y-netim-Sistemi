from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt, QDate
import requests

class YeniBakimFormu(QDialog):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        
        self.setWindowTitle("🛠️ Yeni Bakım Kaydı Ekle")
        self.setMinimumSize(450, 500)
        
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; }
            QLabel { font-weight: bold; color: #2C3E50; font-size: 13px; }
            QLineEdit, QComboBox, QDateEdit, QTextEdit { 
                background-color: white; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; color: #2C3E50;
            }
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus, QTextEdit:focus { border: 1px solid #3498DB; }
        """)

        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.cmb_cihaz = QComboBox()
        self.txt_kisi = QLineEdit()
        self.txt_islem = QTextEdit()
        self.txt_islem.setMaximumHeight(80)
        self.txt_maliyet = QLineEdit("0.0")
        
        # --- YENİ EKLENEN: BAŞLANGIÇ VE BİTİŞ TARİHLERİ ---
        self.dt_baslangic = QDateEdit(QDate.currentDate())
        self.dt_baslangic.setCalendarPopup(True)
        
        self.dt_bitis = QDateEdit(QDate.currentDate())
        self.dt_bitis.setCalendarPopup(True)
        
        self.dt_sonraki_bakim = QDateEdit(QDate.currentDate().addMonths(6))
        self.dt_sonraki_bakim.setCalendarPopup(True)

        form_layout.addRow("Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Bakım Yapan Kişi (*):", self.txt_kisi)
        form_layout.addRow("Yapılan İşlem (*):", self.txt_islem)
        form_layout.addRow("Maliyet (₺):", self.txt_maliyet)
        form_layout.addRow("Başlangıç Tarihi (*):", self.dt_baslangic)
        form_layout.addRow("Bitiş Tarihi (*):", self.dt_bitis)
        form_layout.addRow("Sonraki Bakım Tarihi:", self.dt_sonraki_bakim)
        
        layout.addLayout(form_layout)

        btn_kaydet = QPushButton("✅ Kaydet")
        btn_kaydet.setStyleSheet("QPushButton { background-color: #27AE60; color: white; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px;} QPushButton:hover { background-color: #229954; }")
        btn_kaydet.setCursor(Qt.PointingHandCursor)
        btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(btn_kaydet)

        self.cihazlari_yukle()

    def cihazlari_yukle(self):
        try:
            res = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                for c in res.json():
                    self.cmb_cihaz.addItem(f"{c['envanter_kodu']} - {c['cihaz_adi']}", c['cihaz_id'])
        except Exception:
            pass

    def kaydet(self):
# TL Formatı Düzeltici: 10.000,50 veya 10000 veya 10,50'yi anlar
        metin = self.txt_maliyet.text().strip()
        if '.' in metin and ',' in metin:
            metin = metin.replace('.', '').replace(',', '.')
        elif '.' in metin and len(metin.split('.')[-1]) == 3:
            metin = metin.replace('.', '')
        else:
            metin = metin.replace(',', '.')
            
        try:
            maliyet = float(metin)
        except ValueError:
            maliyet = 0.0

        # GÜVENLİK YAMASI: Eski model "bakim_tarihi" bekliyorsa diye onu da pakete ekliyoruz
        veri = {
            "cihaz_id": self.cmb_cihaz.currentData(),
            "bakim_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"), # EKLENDİ
            "bakim_yapan_kisi": self.txt_kisi.text().strip(),
            "yapilan_islem": self.txt_islem.toPlainText().strip(),
            "maliyet": maliyet,
            "bakim_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "bakim_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd"),
            "sonraki_bakim_tarihi": self.dt_sonraki_bakim.date().toString("yyyy-MM-dd")
        }
        
        if not veri["bakim_yapan_kisi"] or not veri["yapilan_islem"]:
            QMessageBox.warning(self, "Uyarı", "Kişi ve Yapılan İşlem alanları zorunludur.")
            return

        try:
            res = requests.post(f"{self.api_url}/api/bakimlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 201:
                QMessageBox.information(self, "Başarılı", "✅ Bakım kaydı başarıyla eklendi!")
                self.accept()
            else:
                # ARTIK HATAYI GİZLEMİYORUZ, SUNUCUNUN CEVABINI EKRANA BASIYORUZ!
                hata_mesaji = res.json().get("detail", "Bilinmeyen Sunucu Hatası")
                QMessageBox.warning(self, "Hata", f"Kayıt yapılamadı!\n\nSebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class BakimDuzenleFormu(QDialog):
    def __init__(self, api_url, token, bakim_verisi, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.bakim_verisi = bakim_verisi
        
        self.setWindowTitle("🛠️ Bakım Kaydını Düzenle")
        self.setMinimumSize(450, 520)
        
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; }
            QLabel { font-weight: bold; color: #2C3E50; font-size: 13px; }
            QLineEdit, QComboBox, QDateEdit, QTextEdit { 
                background-color: white; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; color: #2C3E50;
            }
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus, QTextEdit:focus { border: 1px solid #3498DB; }
            QLineEdit:read-only { background-color: #EAECEE; color: #7F8C8D; }
        """)

        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(15)
        
        self.txt_cihaz = QLineEdit(bakim_verisi.get("cihaz_adi", ""))
        self.txt_cihaz.setReadOnly(True)
        self.txt_kisi = QLineEdit(bakim_verisi.get("bakim_yapan_kisi", ""))
        
        maliyet_str = str(bakim_verisi.get("maliyet", "0.0"))
        self.txt_maliyet = QLineEdit(maliyet_str)
        
        self.txt_islem = QTextEdit(bakim_verisi.get("yapilan_islem", ""))
        self.txt_islem.setMaximumHeight(80)

        # --- TARİHLERİ GÜVENLİ ÇEKME (Hiçbir şekilde patlamaz) ---
        baslangic_str = bakim_verisi.get("bakim_baslangic_tarihi") or bakim_verisi.get("bakim_tarihi") or QDate.currentDate().toString("yyyy-MM-dd")
        bitis_str = bakim_verisi.get("bakim_bitis_tarihi") or baslangic_str
        sonraki_str = bakim_verisi.get("sonraki_bakim_tarihi") or QDate.currentDate().addMonths(6).toString("yyyy-MM-dd")
            
        self.dt_baslangic = QDateEdit(QDate.fromString(str(baslangic_str)[:10], "yyyy-MM-dd"))
        self.dt_baslangic.setCalendarPopup(True)
        
        self.dt_bitis = QDateEdit(QDate.fromString(str(bitis_str)[:10], "yyyy-MM-dd"))
        self.dt_bitis.setCalendarPopup(True)

        self.dt_sonraki_bakim = QDateEdit(QDate.fromString(str(sonraki_str)[:10], "yyyy-MM-dd"))
        self.dt_sonraki_bakim.setCalendarPopup(True)

        form_layout.addRow("Cihaz (Değiştirilemez):", self.txt_cihaz)
        form_layout.addRow("Bakımı Yapan Kişi (*):", self.txt_kisi)
        form_layout.addRow("Maliyet (₺):", self.txt_maliyet)
        form_layout.addRow("Yapılan İşlem (*):", self.txt_islem)
        form_layout.addRow("Başlangıç Tarihi (*):", self.dt_baslangic)
        form_layout.addRow("Bitiş Tarihi (*):", self.dt_bitis)
        form_layout.addRow("Sonraki Bakım Tarihi:", self.dt_sonraki_bakim) 
        
        layout.addLayout(form_layout)

        btn_kaydet = QPushButton("💾 Değişiklikleri Kaydet")
        btn_kaydet.setStyleSheet("QPushButton { background-color: #2980B9; color: white; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px;} QPushButton:hover { background-color: #2471A3; }")
        btn_kaydet.setCursor(Qt.PointingHandCursor)
        btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(btn_kaydet)

    def kaydet(self):
        # TL Formatı Düzeltici
        metin = self.txt_maliyet.text().strip()
        if '.' in metin and ',' in metin:
            metin = metin.replace('.', '').replace(',', '.')
        elif '.' in metin and len(metin.split('.')[-1]) == 3:
            metin = metin.replace('.', '')
        else:
            metin = metin.replace(',', '.')
            
        try:
            maliyet = float(metin)
        except ValueError:
            maliyet = 0.0

        veri = {
            "bakim_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "bakim_yapan_kisi": self.txt_kisi.text().strip(),
            "yapilan_islem": self.txt_islem.toPlainText().strip(),
            "maliyet": maliyet,
            "bakim_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "bakim_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd"),
            "sonraki_bakim_tarihi": self.dt_sonraki_bakim.date().toString("yyyy-MM-dd") 
        }
        
        if not veri["bakim_yapan_kisi"] or not veri["yapilan_islem"]:
            QMessageBox.warning(self, "Uyarı", "Kişi ve Yapılan İşlem alanları zorunludur.")
            return

        try:
            res = requests.put(f"{self.api_url}/api/bakimlar/{self.bakim_verisi['bakim_id']}", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", "✅ Bakım kaydı başarıyla güncellendi!")
                self.accept()
            else:
                hata_mesaji = res.json().get("detail", "Bilinmeyen Sunucu Hatası")
                QMessageBox.warning(self, "Hata", f"Güncelleme yapılamadı!\n\nSebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class BakimYonetimEkrani(QWidget):
    """Bakım Kayıtlarının Listelendiği Saf Tablo Ekranı"""
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

        # Tabloya Başlangıç ve Bitiş Sütunları Eklendi (Toplam 9 Sütun)
        self.tablo = QTableWidget(0, 9) 
        self.tablo.setHorizontalHeaderLabels(["ID", "Cihaz", "Yapan Kişi", "İşlem", "Maliyet", "Başlangıç", "Bitiş", "Sonraki Bakım", "İşlem"])
        
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tablo.horizontalHeader().setStretchLastSection(False) 
        
        # Hizalamayı Jilet Gibi Yapan Esneme Ayarları
        self.tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch) # İşlem sütunu uzasın
        self.tablo.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents) # Başlangıç daralsın
        self.tablo.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents) # Bitiş daralsın
        self.tablo.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents) # Sonraki Bakım daralsın
        
        self.tablo.setWordWrap(True)
        self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
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
                    self.bakim_detaylari[b["bakim_id"]] = b 
                    
                    id_item = QTableWidgetItem(str(b["bakim_id"]))
                    id_item.setTextAlignment(Qt.AlignCenter)
                    
                    maliyet_degeri = float(b.get('maliyet', 0.0))
                    maliyet_metni = f"{maliyet_degeri:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    maliyet_item = QTableWidgetItem(f"{maliyet_metni} ₺")
                    maliyet_item.setTextAlignment(Qt.AlignCenter)

                    # --- GÜVENLİ TARİH OKUMA (None veya boş gelirse patlamaz) ---
                    baslangic = b.get("bakim_baslangic_tarihi")
                    baslangic_metni = baslangic[:10] if baslangic else str(b.get("bakim_tarihi", "Belirtilmedi"))[:10]
                    
                    bitis = b.get("bakim_bitis_tarihi")
                    bitis_metni = bitis[:10] if bitis else "Belirtilmedi"

                    sonraki = b.get("sonraki_bakim_tarihi")
                    sonraki_metni = sonraki[:10] if sonraki else "Belirtilmedi"

                    baslangic_item = QTableWidgetItem(baslangic_metni)
                    baslangic_item.setTextAlignment(Qt.AlignCenter)
                    
                    bitis_item = QTableWidgetItem(bitis_metni)
                    bitis_item.setTextAlignment(Qt.AlignCenter)
                    
                    sonraki_item = QTableWidgetItem(sonraki_metni)
                    sonraki_item.setTextAlignment(Qt.AlignCenter)

                    # Hücreleri sıfır hata ile yerleştiriyoruz
                    self.tablo.setItem(satir_indeks, 0, id_item)
                    self.tablo.setItem(satir_indeks, 1, QTableWidgetItem(b.get("cihaz_adi", "")))
                    self.tablo.setItem(satir_indeks, 2, QTableWidgetItem(b.get("bakim_yapan_kisi", "")))
                    self.tablo.setItem(satir_indeks, 3, QTableWidgetItem(b.get("yapilan_islem", "")))
                    self.tablo.setItem(satir_indeks, 4, maliyet_item)
                    self.tablo.setItem(satir_indeks, 5, baslangic_item)
                    self.tablo.setItem(satir_indeks, 6, bitis_item)
                    self.tablo.setItem(satir_indeks, 7, sonraki_item)
                    
                    # Düzenle Butonu (8. Sütun)
                    btn_duz = QPushButton("✎ Düzenle")
                    btn_duz.setStyleSheet("QPushButton { background-color: #F39C12; color: white; border-radius: 4px; padding: 5px; font-weight: bold; font-size: 11px; } QPushButton:hover { background-color: #D68910; }")
                    btn_duz.setCursor(Qt.PointingHandCursor)
                    btn_duz.clicked.connect(lambda checked=False, b_id=b["bakim_id"]: self.bakim_duzenle_ac(b_id))
                    
                    btn_widget = QWidget()
                    btn_layout = QHBoxLayout(btn_widget)
                    btn_layout.setContentsMargins(5, 2, 5, 2)
                    btn_layout.setAlignment(Qt.AlignCenter)
                    btn_layout.addWidget(btn_duz)
                    
                    self.tablo.setCellWidget(satir_indeks, 8, btn_widget)
        except Exception as e:
            print("Tablo yükleme hatası:", e)

    def yeni_bakim_ekle(self):
        form = YeniBakimFormu(self.api_url, self.token, self)
        if form.exec():
            self.verileri_yukle() 
            
    def bakim_duzenle_ac(self, bakim_id):
        secili_bakim = self.bakim_detaylari.get(bakim_id)
        if secili_bakim:
            form = BakimDuzenleFormu(self.api_url, self.token, secili_bakim, self)
            if form.exec():
                self.verileri_yukle()