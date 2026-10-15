import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
                               QComboBox, QMessageBox, QDateTimeEdit, QDialog, 
                               QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                               QAbstractItemView, QPushButton, QLineEdit)
from PySide6.QtCore import QDateTime, Signal, Qt
from PySide6.QtGui import QColor

from istemci_modelleri import IstemciRandevu 
from ui_components import StandartButon

# ======================================================================
#  APT-002: YENİ RANDEVU OLUŞTURMA FORMU
# ======================================================================
class RandevuOlusturFormu(QWidget):
    def __init__(self, api_url, token, mevcut_psikolog_id):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.tum_odalar = [] 
        
        self.setWindowTitle("Yeni Randevu Oluştur (APT-002)")
        self.resize(480, 360)
        self.init_ui()
        
        self.odalari_yukle()
        self.psikologlari_yukle() 
        self.siradaki_kodu_getir()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox, QDateTimeEdit { 
                padding: 9px; border-radius: 6px; border: 1px solid #CBD5E1; 
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus { border: 2px solid #2563EB; }
            QComboBox QAbstractItemView { background-color: white; color: #0F2552; selection-background-color: #2563EB; selection-color: white; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(15, 15, 15, 15)
        ana_layout.setSpacing(15)

        # Lacivert Üst Başlık Kartı
        baslik_frame = QFrame() if 'QFrame' in globals() else QWidget() # Güvenli yapı
        # Alternatif düzgün başlık tasarımı için QFrame:
        from PySide6.QtWidgets import QFrame
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(15, 12, 15, 12)
        
        lbl_ikon = QLabel("📅")
        lbl_ikon.setStyleSheet("font-size: 18px; background: transparent;")
        lbl_baslik = QLabel("Yeni Randevu Oluştur")
        lbl_baslik.setStyleSheet("color: white; font-size: 15px; font-weight: bold; background: transparent;")
        
        baslik_layout.addWidget(lbl_ikon)
        baslik_layout.addWidget(lbl_baslik)
        baslik_layout.addStretch()
        ana_layout.addWidget(baslik_frame)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.txt_danisan_kodu = QLineEdit()
        self.txt_danisan_kodu.setReadOnly(True)
        self.txt_danisan_kodu.setStyleSheet("background-color: #E2E8F0; color: #1E3A8A; font-weight: bold; padding: 9px; border-radius: 6px;")
        form_layout.addRow("Danışan Kodu:", self.txt_danisan_kodu)

        self.cmb_psikologlar = QComboBox()
        form_layout.addRow("Psikolog Seçiniz:", self.cmb_psikologlar)

        self.cmb_odalar = QComboBox()
        form_layout.addRow("Görüşme Odası:", self.cmb_odalar)

        self.dt_baslangic = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_baslangic.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Başlangıç:", self.dt_baslangic)

        self.dt_bitis = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.dt_bitis.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Bitiş:", self.dt_bitis)

        ana_layout.addLayout(form_layout)

        # Alt Butonlar
        buton_layout = QHBoxLayout()
        buton_layout.addStretch()

        btn_iptal = QPushButton("İptal")
        btn_iptal.setFixedWidth(90)
        btn_iptal.setStyleSheet("background-color: #E2E8F0; color: #0F2552; border-radius: 6px; padding: 8px; font-weight: bold;")
        btn_iptal.clicked.connect(self.close)

        self.btn_kaydet = QPushButton("Randevuyu Kaydet")
        self.btn_kaydet.setFixedWidth(160)
        self.btn_kaydet.setStyleSheet("background-color: #2563EB; color: white; border-radius: 6px; padding: 8px; font-weight: bold;")
        self.btn_kaydet.clicked.connect(self.randevuyu_kaydet)

        buton_layout.addWidget(btn_iptal)
        buton_layout.addWidget(self.btn_kaydet)
        ana_layout.addLayout(buton_layout)

    def siradaki_kodu_getir(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/randevular/siradaki-kod", headers=headers, timeout=5)
            if cevap.status_code == 200:
                veri = cevap.json()
                self.txt_danisan_kodu.setText(veri["siradaki_kod"])
            else:
                self.txt_danisan_kodu.setText("DAN-OTOMATIK-ATANACAK")
        except Exception:
            self.txt_danisan_kodu.setText("DAN-OTOMATIK-ATANACAK")

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                self.tum_odalar = cevap.json()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def psikologlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for psi in cevap.json():
                    self.cmb_psikologlar.addItem(psi["ad_soyad"], psi["personel_id"])
                
                self.cmb_psikologlar.currentIndexChanged.connect(self.odalari_filtrele)
                
                if self.mevcut_psikolog_id is not None:
                    index = self.cmb_psikologlar.findData(self.mevcut_psikolog_id)
                    if index >= 0:
                        self.cmb_psikologlar.setCurrentIndex(index)
                        self.cmb_psikologlar.setEnabled(False)
                
                self.odalari_filtrele()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikologlar yüklenemedi: {str(e)}")

    def odalari_filtrele(self):
        self.cmb_odalar.clear()
        if not self.tum_odalar: return
            
        secilen_psikolog_adi = self.cmb_psikologlar.currentText().lower().replace(" ", "")
        
        for oda in self.tum_odalar:
            if not oda["aktif_mi"]: continue
                
            oda_adi = oda["oda_adi"].lower()
            ekle = False
            
            if "psikolog1" in secilen_psikolog_adi:
                if ("görüşme" in oda_adi and "1" in oda_adi) or "sanat" in oda_adi:
                    ekle = True
            elif "psikolog2" in secilen_psikolog_adi:
                if ("görüşme" in oda_adi and "2" in oda_adi) or "sanat" in oda_adi or "oyun" in oda_adi:
                    ekle = True
            else:
                if "görüşme" in oda_adi or "terapi" in oda_adi:
                    ekle = True
                    
            if ekle:
                self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])

    def randevuyu_kaydet(self):
        secilen_oda_id = self.cmb_odalar.currentData()
        secilen_psikolog_id = self.cmb_psikologlar.currentData()
        
        if secilen_psikolog_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir psikolog seçiniz.")
            return
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen geçerli bir görüşme odası seçiniz.")
            return
        if self.dt_baslangic.dateTime() >= self.dt_bitis.dateTime():
            QMessageBox.warning(self, "Geçersiz Zaman", "Bitiş zamanı başlangıç zamanından sonra olmalıdır!")
            return

        baslangic_str = self.dt_baslangic.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        bitis_str = self.dt_bitis.dateTime().toString("yyyy-MM-ddTHH:mm:ss")

        yeni_randevu = IstemciRandevu(
            danisan_kod_id=self.txt_danisan_kodu.text(),
            psikolog_id=secilen_psikolog_id,
            oda_id=secilen_oda_id,
            baslangic_zamani=baslangic_str,
            bitis_zamani=bitis_str
        )

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.post(f"{self.api_url}/api/randevular", 
                                json=yeni_randevu.to_dict(), 
                                headers=headers, timeout=5)
            
            if cevap.status_code == 201:
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla oluşturuldu!")
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen psikolog veya oda bu saatlerde dolu!")
            else:
                hata_mesaji = "Bilinmeyen bir sunucu hatası oluştu."
                try:
                    hata_mesaji = cevap.json().get('detail', hata_mesaji)
                except ValueError:
                    hata_mesaji = f"Sunucu hatası: {cevap.status_code}"
                QMessageBox.warning(self, "Hata", f"İşlem başarısız: {hata_mesaji}")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", str(e))


# ======================================================================
#  APT-003 & APT-004: MEVCUT RANDEVUYU DÜZENLEME VE İPTAL FORMU
# ======================================================================
class RandevuDuzenleFormu(QWidget):
    veriler_degisti = Signal()

    def __init__(self, api_url, token, mevcut_psikolog_id, randevu_id, eski_veriler):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.randevu_id = randevu_id
        self.eski_veriler = eski_veriler 
        self.tum_odalar = []
        
        self.setWindowTitle(f"Randevu Yönetimi (ID: {self.randevu_id})")
        self.resize(480, 360)
        
        self.init_ui()
        self.odalari_yukle() 
        self.psikologlari_yukle() 
        self.eski_verileri_arayuze_bas()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox, QDateTimeEdit { 
                padding: 9px; border-radius: 6px; border: 1px solid #CBD5E1; 
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus { border: 2px solid #2563EB; }
            QComboBox QAbstractItemView { background-color: white; color: #0F2552; selection-background-color: #2563EB; selection-color: white; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(15, 15, 15, 15)
        ana_layout.setSpacing(15)

        # Lacivert Üst Başlık Kartı
        from PySide6.QtWidgets import QFrame
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(15, 12, 15, 12)
        
        lbl_ikon = QLabel("✎")
        lbl_ikon.setStyleSheet("font-size: 18px; color: white; background: transparent;")
        lbl_baslik = QLabel(f"Randevu Yönetimi (ID: {self.randevu_id})")
        lbl_baslik.setStyleSheet("color: white; font-size: 15px; font-weight: bold; background: transparent;")
        
        baslik_layout.addWidget(lbl_ikon)
        baslik_layout.addWidget(lbl_baslik)
        baslik_layout.addStretch()
        ana_layout.addWidget(baslik_frame)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.txt_danisan_kodu = QLineEdit()
        self.txt_danisan_kodu.setReadOnly(True)
        self.txt_danisan_kodu.setStyleSheet("background-color: #E2E8F0; color: #1E3A8A; font-weight: bold; padding: 9px; border-radius: 6px;")
        form_layout.addRow("Danışan Kodu:", self.txt_danisan_kodu)

        self.cmb_psikologlar = QComboBox()
        self.cmb_psikologlar.setEnabled(False)
        form_layout.addRow("Psikolog:", self.cmb_psikologlar)

        self.cmb_odalar = QComboBox()
        form_layout.addRow("Görüşme Odası:", self.cmb_odalar)

        self.dt_baslangic = QDateTimeEdit()
        self.dt_baslangic.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Başlangıç:", self.dt_baslangic)

        self.dt_bitis = QDateTimeEdit()
        self.dt_bitis.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Bitiş:", self.dt_bitis)

        ana_layout.addLayout(form_layout)

        # Alt Butonlar (Güncelle, İptal Et)
        buton_layout = QHBoxLayout()
        
        self.btn_guncelle = QPushButton("Değişiklikleri Kaydet")
        self.btn_guncelle.setStyleSheet("background-color: #F59E0B; color: white; border-radius: 6px; padding: 9px; font-weight: bold;")
        self.btn_guncelle.clicked.connect(self.randevuyu_guncelle)
        
        self.btn_iptal = QPushButton("Randevuyu İptal Et")
        self.btn_iptal.setStyleSheet("background-color: #DC2626; color: white; border-radius: 6px; padding: 9px; font-weight: bold;")
        self.btn_iptal.clicked.connect(self.randevuyu_iptal_et)
        
        buton_layout.addWidget(self.btn_guncelle)
        buton_layout.addWidget(self.btn_iptal)
        ana_layout.addLayout(buton_layout)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                self.tum_odalar = cevap.json()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def psikologlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for psi in cevap.json():
                    self.cmb_psikologlar.addItem(psi["ad_soyad"], psi["personel_id"])
                
                index = self.cmb_psikologlar.findData(self.eski_veriler["psikolog_id"])
                if index >= 0:
                    self.cmb_psikologlar.setCurrentIndex(index)
                    
                self.odalari_filtrele()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikologlar yüklenemedi: {str(e)}")

    def odalari_filtrele(self):
        self.cmb_odalar.clear()
        if not self.tum_odalar: return
            
        secilen_psikolog_adi = self.cmb_psikologlar.currentText().lower().replace(" ", "")
        
        for oda in self.tum_odalar:
            if not oda["aktif_mi"]: continue
                
            oda_adi = oda["oda_adi"].lower()
            ekle = False
            
            if "psikolog1" in secilen_psikolog_adi:
                if ("görüşme" in oda_adi and "1" in oda_adi) or "sanat" in oda_adi:
                    ekle = True
            elif "psikolog2" in secilen_psikolog_adi:
                if ("görüşme" in oda_adi and "2" in oda_adi) or "sanat" in oda_adi or "oyun" in oda_adi:
                    ekle = True
            else:
                if "görüşme" in oda_adi or "terapi" in oda_adi:
                    ekle = True
                    
            if ekle:
                self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])

    def eski_verileri_arayuze_bas(self):
        self.txt_danisan_kodu.setText(self.eski_veriler["danisan_kod_id"])
        
        oda_index = self.cmb_odalar.findData(self.eski_veriler["oda_id"])
        if oda_index >= 0:
            self.cmb_odalar.setCurrentIndex(oda_index)
            
        fmt = "yyyy-MM-ddTHH:mm:ss"
        self.dt_baslangic.setDateTime(QDateTime.fromString(self.eski_veriler["baslangic_zamani"].split('.')[0], fmt))
        self.dt_bitis.setDateTime(QDateTime.fromString(self.eski_veriler["bitis_zamani"].split('.')[0], fmt))

    def randevuyu_guncelle(self):
        secilen_oda_id = self.cmb_odalar.currentData()
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir görüşme odası seçiniz.")
            return
        if self.dt_baslangic.dateTime() >= self.dt_bitis.dateTime():
            QMessageBox.warning(self, "Geçersiz Zaman", "Bitiş zamanı başlangıç zamanından sonra olmalıdır!")
            return

        guncel_veriler = {
            "danisan_kod_id": self.txt_danisan_kodu.text(),
            "psikolog_id": self.eski_veriler["psikolog_id"],
            "oda_id": secilen_oda_id,
            "baslangic_zamani": self.dt_baslangic.dateTime().toString("yyyy-MM-ddTHH:mm:ss"),
            "bitis_zamani": self.dt_bitis.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.patch(f"{self.api_url}/api/randevular/{self.randevu_id}", 
                                  json=guncel_veriler, headers=headers, timeout=5)
            
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla güncellendi!")
                self.veriler_degisti.emit() 
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen saatte oda veya psikolog dolu!")
            else:
                QMessageBox.warning(self, "Hata", f"Güncellenemedi: {cevap.json().get('detail')}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

    def randevuyu_iptal_et(self):
        cevap = QMessageBox.question(self, "İptal Onayı", 
                                   "Bu randevuyu iptal etmek istediğinize emin misiniz? Bu işlem geri alınamaz.",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if cevap == QMessageBox.No: return

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            yanit = requests.patch(f"{self.api_url}/api/randevular/{self.randevu_id}/iptal", 
                                     headers=headers, timeout=5)
            
            if yanit.status_code == 200:
                QMessageBox.information(self, "İptal Edildi", "Randevu başarıyla iptal edildi.")
                self.veriler_degisti.emit() 
                self.close()
            else:
                QMessageBox.warning(self, "Hata", f"İptal işlemi başarısız: {yanit.json().get('detail')}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen bir hata oluştu: {str(e)}")


# ======================================================================
#  RANDEVU ANA EKRANI (TABLO GÖRÜNÜMÜ VE DOĞRUDAN DÜZENLEME MANTIĞI)
# ======================================================================
class RandevuAnaEkrani(QWidget):
    def __init__(self, api_url, token, mevcut_psikolog_id):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(6)
        self.tablo.setHorizontalHeaderLabels(["Randevu ID", "Danışan Kodu", "Oda", "Başlangıç", "Bitiş", "Durum"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #D0D7E5; border-radius: 8px; gridline-color: #E2E8F0; }
            QHeaderView::section { background-color: #0A1F5C; color: white; font-weight: bold; padding: 10px; border: none; }
        """)
        layout.addWidget(self.tablo)
        
        self.verileri_cek()

    def verileri_cek(self):
        self.tablo.setRowCount(0)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/randevular", headers=headers, timeout=5)
            if cevap.status_code == 200:
                self.randevular = cevap.json()
                self.tablo.setRowCount(len(self.randevular))
                for satir, r in enumerate(self.randevular):
                    baslangic = r.get("baslangic_zamani", "").replace("T", " ")
                    bitis = r.get("bitis_zamani", "").replace("T", " ")
                    
                    item_id = QTableWidgetItem(str(r.get("randevu_id", "")))
                    item_kod = QTableWidgetItem(r.get("danisan_kod_id", ""))
                    item_oda = QTableWidgetItem(str(r.get("oda_id", "Bilinmiyor"))) 
                    item_bas = QTableWidgetItem(baslangic)
                    item_bit = QTableWidgetItem(bitis)
                    
                    durum_metni = r.get("durum", "")
                    item_durum = QTableWidgetItem(durum_metni)
                    
                    if durum_metni == "IPTAL_EDILDI":
                        item_durum.setForeground(QColor("#DC2626"))
                    elif durum_metni == "PLANLANDI":
                        item_durum.setForeground(QColor("#10B981"))
                    else:
                        item_durum.setForeground(QColor("#2563EB"))
                        
                    for item in [item_id, item_kod, item_oda, item_bas, item_bit, item_durum]:
                        item.setTextAlignment(Qt.AlignCenter)
                        
                    self.tablo.setItem(satir, 0, item_id)
                    self.tablo.setItem(satir, 1, item_kod)
                    self.tablo.setItem(satir, 2, item_oda)
                    self.tablo.setItem(satir, 3, item_bas)
                    self.tablo.setItem(satir, 4, item_bit)
                    self.tablo.setItem(satir, 5, item_durum)
        except Exception as e:
            print("Randevular çekilirken hata oluştu:", e)

    def duzenle_secilen(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        if not secili_satirlar:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen düzenlemek istediğiniz randevuyu tablodan seçin.")
            return
            
        satir = secili_satirlar[0].row()
        randevu_id = int(self.tablo.item(satir, 0).text())
        durum = self.tablo.item(satir, 5).text()
        
        if durum == "IPTAL_EDILDI":
            QMessageBox.warning(self, "Uyarı", "İptal edilmiş bir randevuyu düzenleyemezsiniz.")
            return
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/randevular", headers=headers, timeout=5)
            if cevap.status_code == 200:
                secili_randevu = next((r for r in cevap.json() if r["randevu_id"] == randevu_id), None)
                if secili_randevu:
                    self.duzenle_formu = RandevuDuzenleFormu(
                        api_url=self.api_url, token=self.token, 
                        mevcut_psikolog_id=self.mevcut_psikolog_id,
                        randevu_id=randevu_id, eski_veriler=secili_randevu
                    )
                    self.duzenle_formu.veriler_degisti.connect(self.verileri_cek)
                    self.duzenle_formu.show()
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Randevu bilgileri alınamadı: {str(e)}")

    def iptal_et_secilen(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        if not secili_satirlar:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen iptal etmek istediğiniz randevuyu tablodan seçin.")
            return
            
        satir = secili_satirlar[0].row()
        randevu_id = int(self.tablo.item(satir, 0).text())
        durum = self.tablo.item(satir, 5).text()
        
        if durum == "IPTAL_EDILDI":
            QMessageBox.information(self, "Bilgi", "Bu randevu zaten iptal edilmiş.")
            return
            
        onay = QMessageBox.question(self, "İptal Onayı", "Seçili randevuyu iptal etmek istediğinize emin misiniz?", 
                                    QMessageBox.Yes | QMessageBox.No)
        
        if onay == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            try:
                cevap = requests.patch(f"{self.api_url}/api/randevular/{randevu_id}/iptal", headers=headers, timeout=5)
                if cevap.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Randevu iptal edildi.")
                    self.verileri_cek()
                else:
                    QMessageBox.warning(self, "Hata", "İşlem başarısız oldu.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")