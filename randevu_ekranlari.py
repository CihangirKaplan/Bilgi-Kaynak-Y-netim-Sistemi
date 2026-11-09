import requests
from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QHBoxLayout,
                               QComboBox, QMessageBox, QDateTimeEdit, QDialog, 
                               QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                               QAbstractItemView, QPushButton, QLineEdit,
                               QDateEdit)
from PySide6.QtCore import QDateTime, Signal, Qt, QDate
from PySide6.QtGui import QColor

from istemci_modelleri import IstemciRandevu 
from ui_components import StandartButon

# ======================================================================
#  APT-002: YENİ RANDEVU OLUŞTURMA FORMU
# ======================================================================
class RandevuOlusturFormu(QWidget):
    veriler_degisti = Signal()
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
        self.danisan_kodlarini_yukle()

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

        danisan_layout = QHBoxLayout()
        self.cmb_danisan_kodu = QComboBox()
        danisan_layout.addWidget(self.cmb_danisan_kodu)
        form_layout.addRow("Danışan Kodu:", danisan_layout)

        self.cmb_psikologlar = QComboBox()
        form_layout.addRow("Psikolog Seçiniz:", self.cmb_psikologlar)

        self.cmb_odalar = QComboBox()
        form_layout.addRow("Görüşme Odası:", self.cmb_odalar)

        self.dt_tarih = QDateEdit(QDate.currentDate())
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.dt_tarih.setCalendarPopup(True)
        form_layout.addRow("Randevu Tarihi:", self.dt_tarih)

        self.cmb_saat = QComboBox()
        self.cmb_saat.addItems(["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"])
        form_layout.addRow("Randevu Saati:", self.cmb_saat)

        ana_layout.addLayout(form_layout)

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

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                self.tum_odalar = cevap.json()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def psikologlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
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
        
        secilen_psikolog_id = self.cmb_psikologlar.currentData()
        if secilen_psikolog_id is None:
            return
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Artık tüm odaları değil, sadece bu psikoloğa atanmış odaları çekiyoruz
            istek_url = f"{self.api_url}/api/psikologlar/{secilen_psikolog_id}/odalar"
            cevap = oturum_kontrollu_istek("GET", istek_url, headers=headers, timeout=5)
            
            if oturum_hatasi_mi(cevap): 
                return
                
            if cevap.status_code == 200:
                atanmis_odalar = cevap.json()
                for oda in atanmis_odalar:
                    if oda.get("aktif_mi", True):
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
                        
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikoloğun odaları yüklenemedi: {str(e)}")
    
    def danisan_kodlarini_yukle(self):
        self.cmb_danisan_kodu.clear()
        self.cmb_danisan_kodu.addItem("--- Danışan Seçiniz ---", "") 
        
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/danisan-kodlari", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                danisanlar = cevap.json()
                for d in danisanlar:
                    kod = d.get("danisan_kod_id")
                    self.cmb_danisan_kodu.addItem(kod, kod)
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Danışan kodları yüklenemedi: {str(e)}")
            
    def randevuyu_kaydet(self):
        secilen_danisan_kodu = self.cmb_danisan_kodu.currentData()
        secilen_oda_id = self.cmb_odalar.currentData()
        secilen_psikolog_id = self.cmb_psikologlar.currentData()

        if not secilen_danisan_kodu:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir danışan kodu seçiniz veya yeni oluşturunuz.")
            return
        if secilen_psikolog_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir psikolog seçiniz.")
            return
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen geçerli bir görüşme odası seçiniz.")
            return
            
        tarih_str = self.dt_tarih.date().toString("yyyy-MM-dd")
        saat_str = self.cmb_saat.currentText()
        saat_int = int(saat_str.split(":")[0])

        baslangic_str = f"{tarih_str}T{saat_str}:00"
        bitis_str = f"{tarih_str}T{saat_int + 1:02d}:00:00"

        payload = {
            "danisan_kod_id": secilen_danisan_kodu,
            "psikolog_id": int(secilen_psikolog_id),
            "oda_id": int(secilen_oda_id),
            "baslangic_zamani": baslangic_str,
            "bitis_zamani": bitis_str
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("POST", f"{self.api_url}/api/randevular", json=payload, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            
            if cevap.status_code in (200, 201):
                QMessageBox.information(self, "Başarılı", "Randevu başarıyla oluşturuldu!")
                self.veriler_degisti.emit()
                self.close() 
            elif cevap.status_code == 409:
                QMessageBox.warning(self, "Çakışma", "Seçilen psikolog veya oda bu saatlerde dolu!")
            else:
                hata_detay = cevap.json().get('detail', 'Bilinmeyen hata') if cevap.headers.get("content-type") == "application/json" else cevap.text
                QMessageBox.warning(self, "Hata", f"İşlem başarısız: {hata_detay}")
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
        
        self.setWindowTitle("Randevu Yönetimi")
        self.resize(450, 420)
        
        self.init_ui()
        self.odalari_yukle() 
        self.psikologlari_yukle() 
        self.eski_verileri_arayuze_bas()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #F8F9FA; font-family: 'Segoe UI', Arial; }
            QLabel { font-weight: bold; color: #0F2552; font-size: 13px; }
            QLineEdit, QComboBox, QDateEdit, QDateTimeEdit { 
                padding: 10px; border-radius: 6px; border: 1px solid #CBD5E1; 
                background-color: white; color: #0F2552; font-size: 13px; font-weight: bold;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 2px solid #2563EB; }
            QComboBox QAbstractItemView { 
                background-color: white; color: #0F2552; selection-background-color: #2563EB; selection-color: white; 
            }
            QPushButton#btnGuncelle {
                background-color: #2563EB; color: white; border-radius: 6px; padding: 10px 20px; 
                font-weight: bold; font-size: 14px; border: none;
            }
            QPushButton#btnGuncelle:hover { background-color: #1D4ED8; }
        """)

        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(20, 20, 20, 20)
        ana_layout.setSpacing(18)

        from PySide6.QtWidgets import QFrame
        baslik_frame = QFrame()
        baslik_frame.setStyleSheet("background-color: #0A1F5C; border-radius: 8px;")
        baslik_layout = QHBoxLayout(baslik_frame)
        baslik_layout.setContentsMargins(15, 15, 15, 15)
        
        lbl_ikon = QLabel("✏️")
        lbl_ikon.setStyleSheet("font-size: 18px; color: white; background: transparent;")
        lbl_baslik = QLabel("Randevu Yönetimi")
        lbl_baslik.setStyleSheet("color: white; font-size: 15px; font-weight: bold; background: transparent;")
        
        baslik_layout.addWidget(lbl_ikon)
        baslik_layout.addWidget(lbl_baslik)
        baslik_layout.addStretch()
        ana_layout.addWidget(baslik_frame)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.txt_danisan_kodu = QLineEdit()
        self.txt_danisan_kodu.setReadOnly(True)
        self.txt_danisan_kodu.setStyleSheet("background-color: #E2E8F0; color: #1E3A8A; font-weight: bold; padding: 9px; border-radius: 6px; border: none;")
        form_layout.addRow("Danışan Kodu:", self.txt_danisan_kodu)

        self.cmb_psikologlar = QComboBox()
        form_layout.addRow("Psikolog:", self.cmb_psikologlar)
        self.cmb_psikologlar.currentIndexChanged.connect(self.odalari_filtrele)

        self.cmb_odalar = QComboBox()
        form_layout.addRow("Görüşme Odası:", self.cmb_odalar)

        self.dt_tarih = QDateEdit()
        self.dt_tarih.setDisplayFormat("dd.MM.yyyy")
        self.dt_tarih.setCalendarPopup(True)
        form_layout.addRow("Randevu Tarihi:", self.dt_tarih)

        self.cmb_saat = QComboBox()
        self.cmb_saat.addItems(["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"])
        form_layout.addRow("Randevu Saati:", self.cmb_saat)

        ana_layout.addLayout(form_layout)

        buton_layout = QHBoxLayout()
        self.btn_guncelle = QPushButton("Değişiklikleri Kaydet")
        self.btn_guncelle.setObjectName("btnGuncelle")
        self.btn_guncelle.clicked.connect(self.randevuyu_guncelle)
        
        buton_layout.addStretch()
        buton_layout.addWidget(self.btn_guncelle)
        buton_layout.addStretch()
        
        ana_layout.addLayout(buton_layout)

    def odalari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap): return
            if cevap.status_code == 200:
                self.tum_odalar = cevap.json()
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Odalar yüklenemedi: {str(e)}")

    def psikologlari_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/psikologlar", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap): return
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
        
        secilen_psikolog_id = self.cmb_psikologlar.currentData()
        if secilen_psikolog_id is None:
            return
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # Artık tüm odaları değil, sadece bu psikoloğa atanmış odaları çekiyoruz
            istek_url = f"{self.api_url}/api/psikologlar/{secilen_psikolog_id}/odalar"
            cevap = oturum_kontrollu_istek("GET", istek_url, headers=headers, timeout=5)
            
            if oturum_hatasi_mi(cevap): 
                return
                
            if cevap.status_code == 200:
                atanmis_odalar = cevap.json()
                for oda in atanmis_odalar:
                    if oda.get("aktif_mi", True):
                        self.cmb_odalar.addItem(oda["oda_adi"], oda["oda_id"])
                        
        except Exception as e:
            QMessageBox.warning(self, "Ağ Uyarısı", f"Psikoloğun odaları yüklenemedi: {str(e)}")

    def eski_verileri_arayuze_bas(self):
        self.txt_danisan_kodu.setText(self.eski_veriler["danisan_kod_id"])
        
        oda_index = self.cmb_odalar.findData(self.eski_veriler["oda_id"])
        if oda_index >= 0:
            self.cmb_odalar.setCurrentIndex(oda_index)
            
        baslangic = self.eski_veriler["baslangic_zamani"].split('.')[0]
        tarih_kismi, saat_kismi = baslangic.split("T")

        self.dt_tarih.setDate(QDate.fromString(tarih_kismi, "yyyy-MM-dd"))

        saat_kisa = saat_kismi[:5]
        index = self.cmb_saat.findText(saat_kisa)
        if index >= 0:
            self.cmb_saat.setCurrentIndex(index)

    def randevuyu_guncelle(self):
        secilen_oda_id = self.cmb_odalar.currentData()
        if secilen_oda_id is None:
            QMessageBox.warning(self, "Eksik Veri", "Lütfen bir görüşme odası seçiniz.")
            return
            
        tarih_str = self.dt_tarih.date().toString("yyyy-MM-dd")
        saat_str = self.cmb_saat.currentText()
        saat_int = int(saat_str.split(":")[0])

        guncel_veriler = {
            "danisan_kod_id": self.txt_danisan_kodu.text(),
            "psikolog_id": self.cmb_psikologlar.currentData(),
            "oda_id": secilen_oda_id,
            "baslangic_zamani": f"{tarih_str}T{saat_str}:00",
            "bitis_zamani": f"{tarih_str}T{saat_int + 1:02d}:00:00"
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("PATCH", f"{self.api_url}/api/randevular/{self.randevu_id}",
                                          json=guncel_veriler, headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap): return
            
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


# ======================================================================
#  RANDEVU ANA EKRANI (TABLO GÖRÜNÜMÜ VE DOĞRUDAN DÜZENLEME MANTIĞI)
# ======================================================================
class RandevuAnaEkrani(QWidget):
    def __init__(self, api_url, token, mevcut_psikolog_id, rol=""):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.mevcut_psikolog_id = mevcut_psikolog_id
        self.rol = rol
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(7)
        self.tablo.setHorizontalHeaderLabels([
            "Randevu ID", "Danışan Kodu", "Oda", "Başlangıç", "Bitiş", "Durum", "Oluşturulma Tarihi"
        ])
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

        oda_sozlugu = {}
        try:
            oda_cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if not oturum_hatasi_mi(oda_cevap) and oda_cevap.status_code == 200:
                for oda in oda_cevap.json():
                    oda_sozlugu[oda["oda_id"]] = oda["oda_adi"]
        except Exception as e:
            print("Oda isimleri çekilirken hata oluştu:", e)

        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/randevular", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
                
            if cevap.status_code == 200:
                # Veriyi hem self.randevular'a atıyoruz hem de local değişkene bağlıyoruz
                self.randevular = cevap.json()
                
                self.tablo.setRowCount(len(self.randevular))
                
                def tarih_bicimlendir(tarih_str):
                    if not tarih_str: return ""
                    try:
                        temiz = tarih_str.split(".")[0] 
                        dt = QDateTime.fromString(temiz, "yyyy-MM-ddTHH:mm:ss")
                        if dt.isValid(): return dt.toString("HH.mm dd.MM.yyyy")
                    except Exception:
                        pass
                    return tarih_str.replace("T", " ")

                for satir, r in enumerate(self.randevular):
                    baslangic = tarih_bicimlendir(r.get("baslangic_zamani", ""))
                    bitis = tarih_bicimlendir(r.get("bitis_zamani", ""))
                    
                    hammadde_tarih = (
                        r.get("olusturma_tarihi") or 
                        r.get("created_at") or 
                        r.get("olusturuldu_at") or 
                        r.get("kayit_tarihi") or 
                        ""
                    )
                    olusturma = tarih_bicimlendir(hammadde_tarih)

                    item_id = QTableWidgetItem(str(r.get("randevu_id", "")))
                    item_kod = QTableWidgetItem(r.get("danisan_kod_id", ""))
                    
                    oda_id = r.get("oda_id")
                    oda_adi = oda_sozlugu.get(oda_id, f"Bilinmeyen Oda ({oda_id})")
                    item_oda = QTableWidgetItem(oda_adi) 
                    
                    item_bas = QTableWidgetItem(baslangic)
                    item_bit = QTableWidgetItem(bitis)
                    item_olus = QTableWidgetItem(olusturma)
                    
                    durum_ham = r.get("durum", "")
                    if durum_ham == "IPTAL_EDILDI": durum_metni = "İptal Edildi"
                    elif durum_ham == "PLANLANDI": durum_metni = "Planlandı"
                    else: durum_metni = durum_ham.capitalize()

                    item_durum = QTableWidgetItem(durum_metni)
                    
                    if durum_ham == "IPTAL_EDILDI":
                        item_durum.setForeground(QColor("#DC2626"))
                    elif durum_ham == "PLANLANDI":
                        item_durum.setForeground(QColor("#10B981"))
                    else:
                        item_durum.setForeground(QColor("#2563EB"))
                        
                    for item in [item_id, item_kod, item_oda, item_bas, item_bit, item_durum, item_olus]:
                        item.setTextAlignment(Qt.AlignCenter)
                        
                    self.tablo.setItem(satir, 0, item_id)
                    self.tablo.setItem(satir, 1, item_kod)
                    self.tablo.setItem(satir, 2, item_oda)
                    self.tablo.setItem(satir, 3, item_bas)
                    self.tablo.setItem(satir, 4, item_bit)
                    self.tablo.setItem(satir, 5, item_durum)
                    self.tablo.setItem(satir, 6, item_olus)
            else:
                print(f"Hata: {cevap.text}")
        except Exception as e:
            print("Randevular çekilirken hata oluştu:", e)
                  

    def duzenle_secilen(self):
        secili_satirlar = self.tablo.selectionModel().selectedRows()
        if not secili_satirlar:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen düzenlemek istediğiniz randevuyu tablodan seçin.")
            return
            
        satir = secili_satirlar[0].row()
        randevu_id = int(self.tablo.item(satir, 0).text())
            
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/randevular", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap): return
                
            if cevap.status_code == 200:
                secili_randevu = next((r for r in cevap.json() if r["randevu_id"] == randevu_id), None)
                
                if secili_randevu:
                    gercek_durum = str(secili_randevu.get("durum", ""))
                    
                    if "iptal" in gercek_durum.lower() or "IPTAL" in gercek_durum:
                        QMessageBox.warning(
                            self, 
                            "İşlem Engellendi", 
                            "İptal edilmiş randevular üzerinde değişiklik yapılamaz.\n\n"
                            "Lütfen bu danışan için takvim üzerinden yeni bir randevu oluşturun."
                        )
                        return

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
        
        if durum == "İptal Edildi" or durum == "IPTAL_EDILDI":
            QMessageBox.information(self, "Bilgi", "Bu randevu zaten iptal edilmiş.")
            return
            
        onay = QMessageBox.question(self, "İptal Onayı", "Seçili randevuyu iptal etmek istediğinize emin misiniz?", 
                                    QMessageBox.Yes | QMessageBox.No)
        
        if onay == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            try:
                cevap = oturum_kontrollu_istek("PATCH", f"{self.api_url}/api/randevular/{randevu_id}/iptal", headers=headers, timeout=5)
                if oturum_hatasi_mi(cevap): return
                
                if cevap.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Randevu iptal edildi.")
                    self.verileri_cek()
                else:
                    QMessageBox.warning(self, "Hata", "İşlem başarısız oldu.")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası: {str(e)}")