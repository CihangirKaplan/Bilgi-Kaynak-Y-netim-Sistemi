from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                               QLabel, QLineEdit, QPushButton, QMessageBox, 
                               QGraphicsDropShadowEffect,QCheckBox, QScrollArea, 
                               QGroupBox, QWidget)
from PySide6.QtCore import Qt, QPropertyAnimation, Property, QRect, QRectF
import requests
from PySide6.QtGui import QColor, QPainter

import izin_bagimliliklari


def golge_ekle(widget, blur=20, alpha=30, dy=5):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(10, 31, 92, alpha))
    widget.setGraphicsEffect(eff)

class RolOlusturDialog(QDialog):
    def __init__(self, api_url, token, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.setWindowTitle("TKYS — Yeni Rol Oluştur")
        self.setFixedSize(400, 260)
        self.setStyleSheet("QDialog { background-color: #F8FAFC; }")
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # --- ÜST BAŞLIK KARTI ---
        baslik_layout = QHBoxLayout()
        
        ikon = QLabel("🛡️")
        ikon.setStyleSheet("font-size: 24px; background: #DBEAFE; border-radius: 12px; padding: 8px;")
        ikon.setAlignment(Qt.AlignCenter)
        
        baslik_metin = QVBoxLayout()
        baslik_metin.setSpacing(2)
        ana_baslik = QLabel("Yeni Rol Oluştur")
        ana_baslik.setStyleSheet("font-size: 18px; font-weight: 900; color: #0A1F5C;")
        alt_baslik = QLabel("Sisteme yeni bir yetki grubu tanımlayın")
        alt_baslik.setStyleSheet("font-size: 12px; color: #6B7FA8;")
        
        baslik_metin.addWidget(ana_baslik)
        baslik_metin.addWidget(alt_baslik)
        
        baslik_layout.addWidget(ikon)
        baslik_layout.addLayout(baslik_metin)
        baslik_layout.addStretch()
        layout.addLayout(baslik_layout)

        # --- FORM ALANI ---
        form_layout = QVBoxLayout()
        form_layout.setSpacing(6)
        
        lbl_rol = QLabel("ROL ADI")
        lbl_rol.setStyleSheet("font-size: 11px; font-weight: 800; color: #8A9BC0; letter-spacing: 1px;")
        
        self.rol_adi_input = QLineEdit()
        self.rol_adi_input.setPlaceholderText("Örn: Klinik Sorumlusu")
        self.rol_adi_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                color: #0A1F5C;
                border: 2px solid #E2E8F0;
                border-radius: 10px;
                padding: 8px 14px; /* Dikey boşluk 12px'den 8px'e düşürüldü */
                min-height: 24px;  /* Yazının sığması için minimum yükseklik eklendi */
                font-size: 14px;
                font-weight: 700;
            }
            QLineEdit:focus {
                border: 2px solid #3B82F6;
                background-color: #F0F9FF;
            }
        """)
        golge_ekle(self.rol_adi_input, blur=15, alpha=15, dy=3)
        
        form_layout.addWidget(lbl_rol)
        form_layout.addWidget(self.rol_adi_input)
        layout.addLayout(form_layout)
        
        layout.addStretch()

        # --- BUTONLAR ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_iptal = QPushButton("İptal")
        btn_iptal.setCursor(Qt.PointingHandCursor)
        btn_iptal.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #64748B;
                border: 2px solid #E2E8F0;
                border-radius: 10px;
                padding: 12px 0;
                font-weight: 800;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #F1F5F9; color: #0F172A; }
        """)
        
        btn_kaydet = QPushButton("Kaydet")
        btn_kaydet.setCursor(Qt.PointingHandCursor)
        btn_kaydet.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 0;
                font-weight: 800;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E3A8A; }
        """)
        golge_ekle(btn_kaydet)
        
        btn_iptal.clicked.connect(self.reject)
        btn_kaydet.clicked.connect(self.kaydet_tetikle)
        
        btn_layout.addWidget(btn_iptal, 1)
        btn_layout.addWidget(btn_kaydet, 2) 
        layout.addLayout(btn_layout)

    def kaydet_tetikle(self):
        rol_adi = self.rol_adi_input.text().strip()
        if not rol_adi:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen rol adını giriniz.")
            return
            
        payload = {"rol_adi": rol_adi}
        headers = {"Authorization": f"Bearer {self.token}"}
        hedef_url = f"{self.api_url}/api/roller" 
        
        try:
            res = requests.post(hedef_url, json=payload, headers=headers)
            if res.status_code in (200, 201):
                QMessageBox.information(self, "Başarılı", f"'{rol_adi}' rolü başarıyla oluşturuldu.")
                self.accept()
            else:
                QMessageBox.critical(self, "Sunucu Hatası", f"Kayıt başarısız:\n{res.text}")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı:\n{str(e)}")


def golge_ekle(widget, blur=15, alpha=15, dy=3):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(10, 31, 92, alpha))
    widget.setGraphicsEffect(eff)

# --- KAYAN ANAHTAR (TOGGLE SWITCH) SINIFI ---
class KayanAnahtar(QCheckBox):
    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setFixedSize(46, 24) # Butonun genişlik ve yüksekliği
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pozisyon = 2 # Kapalı haldeki başlangıç pozisyonu

    @Property(float)
    def pozisyon(self):
        return self._pozisyon

    @pozisyon.setter
    def pozisyon(self, pos):
        self._pozisyon = pos
        self.update()

    def hitButton(self, pos):
        return self.contentsRect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Arka plan rengi
        p.setPen(Qt.PenStyle.NoPen)
        kutu = QRect(0, 0, self.width(), self.height())
        if self.isChecked():
            p.setBrush(QColor("#2563EB")) # Aktifse mavi
        else:
            p.setBrush(QColor("#CBD5E1")) # Pasifse gri
        p.drawRoundedRect(kutu, 12, 12)

        # Kayan beyaz yuvarlak
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(self._pozisyon, 2, 20, 20))

    def nextCheckState(self):
        super().nextCheckState()
        # Kayma animasyonu
        self.anim = QPropertyAnimation(self, b"pozisyon")
        self.anim.setDuration(200) # Milisaniye cinsinden kayma hızı
        self.anim.setEndValue(24 if self.isChecked() else 2)
        self.anim.start()

# --- ROL DÜZENLE DİYALOĞU ---
# --- ROL DÜZENLE DİYALOĞU ---
class RolDuzenleDialog(QDialog):
    def __init__(self, api_url, token, roller, rol_izin_map, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.roller = roller
        self.rol_izin_map = rol_izin_map
        
        self.setWindowTitle("TKYS — Rol Düzenle")
        self.setFixedSize(450, 380) # Pencere boyutu biraz küçültülüp toparlandı
        self.setStyleSheet("QDialog { background-color: #F8FAFC; }")
        
        self.arayuzu_olustur()
        
        if self.roller:
            self.rol_secildi()
            
    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # --- ÜST BAŞLIK KARTI ---
        baslik_layout = QHBoxLayout()
        
        ikon = QLabel("✏️")
        ikon.setStyleSheet("font-size: 24px; background: #E0E7FF; border-radius: 12px; padding: 8px;")
        ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        baslik_metin = QVBoxLayout()
        baslik_metin.setSpacing(2)
        ana_baslik = QLabel("Rol Düzenle")
        ana_baslik.setStyleSheet("font-size: 18px; font-weight: 900; color: #0A1F5C;")
        alt_baslik = QLabel("Sistemdeki mevcut rolü ve durumunu güncelleyin")
        alt_baslik.setStyleSheet("font-size: 12px; color: #6B7FA8;")
        
        baslik_metin.addWidget(ana_baslik)
        baslik_metin.addWidget(alt_baslik)
        
        baslik_layout.addWidget(ikon)
        baslik_layout.addLayout(baslik_metin)
        baslik_layout.addStretch()
        layout.addLayout(baslik_layout)

        # --- FORM ALANI ---
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)
        
        # Rol Seçimi
        lbl_secim = QLabel("DÜZENLENECEK ROL")
        lbl_secim.setStyleSheet("font-size: 11px; font-weight: 800; color: #8A9BC0; letter-spacing: 1px;")
        
        self.combo_roller = QComboBox()
        for rol in self.roller:
            if rol["rol_adi"].upper() == "ADMIN":
                continue
            self.combo_roller.addItem(rol.get("gorunen_ad") or rol["rol_adi"], userData=rol["rol_id"])
        self.combo_roller.currentIndexChanged.connect(self.rol_secildi)
        self.combo_roller.setStyleSheet("""
            QComboBox {
                background-color: white; color: #0A1F5C;
                border: 2px solid #E2E8F0; border-radius: 10px;
                padding: 8px 14px; min-height: 24px;
                font-size: 14px; font-weight: 700;
            }
            QComboBox:focus { border: 2px solid #3B82F6; background-color: #F0F9FF; }
            QComboBox::drop-down { border: none; width: 30px; }
        """)
        golge_ekle(self.combo_roller)
        
        # Görünen Ad (ETİKET GÜNCELLENDİ)
        lbl_ad = QLabel("ROL ADI DÜZENLE")
        lbl_ad.setStyleSheet("font-size: 11px; font-weight: 800; color: #8A9BC0; letter-spacing: 1px; margin-top: 5px;")
        
        self.input_ad = QLineEdit()
        self.input_ad.setStyleSheet("""
            QLineEdit {
                background-color: white; color: #0A1F5C;
                border: 2px solid #E2E8F0; border-radius: 10px;
                padding: 8px 14px; min-height: 24px;
                font-size: 14px; font-weight: 700;
            }
            QLineEdit:focus { border: 2px solid #3B82F6; background-color: #F0F9FF; }
        """)
        golge_ekle(self.input_ad)
        
        # Aktiflik Durumu
        lbl_aktiflik = QLabel("DURUM (AKTİF/PASİF)")
        lbl_aktiflik.setStyleSheet("font-size: 11px; font-weight: 800; color: #8A9BC0; letter-spacing: 1px; margin-top: 5px;")
        
        anahtar_satiri = QHBoxLayout()
        self.switch_aktif = KayanAnahtar() # Önceki mesajda eklediğimiz sınıf
        
        self.lbl_durum_metin = QLabel("Aktif")
        self.lbl_durum_metin.setStyleSheet("font-size: 14px; font-weight: 700; color: #2563EB;")
        self.switch_aktif.toggled.connect(self.durum_metni_guncelle)
        
        anahtar_satiri.addWidget(self.switch_aktif)
        anahtar_satiri.addWidget(self.lbl_durum_metin)
        anahtar_satiri.addStretch()
        
        form_layout.addWidget(lbl_secim)
        form_layout.addWidget(self.combo_roller)
        form_layout.addWidget(lbl_ad)
        form_layout.addWidget(self.input_ad)
        form_layout.addWidget(lbl_aktiflik)
        form_layout.addLayout(anahtar_satiri)
        
        layout.addLayout(form_layout)
        layout.addStretch()

        # --- BUTONLAR ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_iptal = QPushButton("İptal")
        btn_iptal.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_iptal.setStyleSheet("""
            QPushButton {
                background-color: white; color: #64748B;
                border: 2px solid #E2E8F0; border-radius: 10px;
                padding: 12px 0; font-weight: 800; font-size: 13px;
            }
            QPushButton:hover { background-color: #F1F5F9; color: #0F172A; }
        """)
        btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Kaydet")
        self.btn_kaydet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_kaydet.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; color: white;
                border: none; border-radius: 10px;
                padding: 12px 0; font-weight: 800; font-size: 13px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E3A8A; }
        """)
        self.btn_kaydet.clicked.connect(self.rol_kaydet)
        golge_ekle(self.btn_kaydet)
        
        btn_layout.addWidget(btn_iptal, 1)
        btn_layout.addWidget(self.btn_kaydet, 2)
        layout.addLayout(btn_layout)

    def durum_metni_guncelle(self, durum):
        if durum:
            self.lbl_durum_metin.setText("Aktif")
            self.lbl_durum_metin.setStyleSheet("font-size: 14px; font-weight: 700; color: #2563EB;")
        else:
            self.lbl_durum_metin.setText("Pasif")
            self.lbl_durum_metin.setStyleSheet("font-size: 14px; font-weight: 700; color: #94A3B8;")

    def rol_secildi(self):
        rol_id = self.combo_roller.currentData()
        rol_adi = self.combo_roller.currentText()
        self.input_ad.setText(rol_adi)
        
        aktif_durumu = True
        for rol in self.roller:
            if rol["rol_id"] == rol_id:
                aktif_durumu = rol.get("aktif_mi", True)
                break
                
        self.switch_aktif.setChecked(aktif_durumu)
        self.switch_aktif._pozisyon = 24 if aktif_durumu else 2
        self.durum_metni_guncelle(aktif_durumu)

    def rol_var_mi(self, gorunen_ad, rol_id):
        for rol in self.roller:
            if rol.get("gorunen_ad") == gorunen_ad and rol["rol_id"] != rol_id:
                return True
        return False  
            
    def rol_kaydet(self):
        rol_id = self.combo_roller.currentData()
        yeni_ad = self.input_ad.text().strip()
        
        if not yeni_ad:
            QMessageBox.warning(self, "Uyarı", "Rol adı boş olamaz.")
            return
        if self.rol_var_mi(yeni_ad, rol_id):
            QMessageBox.warning(self, "Uyarı", f"'{yeni_ad}' isminde başka bir rol var.")
            return
    
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            data = {
                "gorunen_ad": yeni_ad,
                "aktif_mi": self.switch_aktif.isChecked()
            }
            yanit = requests.put(f"{self.api_url}/api/roller/{rol_id}", json=data, headers=headers)
            if yanit.status_code == 200:
                self.accept()
            else:
                QMessageBox.warning(self, "Hata", f"Güncellenemedi. Kod: {yanit.status_code}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Sunucu hatası:\n{e}")

class IzinDuzenleDialog(QDialog):
    NOT_EK_YUKSEKLIK = 110       # not kutusu görününce pencerenin uzayacağı miktar (px)

    def __init__(self, api_url, token, izin_id, roller, matris_verisi, ebeveyn=None):
        super().__init__(ebeveyn)
        self.api_url = api_url
        self.token = token
        self.izin_id = izin_id
        self.roller = roller              # Sistemdeki tüm roller
        self.matris_verisi = matris_verisi # Mevcut izin-rol eşleşmeleri
        
        # Seçilen iznin detayını bulalım
        self.secilen_izin = None
        for izin in matris_verisi.get("izinler", []):
            if izin["izin_id"] == izin_id:
                self.secilen_izin = izin
                break

        # Bu izin tek başına sekme açmıyorsa (örn. bir sayfanın içindeki düğmeyi açıyorsa) yöneticiye not gösterilir.
        self.bagimlilik_notu = None
        if self.secilen_izin:
            self.bagimlilik_notu = izin_bagimliliklari.not_getir(self.secilen_izin["izin_adi"], matris_verisi)

        self.setWindowTitle("TKYS — İzin ve Rol Yetki Düzenleme")
        self.setFixedSize(480, 550 + (self.NOT_EK_YUKSEKLIK if self.bagimlilik_notu else 0))
        self.setStyleSheet("QDialog { background-color: #F8FAFC; }")
        
        self.rol_checkboxlar = {} # Hangi rolde hangi checkbox var tutmak için
        self.arayuzu_olustur()
        self.verileri_doldur()

    def arayuzu_olustur(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # --- ÜST BAŞLIK ---
        baslik_layout = QHBoxLayout()
        ikon = QLabel("⚙️")
        ikon.setStyleSheet("font-size: 24px; background: #E0E7FF; border-radius: 12px; padding: 8px;")
        ikon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        baslik_metin = QVBoxLayout()
        baslik_metin.setSpacing(2)
        ana_baslik = QLabel("İzin & Rol Yetkilerini Düzenle")
        ana_baslik.setStyleSheet("font-size: 16px; font-weight: 900; color: #0A1F5C;")
        alt_baslik = QLabel("Seçilen iznin hangi rollerde geçerli olacağını ayarlayın")
        alt_baslik.setStyleSheet("font-size: 11px; color: #6B7FA8;")
        
        baslik_metin.addWidget(ana_baslik)
        baslik_metin.addWidget(alt_baslik)
        baslik_layout.addWidget(ikon)
        baslik_layout.addLayout(baslik_metin)
        baslik_layout.addStretch()
        layout.addLayout(baslik_layout)

        # --- FORM / İZİN BİLGİSİ ---
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)
        
        lbl_ad = QLabel("DÜZENLENEN İZİN")
        lbl_ad.setStyleSheet("font-size: 11px; font-weight: 800; color: #8A9BC0; letter-spacing: 1px;")
        
        self.input_izin_adi = QLineEdit()
        self.input_izin_adi.setReadOnly(True) # İzin adı sadece okunur (salt okunur)
        self.input_izin_adi.setStyleSheet("""
            QLineEdit {
                background-color: #F1F5F9; color: #0A1F5C;
                border: 2px solid #E2E8F0; border-radius: 10px;
                padding: 8px 14px; font-size: 14px; font-weight: 700;
            }
        """)
        
        form_layout.addWidget(lbl_ad)
        form_layout.addWidget(self.input_izin_adi)
        layout.addLayout(form_layout)

        # --- BAĞIMLILIK NOTU (yalnızca gerekiyorsa) ---
        self.lbl_bagimlilik_notu = QLabel(f"ⓘ  {self.bagimlilik_notu}" if self.bagimlilik_notu else "")
        self.lbl_bagimlilik_notu.setObjectName("bagimlilikNotu")
        self.lbl_bagimlilik_notu.setWordWrap(True)
        self.lbl_bagimlilik_notu.setStyleSheet(
            "QLabel#bagimlilikNotu { background-color: #FFF7E0; color: #7A5200; border: 1px solid #F2D58A; "
            "border-radius: 10px; padding: 10px 12px; font-size: 12px; }"
        )
        self.lbl_bagimlilik_notu.setVisible(bool(self.bagimlilik_notu))
        layout.addWidget(self.lbl_bagimlilik_notu)

        # --- ROLLER VE KUTUCUKLAR (KAYDIRILABİLİR ALAN) ---
        lbl_roller_baslik = QLabel("BU İZNİN GEÇERLİ OLACAĞI ROLLER")
        lbl_roller_baslik.setStyleSheet("font-size: 11px; font-weight: 800; color: #8A9BC0; letter-spacing: 1px; margin-top: 5px;")
        layout.addWidget(lbl_roller_baslik)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 2px solid #E2E8F0; border-radius: 10px; background-color: white; }")
        
        scroll_icerik = QWidget()
        self.grid_roller = QVBoxLayout(scroll_icerik)
        self.grid_roller.setContentsMargins(16, 16, 16, 16)
        self.grid_roller.setSpacing(10)

        # Roller için dinamik checkboxlar oluşturuluyor
        rol_izin_map = self.matris_verisi.get("rol_izin_map", {})
        
        for rol in self.roller:
            rol_id = rol["rol_id"]
            rol_adi_teknik = rol["rol_adi"].upper()
            
            # --- ADMIN ROLÜNÜ BURADA FİLTRELİYORUZ ---
            if rol_adi_teknik == "ADMIN":
                continue
            gorunen_rol_adi = rol.get("gorunen_ad") or rol["rol_adi"]
            
            chk = QCheckBox(gorunen_rol_adi)
            chk.setStyleSheet("""
                QCheckBox { font-size: 13px; font-weight: 700; color: #0A1F5C; spacing: 8px; }
                QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 2px solid #CBD5E1; background: white; }
                QCheckBox::indicator:checked { background: #2563EB; border-color: #2563EB; }
            """)
            
            # Bu izin bu rolde var mı kontrol et
            verilmis = self.izin_bu_rolde_var_mi(rol_id, rol_izin_map)
            chk.setChecked(verilmis)
            
            self.rol_checkboxlar[rol_id] = chk
            self.grid_roller.addWidget(chk)

        # self.grid_roller.addStretch()
        scroll.setWidget(scroll_icerik)
        layout.addWidget(scroll)

        # --- BUTONLAR ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        btn_iptal = QPushButton("İptal")
        btn_iptal.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_iptal.setStyleSheet("""
            QPushButton {
                background-color: white; color: #64748B;
                border: 2px solid #E2E8F0; border-radius: 10px;
                padding: 12px 0; font-weight: 800; font-size: 13px;
            }
            QPushButton:hover { background-color: #F1F5F9; color: #0F172A; }
        """)
        btn_iptal.clicked.connect(self.reject)
        
        self.btn_kaydet = QPushButton("Değişiklikleri Kaydet")
        self.btn_kaydet.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_kaydet.setStyleSheet("""
            QPushButton {
                background-color: #2563EB; color: white;
                border: none; border-radius: 10px;
                padding: 12px 0; font-weight: 800; font-size: 13px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.btn_kaydet.clicked.connect(self.kaydet)
        
        btn_layout.addWidget(btn_iptal, 1)
        btn_layout.addWidget(self.btn_kaydet, 2)
        layout.addLayout(btn_layout)

    def izin_bu_rolde_var_mi(self, rol_id, rol_izin_map):
        # rol_izin_map sözlüğünde str(rol_id) anahtar olarak saklanıyor olabilir
        izin_listesi = rol_izin_map.get(str(rol_id)) or rol_izin_map.get(rol_id, [])
        return self.izin_id in izin_listesi

    def _rolun_izin_kodlari(self, rol_id):
        """Rolün şu an sahip olduğu izinlerin kodları (matris verisinden)."""
        harita = self.matris_verisi.get("rol_izin_map", {})
        idler = set(harita.get(str(rol_id)) or harita.get(rol_id, []))
        id_kod = {izin["izin_id"]: izin["izin_adi"] for izin in self.matris_verisi.get("izinler", [])}
        return {id_kod[i] for i in idler if i in id_kod}

    def onkosul_engeli(self):
        """Bu izin, ön koşulu olmayan bir role YENİ verilmek isteniyorsa açıklayıcı uyarı metni; sorun yoksa None.

        Ön koşul: izin bir sayfanın içindeki düğmeyi açıyorsa o sayfayı açan izin (örn. Rol atama için Kullanıcı
        oluşturma). Zaten verilmiş olanlara dokunulmaz; yalnızca bu kayıtta yeni işaretlenen roller denetlenir."""
        if not self.secilen_izin:
            return None
        kod = self.secilen_izin["izin_adi"]
        tablo = izin_bagimliliklari.onkosullari_getir()
        etiketler = izin_bagimliliklari.etiketler_matristen(self.matris_verisi)
        harita = self.matris_verisi.get("rol_izin_map", {})

        eksik_roller = []
        secenekler = None
        for rol in self.roller:
            rol_id = rol["rol_id"]
            kutu = self.rol_checkboxlar.get(rol_id)
            if kutu is None or not kutu.isChecked() or self.izin_bu_rolde_var_mi(rol_id, harita):
                continue                                           # yalnızca bu kayıtta yeni verilen roller
            eksik = izin_bagimliliklari.eksik_onkosullar(kod, self._rolun_izin_kodlari(rol_id), tablo)
            if not eksik:
                continue
            if not any(k in etiketler for _, kodlar in eksik for k in kodlar):
                continue                                           # ön koşul izni sistemde tanımsız: engellenemez
            secenekler = eksik
            eksik_roller.append(rol.get("gorunen_ad") or rol["rol_adi"])

        if not eksik_roller:
            return None
        gerekli = izin_bagimliliklari.onkosul_metni(secenekler, etiketler)
        sayfalar = ", ".join(f"'{sayfa}'" for sayfa, _ in secenekler)
        roller = "\n".join(f"  •  {ad}" for ad in eksik_roller)
        return (
            f"Bu iznin verilebilmesi için önce {gerekli} izninin olması gerekiyor.\n\n"
            f"Bu izin {sayfalar} sayfasının içinde çalışır; o sayfa {gerekli} izni olmadan görünmez.\n\n"
            f"Bu izne sahip olmayan roller:\n{roller}\n\n"
            f"Önce ilgili rollere {gerekli} iznini verin, sonra bu izni verebilirsiniz."
        )

    def verileri_doldur(self):
        if self.secilen_izin:
            ad = self.secilen_izin.get("gorunen_ad") or self.secilen_izin["izin_adi"]
            self.input_izin_adi.setText(ad)

    def kaydet(self):
        # 0. Ön koşulu olmayan bir role bağlı izin verilmek isteniyorsa kaydetmeden önce uyar
        engel = self.onkosul_engeli()
        if engel:
            QMessageBox.warning(self, "Önce bağlı izin gerekli", engel)
            return

        # 1. Hangi rollerin tikli olduğunu bulalım
        verilen_rol_idleri = []
        for rol_id, chk in self.rol_checkboxlar.items():
            if chk.isChecked():
                verilen_rol_idleri.append(int(rol_id))

        # ADMIN arayüzde gizlidir ancak backend tam rol listesini bekler.
        # ADMIN izni her kaydetme işleminde korunmalıdır.
        admin_rol_idleri = [
            int(rol["rol_id"])
            for rol in self.roller
            if str(rol.get("rol_adi", "")).strip().upper() == "ADMIN"
        ]

        if not admin_rol_idleri:
            QMessageBox.warning(
                self,
                "Hata",
                "ADMIN rolü yüklenemedi. İzinler kaydedilemedi."
            )
            return

        for admin_id in admin_rol_idleri:
            if admin_id not in verilen_rol_idleri:
                verilen_rol_idleri.append(admin_id)

        # 2. Sunucunun beklediği JSON gövdesini (payload) hazırlayalım
        gorunen_ad = self.input_izin_adi.text().strip()
        payload = {
            "gorunen_ad": gorunen_ad,
            "verilen_rol_idleri": verilen_rol_idleri
        }

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            # 3. Sunucudaki doğru PUT rotasına istek atalım (/api/izinler/{izin_id})
            yanit = requests.put(f"{self.api_url}/api/izinler/{self.izin_id}", json=payload, headers=headers)
            
            if yanit.status_code == 200:
                QMessageBox.information(self, "Başarılı", "İzin yetkileri başarıyla güncellendi.")
                self.accept()
            else:
                # Sunucudan gelen hata mesajını detaylı gösterelim
                hata_detayi = yanit.json().get("detail", f"Sunucu Kodu: {yanit.status_code}")
                QMessageBox.warning(self, "Hata", f"Güncellenemedi:\n{hata_detayi}")
        except Exception as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı:\n{e}")