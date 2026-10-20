from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QDialog,
    QFormLayout, QComboBox, QDateEdit, QLineEdit, QTextEdit
)
from PySide6.QtCore import Qt, QDate
import requests

TABLO_STIL = """
QTableWidget { background-color: white; color: #0A1F5C; border-radius: 8px; border: 1px solid #DCE7FF; }
QTableWidget::item { color: #0A1F5C; padding: 5px; }
QHeaderView::section { background-color: #0A1F5C; color: white; padding: 8px; font-weight: bold; }
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QComboBox, QDateTimeEdit, 
    QLineEdit, QTextEdit, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QDateTime
import requests

class YeniRezervasyonFormu(QDialog):
    """Yeni Cihaz Rezervasyonu Oluşturma Ekranı (VIP UX Sürümü)"""
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        
        self.setWindowTitle("📅 Yeni Cihaz Rezervasyonu")
        self.setMinimumSize(500, 520)
        
        # WINDOWS KARANLIK MODUNU EZEN NÜKLEER CSS ZIRHI + TAKVİM TASARIMI
        self.setObjectName("RezervasyonKutusu")
        self.setStyleSheet("""
            QDialog#RezervasyonKutusu { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-family: 'Segoe UI', Arial; font-size: 13px; font-weight: bold; background: transparent; }
            QLineEdit, QTextEdit, QComboBox, QDateEdit { 
                background-color: #FFFFFF; color: #2C3E50; border: 1px solid #BDC3C7; 
                border-radius: 4px; padding: 6px; font-family: 'Segoe UI', Arial; font-size: 13px;
            }
            QComboBox:focus, QDateEdit:focus, QLineEdit:focus { border: 1px solid #3498DB; }
            QMessageBox { background-color: #FFFFFF; }
            QCalendarWidget QWidget { alternate-background-color: #EAECEE; }
        """)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setSpacing(15) # Satırlar arasına nefes alacak boşluk ekledik

        # 1. Cihaz Seçimi
        self.cmb_cihaz = QComboBox()
        
        # 2. Oda Seçimi
        self.cmb_oda = QComboBox()

        # SAAT LİSTESİ OLUŞTURMA (08:00 - 18:00 arası 30 dk aralıklarla klavyesiz seçim!)
        saatler = [f"{h:02d}:{m:02d}" for h in range(8, 19) for m in (0, 30)]

        # 3. Başlangıç Zamanı (Takvim + Saat Kutusu Yanyana)
        layout_baslangic = QHBoxLayout()
        self.dt_baslangic_tarih = QDateEdit(QDate.currentDate())
        self.dt_baslangic_tarih.setCalendarPopup(True) # Efsanevi Takvim Pop-up'ı
        self.cmb_baslangic_saat = QComboBox()
        self.cmb_baslangic_saat.addItems(saatler)
        self.cmb_baslangic_saat.setCurrentText("09:00")
        layout_baslangic.addWidget(self.dt_baslangic_tarih, stretch=2)
        layout_baslangic.addWidget(self.cmb_baslangic_saat, stretch=1)

        # 4. Bitiş Zamanı (Takvim + Saat Kutusu Yanyana)
        layout_bitis = QHBoxLayout()
        self.dt_bitis_tarih = QDateEdit(QDate.currentDate())
        self.dt_bitis_tarih.setCalendarPopup(True)
        self.cmb_bitis_saat = QComboBox()
        self.cmb_bitis_saat.addItems(saatler)
        self.cmb_bitis_saat.setCurrentText("10:00")
        layout_bitis.addWidget(self.dt_bitis_tarih, stretch=2)
        layout_bitis.addWidget(self.cmb_bitis_saat, stretch=1)

        # 5. Proje Bilgileri
        self.txt_proje_turu = QLineEdit()
        self.txt_proje_turu.setPlaceholderText("Örn: Araştırma, Bakım, Test...")
        
        self.txt_proje_aciklama = QTextEdit()
        self.txt_proje_aciklama.setMaximumHeight(80)
        self.txt_proje_aciklama.setPlaceholderText("Rezervasyon amacını kısaca belirtin...")

        form_layout.addRow("Rezerve Edilecek Cihaz (*):", self.cmb_cihaz)
        form_layout.addRow("Kullanılacak Oda (*):", self.cmb_oda)
        form_layout.addRow("Başlangıç Zamanı (*):", layout_baslangic)
        form_layout.addRow("Bitiş Zamanı (*):", layout_bitis)
        form_layout.addRow("Proje Türü:", self.txt_proje_turu)
        form_layout.addRow("Proje Açıklaması:", self.txt_proje_aciklama)

        layout.addLayout(form_layout)

        # 6. Onay Butonu
        self.btn_kaydet = QPushButton("✅ Rezervasyonu Onayla")
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
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # CİHAZLARI ÇEK
            res_cihaz = requests.get(f"{self.api_url}/api/cihazlar", headers=headers)
            if res_cihaz.status_code == 200:
                cihazlar = res_cihaz.json()
                
                # Filtreyi esnettik: Küçük/Büyük harf ve boşluk hatalarına karşı korumalı
                uygun_cihazlar = [c for c in cihazlar if str(c.get("durum", "")).strip().lower() in ["kullanima_hazir", "kullanıma hazır", "kullanılabilir"]]
                
                if uygun_cihazlar:
                    for c in uygun_cihazlar:
                        self.cmb_cihaz.addItem(f"{c['envanter_kodu']} - {c['cihaz_adi']}", c['cihaz_id'])
                else:
                    # Neden boş olduğunu kullanıcıya dürüstçe söylüyoruz
                    self.cmb_cihaz.addItem("Müsait Cihaz Yok (Hepsi dolu/arızalı)", None)
            else:
                self.cmb_cihaz.addItem("Sunucudan cihazlar alınamadı", None)

            # ODALARI ÇEK
            res_oda = requests.get(f"{self.api_url}/api/odalar", headers=headers)
            if res_oda.status_code == 200:
                odalar = res_oda.json()
                uygun_odalar = [o for o in odalar if o.get("aktif_mi")]
                if uygun_odalar:
                    for o in uygun_odalar:
                        self.cmb_oda.addItem(o["oda_adi"], o["oda_id"])
                else:
                    self.cmb_oda.addItem("Aktif oda bulunamadı", None)

        except Exception as e:
            QMessageBox.warning(self, "Bağlantı Hatası", "Sunucuya bağlanırken bir sorun oluştu.")

    def kaydet(self):
        cihaz_id = self.cmb_cihaz.currentData()
        oda_id = self.cmb_oda.currentData()

        if not cihaz_id or not oda_id:
            QMessageBox.warning(self, "Uyarı", "Geçerli bir cihaz veya oda seçilemedi. Envanteri kontrol edin.")
            return

        # Kullanıcının şık UI'dan seçtiği tarih ve saatleri birleştirip Backend'in anladığı formata (ISO 8601) çeviriyoruz
        bas_tarih = self.dt_baslangic_tarih.date().toString("yyyy-MM-dd")
        bas_saat = self.cmb_baslangic_saat.currentText()
        bas_iso = f"{bas_tarih}T{bas_saat}:00"

        bit_tarih = self.dt_bitis_tarih.date().toString("yyyy-MM-dd")
        bit_saat = self.cmb_bitis_saat.currentText()
        bit_iso = f"{bit_tarih}T{bit_saat}:00"

        veri = {
            "cihaz_id": cihaz_id,
            "kullanilacak_oda_id": oda_id,
            "baslangic_zamani": bas_iso,
            "bitis_zamani": bit_iso,
            "proje_turu": self.txt_proje_turu.text().strip(),
            "proje_adi_aciklamasi": self.txt_proje_aciklama.toPlainText().strip()
        }

        try:
            res = requests.post(f"{self.api_url}/api/rezervasyonlar", json=veri, headers={"Authorization": f"Bearer {self.token}"})
            if res.status_code == 201:
                basari = QMessageBox(self)
                basari.setWindowTitle("Başarılı")
                basari.setText("✅ Rezervasyon başarıyla oluşturuldu!")
                basari.setStyleSheet("QMessageBox { background-color: #FFFFFF; } QLabel { color: #27AE60; font-size: 13px; font-weight: bold; } QPushButton { background-color: #27AE60; color: white; padding: 6px 15px; border-radius: 4px; font-weight: bold; }")
                basari.exec()
                self.accept()
            else:
                hata_detay = res.json().get("detail", "Bilinmeyen bir hata oluştu.")
                QMessageBox.warning(self, "İşlem Başarısız", hata_detay)
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")

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
        form = YeniRezervasyonFormu(self.api_url, self.token)
        if form.exec():
            self.verileri_yukle() # Form başarıyla kapanırsa tabloyu yenile

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