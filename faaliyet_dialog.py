from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QSpinBox, QPushButton, QMessageBox
import requests

# Yeni oluşturduğumuz öğrenci formunu buraya çağırıyoruz
from ogrenci_dialog import OgrenciEkleDialog

class FaaliyetEkleDialog(QDialog):
    # DİKKAT: __init__ içine mevcut_veri=None ekledik!
    def __init__(self, api_url, token, parent=None, mevcut_veri=None):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.mevcut_veri = mevcut_veri  # Gelen veriyi sınıfın hafızasına alıyoruz
        
        # Başlığı moda göre ayarlıyoruz
        if self.mevcut_veri:
            self.setWindowTitle("Öğrenci Faaliyetini Düzenle")
        else:
            self.setWindowTitle("Öğrenci Faaliyet Kaydı")
            
        self.setMinimumWidth(450)
        self.setStyleSheet("""
            QDialog { background-color: #F8F9FA; }
            QComboBox, QSpinBox {
                background-color: white;
                color: #2C3E50;
                padding: 6px;
                border: 1px solid #BDC3C7;
                border-radius: 4px;
            }
            QComboBox:focus, QSpinBox:focus {
                border: 1px solid #3498DB;
                background-color: #FAFAFA;
            }
            QPushButton { background-color: #2980B9; color: white; font-weight: bold; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #3498DB; }

            /* Yeni eklediğimiz küçük yeşil butonun özel stili */
            QPushButton#btnYeniOgr { background-color: #27AE60; padding: 5px; font-size: 12px; }
            QPushButton#btnYeniOgr:hover { background-color: #2ECC71; }
        """)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        ogr_layout = QHBoxLayout()
        self.cb_ogrenci = QComboBox()

        self.btn_yeni_ogrenci = QPushButton("➕ Yeni Öğrenci Ekle")
        self.btn_yeni_ogrenci.setObjectName("btnYeniOgr")
        self.btn_yeni_ogrenci.clicked.connect(self.yeni_ogrenci_ekle_formunu_ac)

        # Düzenleme modundaysak, karışıklık olmasın diye "Yeni Öğrenci Ekle" butonunu gizleyebiliriz
        if self.mevcut_veri:
            self.btn_yeni_ogrenci.hide()
            
        ogr_layout.addWidget(self.cb_ogrenci, stretch=3)
        ogr_layout.addWidget(self.btn_yeni_ogrenci, stretch=1)

        self.cb_faaliyet = QComboBox()
        self.cb_birim = QComboBox()
        self.sb_miktar = QSpinBox()
        self.sb_miktar.setRange(1, 10000)

        form_layout.addRow("Öğrenci Seç:", ogr_layout)
        form_layout.addRow("Faaliyet Türü:", self.cb_faaliyet)
        form_layout.addRow("Birim:", self.cb_birim)
        form_layout.addRow("Miktar:", self.sb_miktar)

        layout.addLayout(form_layout)

        # Buton ismini moda göre ayarlıyoruz
        buton_metni = "Güncelle" if self.mevcut_veri else "Kaydet"
        self.btn_kaydet = QPushButton(buton_metni)
        self.btn_kaydet.clicked.connect(self.kaydet_tiklandi)
        layout.addWidget(self.btn_kaydet)

        self.verileri_yukle()

    def ogrencileri_yukle(self):
        self.cb_ogrenci.clear()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res_ogr = requests.get(f"{self.api_url}/api/ogrenciler-liste", headers=headers)
            if res_ogr.status_code == 200:
                self.cb_ogrenci.addItem("Öğrenci Seçiniz...", None)
                for ogr in res_ogr.json():
                    self.cb_ogrenci.addItem(ogr["metin"], ogr["id"])
        except Exception as e:
            print("Öğrenciler yüklenemedi:", e)

    def verileri_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}

        self.ogrencileri_yukle()

        try:
            res_faaliyet = requests.get(f"{self.api_url}/api/faaliyetler", headers=headers)
            if res_faaliyet.status_code == 200:
                self.cb_faaliyet.addItem("Seçiniz...", None)
                for f in res_faaliyet.json():
                    self.cb_faaliyet.addItem(f"{f['ad']} ({f['puan']} Puan)", f["id"])
        except Exception as e:
            print("Faaliyetler yüklenemedi:", e)

        try:
            res_birim = requests.get(f"{self.api_url}/api/faaliyet-birimleri", headers=headers)
            if res_birim.status_code == 200:
                self.cb_birim.addItem("Seçiniz...", None)
                for b in res_birim.json():
                    self.cb_birim.addItem(b["ad"], b["id"])
        except Exception as e:
            print("Birimler yüklenemedi:", e)

        # --- YENİ: EĞER DÜZENLEME MODUNDAYSAK COMBOKUTULARINI ESKİ VERİYLE DOLDUR ---
        if hasattr(self, 'mevcut_veri') and self.mevcut_veri:
            # 1. Öğrenciyi seç
            for i in range(self.cb_ogrenci.count()):
                if self.mevcut_veri["ogrenci_adi"] in self.cb_ogrenci.itemText(i):
                    self.cb_ogrenci.setCurrentIndex(i)
                    break
            
            # 2. Faaliyeti seç
            for i in range(self.cb_faaliyet.count()):
                if self.cb_faaliyet.itemText(i).startswith(self.mevcut_veri["faaliyet_adi"]):
                    self.cb_faaliyet.setCurrentIndex(i)
                    break
                    
            # 3. Birimi seç
            for i in range(self.cb_birim.count()):
                if self.mevcut_veri["birim_adi"] in self.cb_birim.itemText(i):
                    self.cb_birim.setCurrentIndex(i)
                    break
                    
            # 4. Miktarı yaz
            self.sb_miktar.setValue(int(self.mevcut_veri["miktar"]))

    def yeni_ogrenci_ekle_formunu_ac(self):
        dialog = OgrenciEkleDialog(self.api_url, self.token, self)
        if dialog.exec():
            self.ogrencileri_yukle()
            QMessageBox.information(self, "Bilgi", "Liste güncellendi, yeni eklediğiniz öğrenciyi seçebilirsiniz.")

    def kaydet_tiklandi(self):
        ogrenci_id = self.cb_ogrenci.currentData()
        faaliyet_id = self.cb_faaliyet.currentData()
        birim_id = self.cb_birim.currentData()
        miktar = self.sb_miktar.value()

        if not ogrenci_id or not faaliyet_id or not birim_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen öğrenci, faaliyet ve birim alanlarını doldurunuz.")
            return

        payload = {
            "ogrenci_id": ogrenci_id,
            "faaliyet_id": faaliyet_id,
            "birim_id": birim_id,
            "miktar": miktar
        }

        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            if hasattr(self, 'mevcut_veri') and self.mevcut_veri:
                # EĞER DÜZENLEME MODUYSA PUT (GÜNCELLEME) İSTEĞİ AT
                takip_id = str(self.mevcut_veri["takip_id"]).strip() # Görünmez boşlukları temizle
                hedef_url = f"{self.api_url.rstrip('/')}/api/faaliyet-kayitlari/{takip_id}" # Adresi güvenli hale getir
                
                print(f"--- GÜNCELLEME İSTEĞİ ATIYORUZ ---")
                print(f"Gidilen Adres: {hedef_url}")
                
                res = requests.put(hedef_url, json=payload, headers=headers)
            else:
                # EĞER NORMAL MODSA POST (YENİ EKLEME) İSTEĞİ AT
                res = requests.post(f"{self.api_url}/api/faaliyet-kayitlari", json=payload, headers=headers)
            
            if res.status_code == 200:
                QMessageBox.information(self, "Başarılı", res.json().get("mesaj", "İşlem başarıyla tamamlandı!"))
                self.accept()
            else:
                try:
                    hata_detayi = res.json().get("detail", res.text)
                except:
                    hata_detayi = res.text
                QMessageBox.critical(self, "Hata", f"İşlem başarısız oldu.\nSunucu Cevabı: {hata_detayi}")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")