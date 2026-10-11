import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, 
                               QComboBox, QMessageBox, QDateTimeEdit)
from PySide6.QtCore import QDateTime

# Kendi yazdığımız modeli (APT-001) içe aktarıyoruz
from istemci_modelleri import IstemciRandevu 
from ui_components import StandartButon

class RandevuOlusturFormu(QWidget):
    def __init__(self, api_url, token, mevcut_psikolog_id):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        
        self.setWindowTitle("Yeni Randevu Oluştur (APT-002)")
        self.resize(450, 250)
        self.init_ui()
        self.odalari_yukle()
        self.danisanlari_yukle() # Yeni ekledik, açılışta danışanları çeker

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # BEYAZ YAZI SORUNUNU ÇÖZEN STİL (Metin rengi siyah olmaya zorlandı)
        kutu_stili = """
            QComboBox { padding: 8px; border-radius: 6px; border: 2px solid #bdc3c7; background-color: white; color: black; }
            QComboBox QAbstractItemView { background-color: white; color: black; selection-background-color: #1A73E8; selection-color: white; }
            QLineEdit { color: black; }
        """

        # 1. DANIŞAN KODU (Hem Seçilebilir Hem Yazılabilir Yapıldı)
        self.cmb_danisan_kodu = QComboBox()
        self.cmb_danisan_kodu.setEditable(True) # Bu satır sayesinde içine klavyeyle yazı yazılabilir!
        self.cmb_danisan_kodu.setStyleSheet(kutu_stili)
        self.cmb_danisan_kodu.lineEdit().setPlaceholderText("Örn: DAN-2026-0001 (Seçin veya yazın)")
        form_layout.addRow("Danışan Kodu:", self.cmb_danisan_kodu)

        # 2. ODA SEÇİMİ (Stili Düzeltildi)
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
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers)
            if cevap.status_code == 200:
                odalar = cevap.json()
                for oda in odalar:
                    if oda["aktif_mi"]:
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Odalar yüklenemedi: {str(e)}")

    def danisanlari_yukle(self):
        """API'den kayıtlı danışanları çekip ComboBox'a doldurur"""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/danisan-kodlari", headers=headers)
            if cevap.status_code == 200:
                kodlar = cevap.json()
                for kod in kodlar:
                    self.cmb_danisan_kodu.addItem(kod["danisan_kod_id"])
        except Exception:
            pass # Bağlanamazsa bile boş kalır, kullanıcı klavyeyle yazabilir.

    def randevuyu_kaydet(self):
        secilen_oda_id = self.cmb_odalar.currentData()
        baslangic_str = self.dt_baslangic.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        bitis_str = self.dt_bitis.dateTime().toString("yyyy-MM-ddTHH:mm:ss")

        # Artık danışan kodunu Combobox'tan alıyoruz (Kullanıcı listeden seçebilir VEYA yazabilir)
        girilen_danisan = self.cmb_danisan_kodu.currentText().strip()

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
                                  headers=headers)
            
            if cevap.status_code == 201:
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla oluşturuldu!")
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen psikolog veya oda bu saatlerde dolu!")
            elif cevap.status_code == 422:
                QMessageBox.warning(self, "Hatalı Veri", "Lütfen danışan kodunu ve saatleri kontrol edin.")
            else:
                QMessageBox.warning(self, "Hata", f"İşlem başarısız: {cevap.json().get('detail')}")
                
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")