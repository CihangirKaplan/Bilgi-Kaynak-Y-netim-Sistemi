import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, 
                               QComboBox, QMessageBox, QDateTimeEdit)
from PySide6.QtCore import QDateTime

# Kendi yazdığımız modeli (APT-001) içe aktarıyoruz
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
        
        self.setWindowTitle("Yeni Randevu Oluştur (APT-002)")
        self.resize(450, 250)
        self.init_ui()
        
        # Form açılırken verileri yükle (Ağ hatalarına karşı korumalı)
        self.odalari_yukle()
        self.danisanlari_yukle()

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # BEYAZ YAZI SORUNUNU ÇÖZEN STİL
        kutu_stili = """
            QComboBox { padding: 8px; border-radius: 6px; border: 2px solid #bdc3c7; background-color: white; color: black; }
            QComboBox QAbstractItemView { background-color: white; color: black; selection-background-color: #1A73E8; selection-color: white; }
            QLineEdit { color: black; }
        """

        # 1. DANIŞAN KODU (Hem Seçilebilir Hem Yazılabilir Yapıldı)
        self.cmb_danisan_kodu = QComboBox()
        self.cmb_danisan_kodu.setEditable(True)
        self.cmb_danisan_kodu.setStyleSheet(kutu_stili)
        self.cmb_danisan_kodu.lineEdit().setPlaceholderText("Örn: DAN-2026-0001 (Seçin veya yazın)")
        form_layout.addRow("Danışan Kodu:", self.cmb_danisan_kodu)

        # 2. ODA SEÇİMİ 
        self.cmb_odalar = QComboBox()
        self.cmb_odalar.setStyleSheet(kutu_stili)
        form_layout.addRow("Oda Seçiniz:", self.cmb_odalar)

        # Başlangıç ve Bitiş Zamanları
        self.dt_baslangic = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_baslangic.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Başlangıç:", self.dt_baslangic)

        self.dt_bitis = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.dt_bitis.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Bitiş:", self.dt_bitis)

        self.btn_kaydet = StandartButon("Randevuyu Kaydet")
        self.btn_kaydet.clicked.connect(self.randevuyu_kaydet)

        layout.addLayout(form_layout)
        layout.addWidget(self.btn_kaydet)
        self.setLayout(layout)

    def odalari_yukle(self):
        """API'den odaları çeker. Timeout ile donmaları önler."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                odalar = cevap.json()
                for oda in odalar:
                    if oda["aktif_mi"]:
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Zaman Aşımı", "Odalar yüklenirken sunucu yanıt vermedi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Odalar yüklenemedi: {str(e)}")

    def danisanlari_yukle(self):
        """API'den kayıtlı danışanları çekip ComboBox'a doldurur"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/danisan-kodlari", headers=headers, timeout=5)
            if cevap.status_code == 200:
                kodlar = cevap.json()
                for kod in kodlar:
                    self.cmb_danisan_kodu.addItem(kod["danisan_kod_id"])
        except Exception as e:
            # Bağlanamazsa bile sistem çökmez, kullanıcı klavyeyle kod yazabilir.
            QMessageBox.warning(self, "Uyarı", "Danışan kodları ağ sorunu nedeniyle yüklenemedi. Manuel giriş yapabilirsiniz.")

    def randevuyu_kaydet(self):
        """Arayüz verilerini kontrol eder ve API'ye POST isteği atar"""
        girilen_danisan = self.cmb_danisan_kodu.currentText().strip()
        secilen_oda_id = self.cmb_odalar.currentData()
        
        # FORM DOĞRULAMASI (Code Review - Madde 4)
        if not girilen_danisan:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir danışan kodu giriniz.")
            return
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir oda seçiniz.")
            return
        if self.dt_baslangic.dateTime() >= self.dt_bitis.dateTime():
            QMessageBox.warning(self, "Geçersiz Zaman", "Bitiş zamanı başlangıç zamanından sonra olmalıdır!")
            return

        baslangic_str = self.dt_baslangic.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        bitis_str = self.dt_bitis.dateTime().toString("yyyy-MM-ddTHH:mm:ss")

        yeni_randevu = IstemciRandevu(
            danisan_kod_id=girilen_danisan,
            psikolog_id=self.mevcut_psikolog_id,
            oda_id=secilen_oda_id,
            baslangic_zamani=baslangic_str,
            bitis_zamani=bitis_str
        )

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.post(f"{self.api_url}/api/randevular", 
                                  json=yeni_randevu.to_dict(), 
                                  headers=headers,
                                  timeout=5)
            
            if cevap.status_code == 201:
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla oluşturuldu!")
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen psikolog veya oda bu saatlerde dolu!")
            elif cevap.status_code == 422:
                QMessageBox.warning(self, "Hatalı Veri", "Lütfen danışan kodunu ve saatleri kontrol edin.")
            else:
                QMessageBox.warning(self, "Hata", f"İşlem başarısız: {cevap.json().get('detail')}")
                
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Zaman Aşımı", "Sunucuya bağlanılamadı, işlem çok uzun sürdü.")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")


