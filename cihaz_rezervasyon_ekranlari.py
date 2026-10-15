import sys
import requests
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, 
    QComboBox, QMessageBox, QFormLayout, QDateTimeEdit
)
from PySide6.QtCore import Qt, QDateTime

TABLO_STIL = """
QTableWidget { background-color: white; color: #0A1F5C; border-radius: 8px; border: 1px solid #DCE7FF; }
QTableWidget::item { color: #0A1F5C; padding: 5px; }
QHeaderView::section { background-color: #0A1F5C; color: white; padding: 8px; font-weight: bold; }
"""

class RezervasyonFormu(QDialog):
    """Yeni Cihaz Rezervasyonu Oluşturma Ekranı (RES-002 & RES-003)"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        
        self.setWindowTitle("TKYS — Yeni Cihaz Rezervasyonu")
        self.setMinimumWidth(450)
        self.setStyleSheet("* { font-family: 'Segoe UI', Arial; font-size: 13px; }")

        layout = QVBoxLayout(self)
        
        # Üst Bilgi Kutusu
        bilgi = QLabel("📌 Lütfen rezerve etmek istediğiniz cihazı ve saat aralığını seçin. Sistem çakışmaları otomatik kontrol edecektir.")
        bilgi.setStyleSheet("background-color: #E8F0FE; color: #1A73E8; padding: 10px; border-radius: 5px; border: 1px solid #BBD0F7;")
        bilgi.setWordWrap(True)
        layout.addWidget(bilgi)

        form_layout = QFormLayout()
        
        # Cihaz Seçimi
        self.cmb_cihaz = QComboBox()
        self.cihazlari_yukle()
        
        # Tarih ve Saat Seçiciler (Takvim Entegrasyonu İçin Efsane UX)
        self.dt_baslangic = QDateTimeEdit()
        self.dt_baslangic.setCalendarPopup(True) # Açılır takvim!
        self.dt_baslangic.setDateTime(QDateTime.currentDateTime())
        
        self.dt_bitis = QDateTimeEdit()
        self.dt_bitis.setCalendarPopup(True)
        self.dt_bitis.setDateTime(QDateTime.currentDateTime().addSecs(3600)) # Varsayılan: 1 saat sonrası

        form_layout.addRow("Rezerve Edilecek Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Başlangıç Zamanı (*):", self.dt_baslangic)
        form_layout.addRow("Bitiş Zamanı (*):", self.dt_bitis)
        
        layout.addLayout(form_layout)
        
        # Butonlar
        btn_layout = QHBoxLayout()
        self.btn_kaydet = QPushButton("✅ Rezervasyonu Onayla")
        self.btn_kaydet.setStyleSheet("background-color: #27AE60; color: white; padding: 10px; border-radius: 5px; font-weight: bold; font-size: 14px;")
        self.btn_kaydet.setCursor(Qt.PointingHandCursor)
        self.btn_kaydet.clicked.connect(self.kaydet)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_kaydet)
        
        layout.addLayout(btn_layout)

    def cihazlari_yukle(self):
        """Sadece 'Kullanılabilir' olan cihazları listeye çeker."""
        self.cmb_cihaz.clear()
        try:
            cevap = requests.get(f"{self.api_url}/api/cihazlar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                aktif_cihaz_var_mi = False
                for cihaz in cevap.json():
                    # Sadece sağlam cihazlara rezervasyon yapılabilir!
# Sadece sağlam cihazlara rezervasyon yapılabilir!
                    # Veritabanından gelen durum "Kullanima_Hazir" veya "Kullanılabilir" olabilir, ikisini de kontrol et
                    if cihaz["durum"] in ["Kullanima_Hazir", "Kullanılabilir"]:
                        self.cmb_cihaz.addItem(f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}", cihaz["cihaz_id"])
                        aktif_cihaz_var_mi = True
                
                if not aktif_cihaz_var_mi:
                    self.cmb_cihaz.addItem("Uygun/Sağlam Cihaz Bulunamadı!", None)
                    self.btn_kaydet.setEnabled(False)
        except:
            self.cmb_cihaz.addItem("Cihazlar Yüklenemedi!", None)

    def kaydet(self):
        cihaz_id = self.cmb_cihaz.currentData()
        if not cihaz_id:
            QMessageBox.warning(self, "Hata", "Lütfen geçerli bir cihaz seçin.")
            return

        baslangic_str = self.dt_baslangic.dateTime().toString(Qt.ISODate)
        bitis_str = self.dt_bitis.dateTime().toString(Qt.ISODate)

        if self.dt_baslangic.dateTime() >= self.dt_bitis.dateTime():
            QMessageBox.warning(self, "Mantık Hatası", "Bitiş zamanı başlangıç zamanından önce veya aynı olamaz!")
            return

        veri = {
            "cihaz_id": cihaz_id,
            "baslangic_zamani": baslangic_str,
            "bitis_zamani": bitis_str,
            "aciklama": "Arayüzden oluşturuldu"
        }

        try:
            cevap = requests.post(f"{self.api_url}/api/rezervasyonlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            
            if cevap.status_code in [200, 201]:
                QMessageBox.information(self, "Başarılı", "Rezervasyon başarıyla oluşturuldu!")
                self.accept()
            elif cevap.status_code == 409: # Çakışma Hatası (Backend'den Gelecek)
                QMessageBox.critical(self, "ÇAKIŞMA TESPİT EDİLDİ", cevap.json().get('detail', 'Bu saatlerde cihaz zaten rezerve edilmiş!'))
            else:
                QMessageBox.critical(self, "Hata", cevap.json().get('detail', 'Bilinmeyen bir hata oluştu.'))
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", str(e))

class IptalOnayKutusu(QDialog):
    """Sıkıcı QMessageBox yerine geçen, son derece şık özel iptal onay ekranı"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ İptal Onayı")
        self.setFixedSize(420, 160)
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; border: 2px solid #E74C3C; border-radius: 8px; }
            QLabel { font-family: 'Segoe UI', Arial; font-size: 14px; color: #2C3E50; font-weight: bold; }
            QPushButton { font-family: 'Segoe UI'; font-size: 13px; font-weight: bold; border-radius: 6px; padding: 8px 15px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Şık Mesaj Metni
        lbl_mesaj = QLabel("Bu cihaz rezervasyonunu iptal etmek istediğinize\nkesinlikle emin misiniz?")
        lbl_mesaj.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_mesaj)
        
        lbl_alt_mesaj = QLabel("Bu işlem geri alınamaz ve loglara kaydedilecektir.")
        lbl_alt_mesaj.setStyleSheet("color: #7F8C8D; font-size: 11px; font-weight: normal;")
        lbl_alt_mesaj.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_alt_mesaj)

        layout.addSpacing(10)

        # Butonlar
        btn_layout = QHBoxLayout()
        
        self.btn_vazgec = QPushButton("Geri Dön")
        self.btn_vazgec.setStyleSheet("background-color: #BDC3C7; color: #2C3E50;")
        self.btn_vazgec.setCursor(Qt.PointingHandCursor)
        self.btn_vazgec.clicked.connect(self.reject) # Kapatır ve False döner
        
        self.btn_evet = QPushButton("❌ Evet, İptal Et")
        self.btn_evet.setStyleSheet("background-color: #E74C3C; color: white;")
        self.btn_evet.setCursor(Qt.PointingHandCursor)
        self.btn_evet.clicked.connect(self.accept) # Kapatır ve True döner
        
        btn_layout.addWidget(self.btn_vazgec)
        btn_layout.addWidget(self.btn_evet)
        layout.addLayout(btn_layout)

