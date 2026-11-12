from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QSpinBox, QPushButton, QMessageBox
import requests
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)

# Yeni oluşturduğumuz öğrenci formunu buraya çağırıyoruz
from PySide6.QtCore import QTimer

class FaaliyetEkleDialog(QDialog):
    KISAYOL_GENISLIGI = 170       # "Yeni ... Ekle" düğmelerinin ortak genişliği (px)

    # DİKKAT: __init__ içine mevcut_veri=None ekledik!
    def __init__(self, api_url, token, parent=None, mevcut_veri=None, birim_yonetebilir=False):
        super().__init__(parent)
        self.api_url = api_url
        self.token = token
        self.mevcut_veri = mevcut_veri  # Gelen veriyi sınıfın hafızasına alıyoruz
        # Faaliyet birimlerini yalnızca bu izne sahip kullanıcı ekleyebilir (sunucu da aynı izni ister);
        # izni olmayana "Yeni Birim" düğmesi hiç gösterilmez.
        self.birim_yonetebilir = birim_yonetebilir
        
        # Başlığı moda göre ayarlıyoruz
        if self.mevcut_veri:
            self.setWindowTitle("Öğrenci Faaliyetini Düzenle")
        else:
            self.setWindowTitle("Öğrenci Faaliyet Kaydı")
            
        self.setMinimumWidth(560)
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

            /* Yeni eklediğimiz küçük yeşil butonun özel stili (öğrenci, faaliyet türü ve birim kısayolları aynı görünür) */
            QPushButton#btnYeniOgr, QPushButton#btnKisayol { background-color: #27AE60; padding: 5px; font-size: 12px; }
            QPushButton#btnYeniOgr:hover, QPushButton#btnKisayol:hover { background-color: #2ECC71; }
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
        ogr_layout.addWidget(self.btn_yeni_ogrenci)

        self.cb_faaliyet = QComboBox()
        self.cb_birim = QComboBox()
        self.sb_miktar = QSpinBox()
        self.sb_miktar.setRange(1, 10000)

        # Öğrenci düğmesiyle aynı görünümde kısayollar: ilgili yönetim penceresini açar, form kapanmaz.
        self.btn_yeni_faaliyet_turu = QPushButton("➕ Yeni Faaliyet Türü")
        self.btn_yeni_faaliyet_turu.setObjectName("btnKisayol")
        self.btn_yeni_faaliyet_turu.setToolTip("Listede olmayan bir faaliyet türünü ekleyin; form açık kalır.")
        self.btn_yeni_faaliyet_turu.clicked.connect(self.faaliyet_turleri_penceresini_ac)

        self.btn_yeni_birim = QPushButton("➕ Yeni Birim Ekle")
        self.btn_yeni_birim.setObjectName("btnKisayol")
        self.btn_yeni_birim.setToolTip("Listede olmayan bir birimi ekleyin; form açık kalır.")
        self.btn_yeni_birim.clicked.connect(self.birimler_penceresini_ac)

        # Düzenleme modunda (öğrenci düğmesi gibi) ve yetkisi olmayanlar için kısayollar gizlenir.
        if self.mevcut_veri:
            self.btn_yeni_faaliyet_turu.hide()
        if self.mevcut_veri or not self.birim_yonetebilir:
            self.btn_yeni_birim.hide()

        # Üç düğme aynı genişlikte olur; böylece açılır kutular alt alta hizalı durur.
        for dugme in (self.btn_yeni_ogrenci, self.btn_yeni_faaliyet_turu, self.btn_yeni_birim):
            dugme.setFixedWidth(self.KISAYOL_GENISLIGI)
        # Yetkisi olmayanda birim düğmesi gizlenir ama yeri korunur (hizalama bozulmasın). Düzenleme modunda
        # hiçbir düğme görünmediği için yer ayrılmaz.
        if not self.mevcut_veri and not self.birim_yonetebilir:
            boyut = self.btn_yeni_birim.sizePolicy()
            boyut.setRetainSizeWhenHidden(True)
            self.btn_yeni_birim.setSizePolicy(boyut)

        faaliyet_layout = QHBoxLayout()
        faaliyet_layout.addWidget(self.cb_faaliyet, stretch=3)
        faaliyet_layout.addWidget(self.btn_yeni_faaliyet_turu)

        birim_layout = QHBoxLayout()
        birim_layout.addWidget(self.cb_birim, stretch=3)
        birim_layout.addWidget(self.btn_yeni_birim)

        form_layout.addRow("Öğrenci Seç:", ogr_layout)
        form_layout.addRow("Faaliyet Türü:", faaliyet_layout)
        form_layout.addRow("Birim:", birim_layout)
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
            res_ogr = oturum_kontrollu_istek("GET", f"{self.api_url}/api/ogrenciler-liste", headers=headers)
            if oturum_hatasi_mi(res_ogr):
                return
            if res_ogr.status_code == 200:
                self.cb_ogrenci.addItem("Öğrenci Seçiniz...", None)
                for ogr in res_ogr.json():
                    self.cb_ogrenci.addItem(ogr["metin"], ogr["id"])
        except Exception as e:
            print("Öğrenciler yüklenemedi:", e)

    def faaliyet_turlerini_yukle(self):
        """Faaliyet türü listesini yeniler. Oturum süresi dolduysa False döner."""
        self.cb_faaliyet.clear()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res_faaliyet = oturum_kontrollu_istek("GET", f"{self.api_url}/api/faaliyetler", headers=headers)
            if oturum_hatasi_mi(res_faaliyet):
                return False
            if res_faaliyet.status_code == 200:
                self.cb_faaliyet.addItem("Seçiniz...", None)
                for f in res_faaliyet.json():
                    self.cb_faaliyet.addItem(f"{f['ad']} ({f['puan']} Puan)", f["id"])
        except Exception as e:
            print("Faaliyetler yüklenemedi:", e)
        return True

    def birimleri_yukle(self):
        """Birim listesini yeniler. Oturum süresi dolduysa False döner."""
        self.cb_birim.clear()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            res_birim = oturum_kontrollu_istek("GET", f"{self.api_url}/api/faaliyet-birimleri", headers=headers)
            if oturum_hatasi_mi(res_birim):
                return False
            if res_birim.status_code == 200:
                self.cb_birim.addItem("Seçiniz...", None)
                for b in res_birim.json():
                    self.cb_birim.addItem(b["ad"], b["id"])
        except Exception as e:
            print("Birimler yüklenemedi:", e)
        return True

    @staticmethod
    def _idler(combo):
        return {combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None}

    def _listeyi_yenile_ve_yeniyi_sec(self, combo, yukle):
        """Listeyi yeniden yükler. Yönetim penceresinde yeni kayıt eklendiyse onu seçer, eklenmediyse önceki seçimi korur."""
        onceki_secim = combo.currentData()
        eski_idler = self._idler(combo)
        if yukle() is False:
            return
        yeni_idler = self._idler(combo) - eski_idler
        hedef = max(yeni_idler) if yeni_idler else onceki_secim
        if hedef is not None:
            index = combo.findData(hedef)
            if index >= 0:
                combo.setCurrentIndex(index)

    def faaliyet_turleri_penceresini_ac(self):
        """Faaliyet Türleri yönetim penceresini açar; kapanınca liste yenilenir ve eklenen tür seçilir."""
        from faaliyet_turleri_dialog import FaaliyetTurleriDialog
        FaaliyetTurleriDialog(self.api_url, self.token, self).exec()
        self._listeyi_yenile_ve_yeniyi_sec(self.cb_faaliyet, self.faaliyet_turlerini_yukle)

    def birimler_penceresini_ac(self):
        """Faaliyet Birimleri yönetim penceresini açar; kapanınca liste yenilenir ve eklenen birim seçilir."""
        from birim_dialog import BirimYonetimDialog
        BirimYonetimDialog(self.api_url, self.token, self).exec()
        self._listeyi_yenile_ve_yeniyi_sec(self.cb_birim, self.birimleri_yukle)

    def verileri_yukle(self):
        headers = {"Authorization": f"Bearer {self.token}"}

        self.ogrencileri_yukle()

        if self.faaliyet_turlerini_yukle() is False:
            return
        if self.birimleri_yukle() is False:
            return

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
        ana_pencere = self.parent()

        if not hasattr(
            ana_pencere, "ogrenciler_sayfasina_git"
        ):
            QMessageBox.warning(
                self,
                "Uyarı",
                "Öğrenciler sayfasına geçilemiyor."
            )
            return

        self.reject()

        QTimer.singleShot(
            0,
            lambda: ana_pencere.ogrenciler_sayfasina_git(
                yeni_ekle=True
            )
        )

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
                
                res = oturum_kontrollu_istek("PUT", hedef_url, json=payload, headers=headers)
                if oturum_hatasi_mi(res):
                    return
            else:
                # EĞER NORMAL MODSA POST (YENİ EKLEME) İSTEĞİ AT
                res = oturum_kontrollu_istek("POST", f"{self.api_url}/api/faaliyet-kayitlari", json=payload, headers=headers)
                if oturum_hatasi_mi(res):
                    return
            
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