# ======================================================================
#  APT-003: MEVCUT RANDEVUYU DÜZENLEME FORMU
# ======================================================================
class RandevuDuzenleFormu(QWidget):
    def __init__(self, api_url, token, mevcut_psikolog_id, randevu_id, eski_veriler):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.randevu_id = randevu_id
        self.eski_veriler = eski_veriler 
        
        self.setWindowTitle(f"Randevu Düzenle (ID: {self.randevu_id})")
        self.resize(450, 250)
        
        self.init_ui()
        self.odalari_yukle()
        self.danisanlari_yukle()
        
        # Kutuların içini veritabanından gelen ESKİ VERİLERLE doldur
        self.eski_verileri_arayuze_bas()

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        kutu_stili = """
            QComboBox { padding: 8px; border-radius: 6px; border: 2px solid #bdc3c7; background-color: white; color: black; }
            QComboBox QAbstractItemView { background-color: white; color: black; selection-background-color: #1A73E8; selection-color: white; }
            QLineEdit { color: black; }
        """

        self.cmb_danisan_kodu = QComboBox()
        self.cmb_danisan_kodu.setEditable(True)
        self.cmb_danisan_kodu.setStyleSheet(kutu_stili)
        form_layout.addRow("Danışan Kodu:", self.cmb_danisan_kodu)

        self.cmb_odalar = QComboBox()
        self.cmb_odalar.setStyleSheet(kutu_stili)
        form_layout.addRow("Oda Seçiniz:", self.cmb_odalar)

        self.dt_baslangic = QDateTimeEdit()
        self.dt_baslangic.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Başlangıç:", self.dt_baslangic)

        self.dt_bitis = QDateTimeEdit()
        self.dt_bitis.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Bitiş:", self.dt_bitis)

        self.btn_guncelle = StandartButon("Değişiklikleri Kaydet")
        self.btn_guncelle.setStyleSheet("background-color: #f39c12; color: white; border-radius: 6px; padding: 10px; font-weight: bold;") # Turuncu
        self.btn_guncelle.clicked.connect(self.randevuyu_guncelle)

        layout.addLayout(form_layout)
        layout.addWidget(self.btn_guncelle)
        self.setLayout(layout)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for oda in cevap.json():
                    if oda["aktif_mi"]:
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
        except: pass

    def danisanlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/danisan-kodlari", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for kod in cevap.json():
                    self.cmb_danisan_kodu.addItem(kod["danisan_kod_id"])
        except: pass

    def eski_verileri_arayuze_bas(self):
        """Açılır açılmaz kutuları eski verilerle doldurur"""
        self.cmb_danisan_kodu.setCurrentText(self.eski_veriler["danisan_kod_id"])
        
        oda_index = self.cmb_odalar.findData(self.eski_veriler["oda_id"])
        if oda_index >= 0:
            self.cmb_odalar.setCurrentIndex(oda_index)
            
        fmt = "yyyy-MM-ddTHH:mm:ss"
        self.dt_baslangic.setDateTime(QDateTime.fromString(self.eski_veriler["baslangic_zamani"].split('.')[0], fmt))
        self.dt_bitis.setDateTime(QDateTime.fromString(self.eski_veriler["bitis_zamani"].split('.')[0], fmt))

    def randevuyu_guncelle(self):
        girilen_danisan = self.cmb_danisan_kodu.currentText().strip()
        secilen_oda_id = self.cmb_odalar.currentData()
        
        # FORM DOĞRULAMASI (Code Review - Madde 4)
        if not girilen_danisan:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir danışan kodu giriniz.")
            return
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir oda seçiniz.")
            return
        if self.dt_baslangic.dateTime() >= self.dt_bitis.dateTime():
            QMessageBox.warning(self, "Geçersiz Zaman", "Bitiş zamanı başlangıç zamanından sonra olmalıdır!")
            return

        guncel_veriler = {
            "danisan_kod_id": girilen_danisan,
            "psikolog_id": self.mevcut_psikolog_id,
            "oda_id": secilen_oda_id,
            "baslangic_zamani": self.dt_baslangic.dateTime().toString("yyyy-MM-ddTHH:mm:ss"),
            "bitis_zamani": self.dt_bitis.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # POST yerine PATCH atıyoruz (APT-003)
            cevap = requests.patch(f"{self.api_url}/api/randevular/{self.randevu_id}", 
                                  json=guncel_veriler, 
                                  headers=headers,
                                  timeout=5)
            
            if cevap.status_code == 200:
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla güncellendi!")
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen saatte oda veya siz dolusunuz!")
            else:
                QMessageBox.warning(self, "Hata", f"Güncellenemedi: {cevap.json().get('detail')}")
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, "Zaman Aşımı", "Sunucuya bağlanılamadı, işlem çok uzun sürdü.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))