class RezervasyonYonetimEkrani(QWidget):
    """Ana Rezervasyon Listesi Ekranı"""
    def __init__(self, api_url, token, yetkili_mi=False):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.yetkili_mi = yetkili_mi
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tablo
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(["Rez. ID", "Cihaz Adı", "Başlangıç", "Bitiş", "Durum", "İşlem"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setStyleSheet(TABLO_STIL)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Satır yüksekliklerini artırıyoruz ki butonlar rahatça sığsın
        self.tablo.verticalHeader().setDefaultSectionSize(45) 
        self.tablo.verticalHeader().setVisible(False) # Sol taraftaki gereksiz 1, 2, 3 satır numaralarını gizliyoruz (daha şık)
        
        layout.addWidget(self.tablo)
        self.verileri_yukle()

    def verileri_yukle(self):
        self.tablo.setRowCount(0)
        try:
            # Backend'de henüz bu endpoint'i yazmadıysak 404 döner, şimdilik sadece try bloğunda
            cevap = requests.get(f"{self.api_url}/api/rezervasyonlar", headers={"Authorization": f"Bearer {self.token}"})
            if cevap.status_code == 200:
                rezervasyonlar = cevap.json()
                self.tablo.setRowCount(len(rezervasyonlar))
                for satir, rez in enumerate(rezervasyonlar):
                    self.tablo.setItem(satir, 0, QTableWidgetItem(str(rez.get("rezervasyon_id", ""))))
                    self.tablo.setItem(satir, 1, QTableWidgetItem(str(rez.get("cihaz_id", "Bilinmeyen Cihaz")))) # İleride cihaz adı gelecek
                    self.tablo.setItem(satir, 2, QTableWidgetItem(rez.get("baslangic_zamani", "").replace("T", " ")[:16]))
                    self.tablo.setItem(satir, 3, QTableWidgetItem(rez.get("bitis_zamani", "").replace("T", " ")[:16]))
                    
                    durum_hucre = QTableWidgetItem(rez.get("durum", "Aktif"))
                    if rez.get("durum") == "İptal Edildi":
                        durum_hucre.setForeground(Qt.red)
                    else:
                        durum_hucre.setForeground(Qt.darkGreen)
                    self.tablo.setItem(satir, 4, durum_hucre)

                    # Eğer iptal edilmemişse ve kullanıcının yetkisi varsa İptal butonu koy
                    if rez.get("durum") != "İptal Edildi" and self.yetkili_mi:
                        btn_iptal = QPushButton("❌ İptal Et")
                        # Butonu daha esnek, fontu biraz daha okunur ve yatayda ortalanmış yaptık
                        btn_iptal.setStyleSheet("""
                            QPushButton {
                                background-color: #E74C3C; 
                                color: white; 
                                border-radius: 6px; 
                                padding: 6px 10px; 
                                font-weight: bold;
                                font-size: 12px;
                            }
                            QPushButton:hover {
                                background-color: #C0392B;
                            }
                        """)
                        btn_iptal.setCursor(Qt.PointingHandCursor)
                        # Çift tıklama yerine normal tıklamada çalışması için:
                        btn_iptal.clicked.connect(lambda checked=False, r_id=rez.get("rezervasyon_id"): self.rezervasyon_iptal_et(r_id))
                        
                        hucre_widget = QWidget()
                        hucre_layout = QHBoxLayout(hucre_widget)
                        hucre_layout.setContentsMargins(5, 5, 5, 5) # Butonun etrafındaki boşlukları biraz artırdık
                        hucre_layout.addWidget(btn_iptal)
                        hucre_layout.setAlignment(Qt.AlignCenter)
                        self.tablo.setCellWidget(satir, 5, hucre_widget)
        except Exception as e:
            pass

    def yeni_rezervasyon_olustur(self):
        form = RezervasyonFormu(self.api_url, self.token)
        if form.exec():
            self.verileri_yukle()

    def rezervasyon_iptal_et(self, rezervasyon_id):
            # Klasik QMessageBox yerine kendi yaptığımız o harika ekranı çağırıyoruz
            onay_kutusu = IptalOnayKutusu(self)
            
            # Eğer kullanıcı "Evet, İptal Et" butonuna basarsa (accept)
            if onay_kutusu.exec():
                try:
                    res = requests.patch(f"{self.api_url}/api/rezervasyonlar/{rezervasyon_id}/iptal", headers={"Authorization": f"Bearer {self.token}"})
                    if res.status_code == 200:
                        # İşlem başarılıysa ekranı yenile
                        self.verileri_yukle()
                        
                        # Başarılı mesajını da şıklaştıralım
                        msg = QMessageBox(self)
                        msg.setWindowTitle("Başarılı")
                        msg.setText("✅ Rezervasyon başarıyla iptal edildi.")
                        msg.setStyleSheet("QMessageBox { background-color: white; } QLabel { color: #27AE60; font-size: 13px; font-weight: bold; } QPushButton { background-color: #27AE60; color: white; padding: 5px 15px; border-radius: 4px; }")
                        msg.exec()
                    else:
                        QMessageBox.warning(self, "Hata", "İptal işlemi reddedildi.")
                except:
                    QMessageBox.critical(self, "Hata", "Sunucuya bağlanılamadı.")