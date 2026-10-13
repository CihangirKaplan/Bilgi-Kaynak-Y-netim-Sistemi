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
        
        self.setWindowTitle("Yeni Randevu Oluştur (APT-002)")
        self.resize(450, 250)
        self.init_ui()
        
        self.odalari_yukle()
        self.siradaki_kodu_getir() # Form açıldığında otomatik kodu çek

    def init_ui(self):
            layout = QVBoxLayout()
            form_layout = QFormLayout()

            kutu_stili = """
                QComboBox, QLineEdit { padding: 8px; border-radius: 6px; border: 2px solid #bdc3c7; background-color: white; color: black; font-weight: bold; }
                QComboBox QAbstractItemView { background-color: white; color: black; selection-background-color: #1A73E8; selection-color: white; }
            """

            self.txt_danisan_kodu = QLineEdit()
            self.txt_danisan_kodu.setReadOnly(True)
            self.txt_danisan_kodu.setStyleSheet("background-color: #E2E8F0; color: #1E3A8A; font-weight: bold; padding: 8px; border-radius: 6px;")
            form_layout.addRow("Danışan Kodu:", self.txt_danisan_kodu)

            # YENİ: Psikolog Seçimi
            self.cmb_psikologlar = QComboBox()
            self.cmb_psikologlar.setStyleSheet(kutu_stili)
            form_layout.addRow("Psikolog Seçiniz:", self.cmb_psikologlar)

            self.cmb_odalar = QComboBox()
            self.cmb_odalar.setStyleSheet(kutu_stili)
            form_layout.addRow("Oda Seçiniz:", self.cmb_odalar)

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

            # Arayüz açılırken psikolog listesini de çek (Yeni fonksiyonu en alta eklersin)
            self.psikologlari_yukle()

    def siradaki_kodu_getir(self):
        """API'den sıradaki kodu çekip ekrana kilitler."""
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
                for oda in cevap.json():
                    if oda["aktif_mi"]:
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def randevuyu_kaydet(self):
            secilen_oda_id = self.cmb_odalar.currentData()
            secilen_psikolog_id = self.cmb_psikologlar.currentData() # YENİ EKLENDİ
            
            if secilen_psikolog_id is None:
                QMessageBox.warning(self, "Eksik Veri", "Lütfen bir psikolog seçiniz.")
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
                danisan_kod_id=self.txt_danisan_kodu.text(),
                psikolog_id=secilen_psikolog_id, # ARTIK SEÇİLEN KİŞİNİN ID'Sİ GİDİYOR
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

    def psikologlari_yukle(self):
        """API'den aktif psikologları çeker ve ComboBox'a doldurur."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for psi in cevap.json():
                    # ComboBox'a adı yazdırıyoruz ama arkaplanda ID'sini tutuyoruz
                    self.cmb_psikologlar.addItem(psi["ad_soyad"], psi["personel_id"])
                
                # Eğer giriş yapan kişinin kendisi psikologsa (mevcut_psikolog_id None değilse) onu otomatik seçili yap
                if self.mevcut_psikolog_id is not None:
                    index = self.cmb_psikologlar.findData(self.mevcut_psikolog_id)
                    if index >= 0:
                        self.cmb_psikologlar.setCurrentIndex(index)
                        self.cmb_psikologlar.setEnabled(False) # Kendisi psikologsa başkasına randevu yazamasın
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikologlar yüklenemedi: {str(e)}")

# ======================================================================
#  APT-003 & APT-004: MEVCUT RANDEVUYU DÜZENLEME VE İPTAL FORMU
# ======================================================================
class RandevuDuzenleFormu(QWidget):
    veriler_degisti = Signal() # Tabloyu otomatik yenilemek için özel sinyal

    def __init__(self, api_url, token, mevcut_psikolog_id, randevu_id, eski_veriler):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.randevu_id = randevu_id
        self.eski_veriler = eski_veriler 
        
        self.setWindowTitle(f"Randevu Yönetimi (ID: {self.randevu_id})")
        self.resize(450, 300)
        
        self.init_ui()
        self.odalari_yukle()
        self.eski_verileri_arayuze_bas()

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        kutu_stili = """
            QComboBox { padding: 8px; border-radius: 6px; border: 2px solid #bdc3c7; background-color: white; color: black; }
            QComboBox QAbstractItemView { background-color: white; color: black; selection-background-color: #1A73E8; selection-color: white; }
        """

        # Düzenlemede danışan kodu değiştirilemez! (Kilitli QLineEdit)
        self.txt_danisan_kodu = QLineEdit()
        self.txt_danisan_kodu.setReadOnly(True)
        self.txt_danisan_kodu.setStyleSheet("background-color: #E2E8F0; color: #1E3A8A; font-weight: bold; padding: 8px; border-radius: 6px;")
        form_layout.addRow("Danışan Kodu:", self.txt_danisan_kodu)

        self.cmb_odalar = QComboBox()
        self.cmb_odalar.setStyleSheet(kutu_stili)
        form_layout.addRow("Oda Seçiniz:", self.cmb_odalar)

        self.dt_baslangic = QDateTimeEdit()
        self.dt_baslangic.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Başlangıç:", self.dt_baslangic)

        self.dt_bitis = QDateTimeEdit()
        self.dt_bitis.setDisplayFormat("yyyy-MM-dd HH:mm:00")
        form_layout.addRow("Bitiş:", self.dt_bitis)

        layout.addLayout(form_layout)
        
        buton_layout = QHBoxLayout()
        self.btn_guncelle = StandartButon("Değişiklikleri Kaydet")
        self.btn_guncelle.setStyleSheet("background-color: #f39c12; color: white; border-radius: 6px; padding: 10px; font-weight: bold;")
        self.btn_guncelle.clicked.connect(self.randevuyu_guncelle)
        
        self.btn_iptal = StandartButon("Randevuyu İptal Et")
        self.btn_iptal.setStyleSheet("background-color: #c0392b; color: white; border-radius: 6px; padding: 10px; font-weight: bold;")
        self.btn_iptal.clicked.connect(self.randevuyu_iptal_et)
        
        buton_layout.addWidget(self.btn_guncelle)
        buton_layout.addWidget(self.btn_iptal)
        
        layout.addLayout(buton_layout)
        self.setLayout(layout)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                for oda in cevap.json():
                    if oda["aktif_mi"]:
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

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
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir oda seçiniz.")
            return
        if self.dt_baslangic.dateTime() >= self.dt_bitis.dateTime():
            QMessageBox.warning(self, "Geçersiz Zaman", "Bitiş zamanı başlangıç zamanından sonra olmalıdır!")
            return

        guncel_veriler = {
            "danisan_kod_id": self.txt_danisan_kodu.text(),
            "psikolog_id": self.mevcut_psikolog_id,
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
                self.veriler_degisti.emit() # Listeyi yenilemesi için sinyal gönder
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen saatte oda veya siz dolusunuz!")
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
                self.veriler_degisti.emit() # Listeyi yenilemesi için sinyal gönder
                self.close()
            else:
                QMessageBox.warning(self, "Hata", f"İptal işlemi başarısız: {yanit.json().get('detail')}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen bir hata oluştu: {str(e)}")


# ======================================================================
#  RANDEVULARI DÜZENLE (LİSTE) EKRANI
# ======================================================================
class RandevuListesiFormu(QDialog):
    def __init__(self, api_url, token, mevcut_psikolog_id, parent=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.kullanici_id = mevcut_psikolog_id
        
        self.setWindowTitle("Randevu Listesi ve Düzenleme")
        self.resize(750, 400)
        self.setStyleSheet("background-color: #F8F9FA;")
        
        layout = QVBoxLayout(self)
        bilgi = QLabel("Düzenlemek veya iptal etmek istediğiniz randevuya çift tıklayın.")
        bilgi.setStyleSheet("font-size: 14px; color: #1D4ED8; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(bilgi)
        
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(5)
        self.tablo.setHorizontalHeaderLabels(["ID", "Danışan Kodu", "Başlangıç", "Bitiş", "Durum"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; color: #0F2552; gridline-color: #E2E8F0; font-size: 13px; }
            QHeaderView::section { background-color: #EAF0FA; color: #0F2552; font-weight: bold; border: 1px solid #E2E8F0; padding: 6px; }
        """)
        
        self.tablo.cellDoubleClicked.connect(self.satira_cift_tiklandi)
        layout.addWidget(self.tablo)
        
        self.yenile_btn = QPushButton("🔄 Listeyi Yenile")
        self.yenile_btn.setStyleSheet("background-color: #10B981; color: white; padding: 10px; border-radius: 6px; font-weight: bold;")
        self.yenile_btn.clicked.connect(self.verileri_cek)
        layout.addWidget(self.yenile_btn)
        
        self.verileri_cek()
        
    def verileri_cek(self):
        self.tablo.setRowCount(0)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/randevular", headers=headers)
            if cevap.status_code == 200:
                self.randevular = cevap.json()
                for r in self.randevular:
                    satir = self.tablo.rowCount()
                    self.tablo.insertRow(satir)
                    self.tablo.setItem(satir, 0, QTableWidgetItem(str(r["randevu_id"])))
                    self.tablo.setItem(satir, 1, QTableWidgetItem(r["danisan_kod_id"]))
                    self.tablo.setItem(satir, 2, QTableWidgetItem(r["baslangic_zamani"].replace("T", " ")))
                    self.tablo.setItem(satir, 3, QTableWidgetItem(r["bitis_zamani"].replace("T", " ")))
                    
                    durum_item = QTableWidgetItem(r["durum"])
                    if r["durum"] == "IPTAL_EDILDI":
                        durum_item.setForeground(QColor("#DC2626"))
                    else:
                        durum_item.setForeground(QColor("#2563EB"))
                    self.tablo.setItem(satir, 4, durum_item)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Bağlantı sorunu: {e}")

    def satira_cift_tiklandi(self, satir, sutun):
        randevu_id = int(self.tablo.item(satir, 0).text())
        secili_randevu = next((r for r in self.randevular if r["randevu_id"] == randevu_id), None)
        
        if secili_randevu:
            if secili_randevu["durum"] == "IPTAL_EDILDI":
                QMessageBox.warning(self, "Uyarı", "İptal edilmiş bir randevuyu düzenleyemezsiniz.")
                return
                
            self.duzenle_formu = RandevuDuzenleFormu(
                api_url=self.api_url, 
                token=self.token, 
                mevcut_psikolog_id=self.kullanici_id,
                randevu_id=randevu_id,
                eski_veriler=secili_randevu
            )
            # Sinyal bağlantısı sayesinde işlem bitince tablo otomatik yenilenir!
            self.duzenle_formu.veriler_degisti.connect(self.verileri_cek)
            self.duzenle_formu.show()