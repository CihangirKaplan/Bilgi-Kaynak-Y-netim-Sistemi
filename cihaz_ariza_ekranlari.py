import sys
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, 
    QComboBox, QMessageBox, QFormLayout, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

TABLO_STIL = """
QTableWidget { background-color: white; color: #0A1F5C; border-radius: 8px; border: 1px solid #DCE7FF; }
QTableWidget::item { color: #0A1F5C; padding: 5px; border-bottom: 1px solid #F0F4F8; }
QHeaderView::section { background-color: #0A1F5C; color: white; padding: 12px; font-weight: bold; border: none; }
"""

class ArizaBildirimFormu(QDialog):
    """Yeni Cihaz Arıza Bildirimi Oluşturma Ekranı (FAIL-002)"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        
        self.setWindowTitle("⚠️ Yeni Arıza Bildirimi")
        self.setMinimumSize(450, 400)
        self.setStyleSheet("""
            QDialog { 
                background-color: #F8F9FA; 
            }
            QLabel { 
                color: #2C3E50; 
                font-family: 'Segoe UI', Arial; 
                font-size: 13px; 
                font-weight: bold; 
            }
            QLineEdit, QTextEdit, QComboBox { 
                background-color: white; 
                color: #2C3E50; 
                border: 1px solid #BDC3C7; 
                border-radius: 4px; 
                padding: 6px; 
                font-family: 'Segoe UI', Arial; 
                font-size: 13px;
            }
            QLineEdit:read-only { 
                background-color: #EAECEE; 
                color: #7F8C8D; 
            }
            QMessageBox { 
                background-color: white; 
            }
        """)
        layout = QVBoxLayout(self)
        
        bilgi = QLabel("Arızalanan cihazı ve sorunun detaylarını giriniz.\nBu cihaz otomatik olarak 'Arızalı' durumuna geçecektir.")
        bilgi.setStyleSheet("background-color: #FDEDED; color: #E74C3C; padding: 10px; border-radius: 5px; border: 1px solid #F5B7B1; font-weight: bold;")
        bilgi.setWordWrap(True)
        layout.addWidget(bilgi)

        form_layout = QFormLayout()
        
        # 1. Cihaz Seçimi
        self.cmb_cihaz = QComboBox()
        self.cmb_cihaz.setStyleSheet("padding: 5px; border-radius: 4px; border: 1px solid #BDC3C7;")
        self.cihazlari_yukle()
        
        # 2. Aciliyet Seçimi
        self.cmb_aciliyet = QComboBox()
        self.cmb_aciliyet.addItems(["Düşük", "Orta", "Yüksek", "Kritik"])
        self.cmb_aciliyet.setStyleSheet("padding: 5px; border-radius: 4px; border: 1px solid #BDC3C7;")
        
        # 3. Arıza Başlığı
        self.txt_baslik = QLineEdit()
        self.txt_baslik.setPlaceholderText("Örn: Güç kablosu temassızlığı")
        self.txt_baslik.setStyleSheet("padding: 6px; border-radius: 4px; border: 1px solid #BDC3C7;")
        
        # 4. Arıza Açıklaması
        self.txt_aciklama = QTextEdit()
        self.txt_aciklama.setPlaceholderText("Arızanın detaylarını, ne zaman fark edildiğini vb. belirtiniz...")
        self.txt_aciklama.setStyleSheet("padding: 6px; border-radius: 4px; border: 1px solid #BDC3C7;")
        self.txt_aciklama.setMaximumHeight(100)

        form_layout.addRow("Arızalı Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Aciliyet Seviyesi (*):", self.cmb_aciliyet)
        form_layout.addRow("Sorun Başlığı (*):", self.txt_baslik)
        form_layout.addRow("Açıklama (*):", self.txt_aciklama)
        
        layout.addLayout(form_layout)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        self.btn_kaydet = QPushButton("🚨 Arızayı Bildir")
        self.btn_kaydet.setStyleSheet("background-color: #E74C3C; color: white; padding: 10px 15px; border-radius: 6px; font-weight: bold; font-size: 14px;")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_kaydet)
        
        layout.addLayout(btn_layout)

    def cihazlari_yukle(self):
        """Sadece 'Kullanılabilir' ve 'Rezerve' durumdaki cihazları listeler."""
        self.cmb_cihaz.clear()
        try:
            cevap = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                aktif_cihaz_var_mi = False
                for cihaz in cevap.json():
                    # Zaten arızalı veya bakımda olan cihaza yeni arıza kaydı açılamaz
                    if cihaz["durum"] in ["Kullanima_Hazir", "Kullanılabilir", "Rezerve"]:
                        self.cmb_cihaz.addItem(f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}", cihaz["cihaz_id"])
                        aktif_cihaz_var_mi = True
                
                if not aktif_cihaz_var_mi:
                    self.cmb_cihaz.addItem("Arıza bildirilebilecek cihaz bulunamadı!", None)
                    self.btn_kaydet.setEnabled(False)
        except:
            self.cmb_cihaz.addItem("Cihazlar Yüklenemedi!", None)

    def kaydet(self):
        cihaz_id = self.cmb_cihaz.currentData()
        baslik = self.txt_baslik.text().strip()
        aciklama = self.txt_aciklama.toPlainText().strip()
        aciliyet = self.cmb_aciliyet.currentText()

        if not cihaz_id:
            QMessageBox.warning(self, "Hata", "Lütfen geçerli bir cihaz seçin.")
            return
        if not baslik or not aciklama:
            QMessageBox.warning(self, "Hata", "Lütfen arıza başlığı ve açıklama alanlarını doldurun.")
            return

        veri = {
            "cihaz_id": cihaz_id,
            "ariza_baslik": baslik,
            "ariza_aciklama": aciklama,
            "aciliyet": aciliyet
        }

        try:
            cevap = requests.post(f"{self.api_url}/api/arizalar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code in [200, 201]:
                QMessageBox.information(self, "Başarılı", "Arıza bildirimi oluşturuldu. Cihaz durumu otomatik olarak güncellendi.")
                self.accept()
            else:
                hata = str(cevap.json().get('detail', 'Bilinmeyen bir hata oluştu.'))
                QMessageBox.critical(self, "Hata", hata)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", "Sunucuya ulaşılamadı. Öğrenci C arıza endpoint'ini (POST /api/arizalar) henüz yazmamış olabilir.")

class ArizaYonetimEkrani(QWidget):
    """Ana Arıza Kayıtları Listesi Ekranı"""
    def __init__(self, api_url, token, yetkili_mi=False):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.yetkili_mi = yetkili_mi
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(7) 
        self.tablo.setHorizontalHeaderLabels(["Kayıt No", "Cihaz Adı", "Sorun Başlığı", "Aciliyet", "Durum", "Bildirim Tarihi", "İşlem"])
        
        # SÜTUN GENİŞLİKLERİ ÇÖZÜMÜ: Sadece başlık esnesin, diğerleri içeriğe göre genişlesin!
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Varsayılan olarak esne
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents) # Kayıt No dar olsun
        self.tablo.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents) # Aciliyet
        self.tablo.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents) # Durum sütunu yazıyı kesmesin
        self.tablo.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents) # Tarih
        self.tablo.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents) # İşlem butonu sığsın
        
        self.tablo.setStyleSheet(TABLO_STIL)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.verticalHeader().setDefaultSectionSize(55) # Butonlar rahat nefes alsın diye satırları biraz daha büyüttük
        self.tablo.verticalHeader().setVisible(False)
        
        layout.addWidget(self.tablo)
        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        self.ariza_detaylari = {}
        try:
            cevap = requests.get(f"{self.api_url}/api/arizalar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                arizalar = cevap.json()
                self.tablo.setRowCount(len(arizalar))
                for satir, ar in enumerate(arizalar):
                    self.ariza_detaylari[ar.get("ariza_id")] = ar
                    self.tablo.setItem(satir, 0, QTableWidgetItem(str(ar.get("ariza_id", ""))))
                    self.tablo.setItem(satir, 1, QTableWidgetItem(str(ar.get("cihaz_adi", "Bilinmeyen"))))
                    self.tablo.setItem(satir, 2, QTableWidgetItem(ar.get("ariza_baslik", "")))
                    
                    aciliyet_item = QTableWidgetItem(ar.get("aciliyet", ""))
                    if ar.get("aciliyet") == "Kritik":
                        aciliyet_item.setForeground(Qt.red)
                        aciliyet_item.setFont(QFont("Arial", 10, QFont.Bold))
                    elif ar.get("aciliyet") == "Yüksek":
                        aciliyet_item.setForeground(QColor("#E67E22")) 
                    self.tablo.setItem(satir, 3, aciliyet_item)
                    
                    # DURUM RENKLENDİRMESİ VE BOYUTLANDIRMASI
                    durum_metni = ar.get("durum", "Açık")
                    lbl_durum = QLabel()
                    lbl_durum.setAlignment(Qt.AlignCenter)
                    lbl_durum.setFont(QFont("Arial", 10, QFont.Bold))
                    
                    if durum_metni == "Çözüldü":
                        lbl_durum.setText("🟢 Arıza Düzeltildi")
                        lbl_durum.setStyleSheet("color: #27AE60; background-color: #EAFAF1; border-radius: 12px; padding: 6px 12px;")
                    else:
                        lbl_durum.setText("🔴 Arıza Düzeltilmedi")
                        lbl_durum.setStyleSheet("color: #E74C3C; background-color: #FDEDED; border-radius: 12px; padding: 6px 12px;")
                    
                    # Yazının kesinlikle kırpılmaması için minimum genişlik verdik
                    lbl_durum.setMinimumWidth(150)
                    
                    durum_widget = QWidget()
                    durum_layout = QHBoxLayout(durum_widget)
                    durum_layout.setContentsMargins(5, 2, 5, 2)
                    durum_layout.setAlignment(Qt.AlignCenter)
                    durum_layout.addWidget(lbl_durum)
                    self.tablo.setCellWidget(satir, 4, durum_widget)
                    
                    self.tablo.setItem(satir, 5, QTableWidgetItem(ar.get("bildirim_tarihi", "")[:16].replace("T", " ")))
                    
                    # DÜZENLE / ÇÖZÜLDÜ BUTONU
                    if self.yetkili_mi and durum_metni != "Çözüldü":
                        btn_coz = QPushButton("🔧 Düzenle / Çöz")
                        btn_coz.setStyleSheet("""
                            QPushButton { background-color: #3498DB; color: white; border-radius: 6px; padding: 8px 12px; font-weight: bold; font-size: 12px; }
                            QPushButton:hover { background-color: #2980B9; }
                        """)
                        btn_coz.setMinimumWidth(120) # Butonun kırpılmasını engeller
                        btn_coz.setCursor(Qt.PointingHandCursor)
                        btn_coz.clicked.connect(lambda checked=False, a_id=ar.get("ariza_id"): self.ariza_duzenle_form_ac(a_id))                        
                        btn_widget = QWidget()
                        btn_layout = QHBoxLayout(btn_widget)
                        btn_layout.setContentsMargins(5, 2, 5, 2)
                        btn_layout.setAlignment(Qt.AlignCenter)
                        btn_layout.addWidget(btn_coz)
                        self.tablo.setCellWidget(satir, 6, btn_widget)
                    else:
                        self.tablo.setItem(satir, 6, QTableWidgetItem(""))
        except Exception as e:
            print(f"Tablo yüklenirken hata: {str(e)}")

    def ariza_duzenle_form_ac(self, ariza_id):
        secili_ariza = self.ariza_detaylari.get(ariza_id)
        if secili_ariza:
            form = ArizaDuzenleFormu(self.api_url, self.token, secili_ariza, self)
            if form.exec():
                self.verileri_yukle()

    def yeni_ariza_bildirimi(self):
        form = ArizaBildirimFormu(self.api_url, self.token)
        if form.exec():
            self.verileri_yukle()

class ArizaDuzenleFormu(QDialog):
    """Mevcut Arızayı Düzenleme ve Çözme Ekranı"""
    def __init__(self, api_url, token, ariza_verisi, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.ariza_verisi = ariza_verisi
        
        self.setWindowTitle(f"🔧 Arıza Düzenle - {ariza_verisi['cihaz_adi']}")
        self.setMinimumSize(450, 420)
        
        # 1. ADIM: Pencereye benzersiz bir kimlik (ID) veriyoruz
        self.setObjectName("DuzenleKutusu")
        
        # 2. ADIM: Nükleer CSS Zırhı! (Başına '#' koyarak Windows'un bunu ezmesini imkansız kılıyoruz)
        self.setStyleSheet("""
            QDialog#DuzenleKutusu { 
                background-color: #F8F9FA; 
            }
            QLabel { 
                color: #0A1F5C; 
                font-family: 'Segoe UI', Arial; 
                font-size: 13px; 
                font-weight: bold; 
                background: transparent;
            }
            QLineEdit, QTextEdit, QComboBox { 
                background-color: #FFFFFF; 
                color: #0A1F5C; 
                border: 1px solid #BDC3C7; 
                border-radius: 4px; 
                padding: 6px; 
                font-family: 'Segoe UI', Arial; 
                font-size: 13px;
            }
            QLineEdit:read-only { 
                background-color: #EAECEE; 
                color: #7F8C8D; 
            }
            QMessageBox { 
                background-color: #FFFFFF; 
            }
        """)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Alt elemanlardaki 'setStyleSheet' kodlarını SİLDİK ki üstteki zırhı delmesinler!
        
        # 1. Cihaz Adı
        self.lbl_cihaz = QLineEdit(self.ariza_verisi["cihaz_adi"])
        self.lbl_cihaz.setReadOnly(True)
        
        # 2. Aciliyet
        self.cmb_aciliyet = QComboBox()
        self.cmb_aciliyet.addItems(["Düşük", "Orta", "Yüksek", "Kritik"])
        self.cmb_aciliyet.setCurrentText(self.ariza_verisi.get("aciliyet", "Orta"))
        
        # 3. Başlık
        self.txt_baslik = QLineEdit(self.ariza_verisi.get("ariza_baslik", ""))
        
        # 4. Açıklama
        self.txt_aciklama = QTextEdit(self.ariza_verisi.get("ariza_aciklama", ""))
        self.txt_aciklama.setMaximumHeight(100)
        
        # 5. DURUM
        self.cmb_durum = QComboBox()
        self.cmb_durum.addItems(["🔴 Açık (Devam Ediyor)", "🟢 Çözüldü (Cihazı Aç)"])
        if self.ariza_verisi.get("durum") == "Çözüldü":
            self.cmb_durum.setCurrentIndex(1)
        # Buna özel stil veriyoruz ama arka planı zorla beyaz yapıyoruz
        self.cmb_durum.setStyleSheet("background-color: #FFFFFF; border: 2px solid #3498DB; font-weight: bold; color: #0A1F5C;")

        form_layout.addRow("Cihaz:", self.lbl_cihaz)
        form_layout.addRow("Aciliyet Seviyesi:", self.cmb_aciliyet)
        form_layout.addRow("Sorun Başlığı:", self.txt_baslik)
        form_layout.addRow("Açıklama:", self.txt_aciklama)
        form_layout.addRow("Mevcut Durum:", self.cmb_durum)
        
        layout.addLayout(form_layout)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        self.btn_kaydet = QPushButton("💾 Güncelle")
        self.btn_kaydet.setStyleSheet("background-color: #2980B9; color: white; padding: 10px 15px; border-radius: 6px; font-weight: bold; font-size: 14px;")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_kaydet)
        
        layout.addLayout(btn_layout)

    def kaydet(self):
        baslik = self.txt_baslik.text().strip()
        aciklama = self.txt_aciklama.toPlainText().strip()
        
        if not baslik or not aciklama:
            QMessageBox.warning(self, "Hata", "Başlık ve açıklama boş bırakılamaz.")
            return

        veri = {
            "ariza_baslik": baslik,
            "ariza_aciklama": aciklama,
            "aciliyet": self.cmb_aciliyet.currentText(),
            "cozuldu_mu": True if "Çözüldü" in self.cmb_durum.currentText() else False
        }

        try:
            cevap = requests.put(
                f"{self.api_url}/api/arizalar/{self.ariza_verisi['ariza_id']}", 
                json=veri, 
                headers={"Authorization": f"Bearer {self.token}"}
            )
            if cevap.status_code == 200:
                basari = QMessageBox(self)
                basari.setWindowTitle("Başarılı")
                basari.setText("✅ Arıza kaydı başarıyla güncellendi!")
                basari.setStyleSheet("QMessageBox { background-color: #FFFFFF; } QLabel { color: #27AE60; font-size: 13px; font-weight: bold; } QPushButton { background-color: #27AE60; color: white; padding: 6px 15px; border-radius: 4px; font-weight: bold; }")
                basari.exec()
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", f"İşlem reddedildi. Kod: {cevap.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucuya bağlanılamadı: {str(e)}")