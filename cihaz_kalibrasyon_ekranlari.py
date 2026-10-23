from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit
)
from PySide6.QtCore import Qt, QDate
import requests

class YeniKalibrasyonFormu(QDialog):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        
        self.setWindowTitle("🎯 Yeni Kalibrasyon Kaydı Ekle")
        self.setMinimumSize(450, 420)
        
        self.setObjectName("KalibrasyonKutusu")
        self.setStyleSheet("""
            QDialog#KalibrasyonKutusu { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-family: 'Segoe UI', Arial; font-size: 13px; font-weight: bold; background: transparent; }
            QLineEdit, QComboBox, QDateEdit { 
                background-color: #FFFFFF; color: #2C3E50; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; font-family: 'Segoe UI', Arial; font-size: 13px;
            }
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus { border: 1px solid #3498DB; }
            QMessageBox { background-color: #FFFFFF; }
            QCalendarWidget QWidget { alternate-background-color: #EAECEE; color: black; }
        """)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(15)

        self.cmb_cihaz = QComboBox()
        self.txt_kurum = QLineEdit()
        self.txt_kurum.setPlaceholderText("Örn: TSE, Kalibro A.Ş...")
        self.txt_sertifika = QLineEdit()
        self.txt_sertifika.setPlaceholderText("Sertifika veya Belge No...")
        self.dt_gecerlilik = QDateEdit(QDate.currentDate().addYears(1))
        self.dt_gecerlilik.setCalendarPopup(True)

        # --- YENİ EKLENEN TARİHLER ---
        self.dt_baslangic = QDateEdit(QDate.currentDate())
        self.dt_baslangic.setCalendarPopup(True)
        
        self.dt_bitis = QDateEdit(QDate.currentDate())
        self.dt_bitis.setCalendarPopup(True)

        form.addRow("Cihaz (*):", self.cmb_cihaz)
        form.addRow("Yapan Kurum (*):", self.txt_kurum)
        form.addRow("Sertifika No (*):", self.txt_sertifika)
        form.addRow("Başlangıç Tarihi (*):", self.dt_baslangic) # YENİ
        form.addRow("Bitiş Tarihi (*):", self.dt_bitis)         # YENİ
        form.addRow("Geçerlilik Tarihi (*):", self.dt_gecerlilik)
        layout.addLayout(form)

        self.btn_kaydet = QPushButton("✅ Kaydet")
        self.btn_kaydet.setStyleSheet("""
            QPushButton { background-color: #27AE60; color: white; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px;}
            QPushButton:hover { background-color: #229954; }
        """)
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        layout.addWidget(self.btn_kaydet)

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
        veri = {
            "cihaz_id": self.cmb_cihaz.currentData(),
            "kalibrasyon_yapan_kurum": self.txt_kurum.text().strip(),
            "sertifika_no": self.txt_sertifika.text().strip(),
            "gecerlilik_tarihi": self.dt_gecerlilik.date().toString("yyyy-MM-dd"),
            # YENİ EKLENEN VERİLER
            "kalibrasyon_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "kalibrasyon_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd")
        }
        if not veri["kalibrasyon_yapan_kurum"] or not veri["sertifika_no"]:
            QMessageBox.warning(self, "Uyarı", "Kurum ve Sertifika No zorunludur.")
            return

        try:
            res = requests.post(f"{self.api_url}/api/kalibrasyonlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 201:
                QMessageBox.information(self, "Başarılı", "✅ Kalibrasyon başarıyla eklendi!")
                self.accept()
            else:
                # Hatayı gizlemiyoruz, ekrana basıyoruz!
                hata_mesaji = res.json().get("detail", "Kayıt yapılamadı.")
                QMessageBox.warning(self, "Hata", f"Sebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class KalibrasyonDuzenleFormu(QDialog):
    def __init__(self, api_url, token, veri, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.k_veri = veri
        
        self.setWindowTitle("🎯 Kalibrasyon Düzenle")
        self.setMinimumSize(450, 420)
        
        self.setObjectName("KalibrasyonKutusu")
        self.setStyleSheet("""
            QDialog#KalibrasyonKutusu { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-family: 'Segoe UI', Arial; font-size: 13px; font-weight: bold; background: transparent; }
            QLineEdit, QDateEdit { 
                background-color: #FFFFFF; color: #2C3E50; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; font-family: 'Segoe UI', Arial; font-size: 13px;
            }
            QDateEdit:focus, QLineEdit:focus { border: 1px solid #3498DB; }
            QLineEdit:read-only { background-color: #EAECEE; color: #7F8C8D; }
            QMessageBox { background-color: #FFFFFF; }
            QCalendarWidget QWidget { alternate-background-color: #EAECEE; color: black; }
        """)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(15)

        self.txt_cihaz = QLineEdit(veri.get("cihaz_adi", ""))
        self.txt_cihaz.setReadOnly(True)
        self.txt_kurum = QLineEdit(veri.get("kalibrasyon_yapan_kurum", ""))
        self.txt_sertifika = QLineEdit(veri.get("sertifika_no", ""))
        self.dt_gecerlilik = QDateEdit(QDate.fromString(str(veri.get("gecerlilik_tarihi", QDate.currentDate().toString("yyyy-MM-dd")))[:10], "yyyy-MM-dd"))
        self.dt_gecerlilik.setCalendarPopup(True)

        # --- YENİ TARİHLERİ GÜVENLİ ÇEKME ---
        baslangic_str = veri.get("kalibrasyon_baslangic_tarihi") or QDate.currentDate().toString("yyyy-MM-dd")
        bitis_str = veri.get("kalibrasyon_bitis_tarihi") or baslangic_str
        
        self.dt_baslangic = QDateEdit(QDate.fromString(str(baslangic_str)[:10], "yyyy-MM-dd"))
        self.dt_baslangic.setCalendarPopup(True)
        
        self.dt_bitis = QDateEdit(QDate.fromString(str(bitis_str)[:10], "yyyy-MM-dd"))
        self.dt_bitis.setCalendarPopup(True)

        form.addRow("Cihaz:", self.txt_cihaz)
        form.addRow("Yapan Kurum (*):", self.txt_kurum)
        form.addRow("Sertifika No (*):", self.txt_sertifika)
        form.addRow("Başlangıç Tarihi (*):", self.dt_baslangic) # YENİ
        form.addRow("Bitiş Tarihi (*):", self.dt_bitis)         # YENİ
        form.addRow("Geçerlilik (*):", self.dt_gecerlilik)
        layout.addLayout(form)

        btn = QPushButton("💾 Güncelle")
        btn.setStyleSheet("""
            QPushButton { background-color: #2980B9; color: white; padding: 10px; border-radius: 6px; font-weight: bold; font-size: 14px;}
            QPushButton:hover { background-color: #2471A3; }
        """)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self.kaydet)
        layout.addWidget(btn)

    def kaydet(self):
        veri = {
            "kalibrasyon_yapan_kurum": self.txt_kurum.text().strip(),
            "sertifika_no": self.txt_sertifika.text().strip(),
            "gecerlilik_tarihi": self.dt_gecerlilik.date().toString("yyyy-MM-dd"),
            # YENİ EKLENEN VERİLER
            "kalibrasyon_baslangic_tarihi": self.dt_baslangic.date().toString("yyyy-MM-dd"),
            "kalibrasyon_bitis_tarihi": self.dt_bitis.date().toString("yyyy-MM-dd")
        }
        if not veri["kalibrasyon_yapan_kurum"] or not veri["sertifika_no"]:
            QMessageBox.warning(self, "Uyarı", "Kurum ve Sertifika No zorunludur.")
            return
            
        try:
            res = requests.put(f"{self.api_url}/api/kalibrasyonlar/{self.k_veri['kalibrasyon_id']}", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200: 
                QMessageBox.information(self, "Başarılı", "✅ Kalibrasyon başarıyla güncellendi!")
                self.accept()
            else:
                hata_mesaji = res.json().get("detail", "Güncelleme yapılamadı.")
                QMessageBox.warning(self, "Hata", f"Sebep: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası: {str(e)}")

class KalibrasyonYonetimEkrani(QWidget):
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.detaylar = {}
        
        layout = QVBoxLayout(self)
        ust = QHBoxLayout()
        baslik = QLabel("🎯 Cihaz Kalibrasyon Kayıtları")
        baslik.setStyleSheet("font-size: 20px; font-weight: bold; color: #2C3E50;")
        
        btn_yeni = QPushButton("+ Yeni Kalibrasyon")
        btn_yeni.setStyleSheet("background-color: #2980B9; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px;")
        btn_yeni.setCursor(Qt.PointingHandCursor)
        btn_yeni.clicked.connect(self.yeni_ekle)
        
        btn_yenile = QPushButton("🔄 Yenile")
        btn_yenile.setStyleSheet("background-color: #7F8C8D; color: white; padding: 8px 15px; font-weight: bold; border-radius: 4px;")
        btn_yenile.setCursor(Qt.PointingHandCursor)
        btn_yenile.clicked.connect(self.yukle)

        ust.addWidget(baslik); ust.addStretch(); ust.addWidget(btn_yenile); ust.addWidget(btn_yeni)
        layout.addLayout(ust)

# Tabloyu 7 sütundan 9 sütuna çıkardık ve başlıkları güncelledik
        self.tablo = QTableWidget(0, 9)
        self.tablo.setHorizontalHeaderLabels([
            "ID", "Cihaz", "Kurum", "Sertifika No", 
            "Başlangıç", "Bitiş", "Geçerlilik", "İşlem Tarihi", "İşlem"
        ])
        
# Sabit width (genişlik) yerine içeriğe göre dinamik boyutlanma yapıyoruz
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # ID
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)          # Cihaz (Esner)
        self.tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)          # Kurum (Esner)
        self.tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents) # Sertifika
        self.tablo.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents) # Başlangıç
        self.tablo.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents) # Bitiş
        self.tablo.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents) # Geçerlilik
        
        # --- DEĞİŞEN KISIM: 7 ve 8. Sütunları "Fixed" yapıyoruz ---
        self.tablo.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed) # İşlem Tarihi
        self.tablo.horizontalHeader().setSectionResizeMode(8, QHeaderView.Fixed) # Düzenle Butonu

        # Diğer standart tablo ayarların
        self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tablo.verticalHeader().setMinimumSectionSize(50) 
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setWordWrap(True)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; alternate-background-color: #F2F4F4; color: #0A1F5C; } 
            QTableWidget::item { padding: 8px; color: #0A1F5C; } 
            QHeaderView::section { background-color: #34495E; color: white; font-weight: bold; padding: 8px; border: none; }
        """)
        
        layout.addWidget(self.tablo)
        
        # --- DEĞİŞEN KISIM: Sadece bu iki sütuna asla daralmayacak net genişlik veriyoruz ---
        self.tablo.setColumnWidth(7, 130) # Tarih ve saat tek satırda aslanlar gibi duracak
        self.tablo.setColumnWidth(8, 105) # Düzenle butonu yazısı tam sığacak
        
        self.yukle()

    def yukle(self):
        self.tablo.setRowCount(0); self.detaylar.clear()
        try:
            res = requests.get(f"{self.api_url}/api/kalibrasyonlar", headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 200:
                for i, k in enumerate(res.json()):
                    self.tablo.insertRow(i)
                    self.detaylar[k["kalibrasyon_id"]] = k
                    
                    # 0. ID
                    id_item = QTableWidgetItem(str(k["kalibrasyon_id"]))
                    id_item.setTextAlignment(Qt.AlignCenter)
                    self.tablo.setItem(i, 0, id_item)
                    
                    # 1. Cihaz ve 2. Kurum
                    self.tablo.setItem(i, 1, QTableWidgetItem(k.get("cihaz_adi", "")))
                    self.tablo.setItem(i, 2, QTableWidgetItem(k.get("kalibrasyon_yapan_kurum", "")))
                    
                    # 3. Sertifika No
                    sert_item = QTableWidgetItem(k.get("sertifika_no", ""))
                    sert_item.setTextAlignment(Qt.AlignCenter)
                    self.tablo.setItem(i, 3, sert_item)
                    
                    # 4. YENİ: Başlangıç Tarihi
                    baslangic_str = k.get("kalibrasyon_baslangic_tarihi", "Belirtilmedi")
                    bas_item = QTableWidgetItem(baslangic_str[:10] if baslangic_str != "Belirtilmedi" else "Belirtilmedi")
                    bas_item.setTextAlignment(Qt.AlignCenter)
                    self.tablo.setItem(i, 4, bas_item)

                    # 5. YENİ: Bitiş Tarihi
                    bitis_str = k.get("kalibrasyon_bitis_tarihi", "Belirtilmedi")
                    bitis_item = QTableWidgetItem(bitis_str[:10] if bitis_str != "Belirtilmedi" else "Belirtilmedi")
                    bitis_item.setTextAlignment(Qt.AlignCenter)
                    self.tablo.setItem(i, 5, bitis_item)
                    
                    # 6. Geçerlilik Tarihi (Kayıp geldi)
                    gecerlilik_str = k.get("gecerlilik_tarihi", "Belirtilmedi")
                    gec_item = QTableWidgetItem(gecerlilik_str[:10] if gecerlilik_str != "Belirtilmedi" else "Belirtilmedi")
                    gec_item.setTextAlignment(Qt.AlignCenter)
                    self.tablo.setItem(i, 6, gec_item)
                    
                    # 7. İşlem Tarihi (Kayıp geldi)
                    islem_str = k.get("islem_tarihi", "")
                    tarih_metni = islem_str[:16].replace("T", " ") if "T" in islem_str else islem_str[:16]
                    tarih_item = QTableWidgetItem(tarih_metni)
                    tarih_item.setTextAlignment(Qt.AlignCenter)
                    self.tablo.setItem(i, 7, tarih_item)
                    
                    # 8. İşlem Butonu
                    btn = QPushButton("✎ Düzenle")
                    btn.setStyleSheet("background-color: #F39C12; color: white; border-radius: 4px; padding: 6px 12px; font-weight: bold;")
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.clicked.connect(lambda _, kid=k["kalibrasyon_id"]: self.duzenle(kid))
                    
                    w = QWidget(); l = QHBoxLayout(w); l.setContentsMargins(5, 2, 5, 2); l.setAlignment(Qt.AlignCenter); l.addWidget(btn)
                    self.tablo.setCellWidget(i, 8, w)
        except Exception:
            pass

    def yeni_ekle(self):
        if YeniKalibrasyonFormu(self.api_url, self.token, self).exec(): self.yukle()
        
    def duzenle(self, kid):
        if KalibrasyonDuzenleFormu(self.api_url, self.token, self.detaylar[kid], self).exec(): self.yukle()