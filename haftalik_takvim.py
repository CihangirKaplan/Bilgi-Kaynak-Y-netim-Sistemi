import sys
import requests
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QCalendarWidget, 
    QCheckBox, QComboBox, QApplication, QFrame
)
from PySide6.QtCore import Qt, QDate, QDateTime
from PySide6.QtGui import QColor, QFont

# ======================================================================
#  CAL-002: HAFTALIK TAKVİM ARAYÜZÜ (Google Takvim Tarzı)
# ======================================================================
class HaftalikTakvimEkrani(QWidget):
    def __init__(self, api_url="", token=""):
        super().__init__()
        self.api_url = api_url
        self.token = token
        
        self.mevcut_tarih = QDate.currentDate()
        self.saatler = [f"{h:02d}:00" for h in range(8, 19)] # 08:00 - 19:00 arası
        
        self.setWindowTitle("CAL-002 - Haftalık Takvim")
        self.resize(1100, 700)
        self.setStyleSheet("background-color: #FFFFFF; font-family: 'Segoe UI', Arial;")
        
        self.init_ui()
        self.haftayi_guncelle()
        self.odalari_yukle()

    def init_ui(self):
        ana_layout = QHBoxLayout(self)
        ana_layout.setContentsMargins(10, 10, 10, 10)
        ana_layout.setSpacing(20)

        # ==================== SOL PANEL (Kenar Çubuğu) ====================
        sol_panel = QVBoxLayout()
        sol_panel.setSpacing(20)
        sol_panel.setAlignment(Qt.AlignTop)
        
        # 1. Ana Ekrana Dön Butonu (Oluştur butonu yerine eklendi)
        self.btn_ana_ekrana_don = QPushButton("←")
        self.btn_ana_ekrana_don.setFixedSize(40, 40)
        self.btn_ana_ekrana_don.setToolTip("Ana Ekrana Dön")
        self.btn_ana_ekrana_don.setCursor(Qt.PointingHandCursor)
        self.btn_ana_ekrana_don.setStyleSheet("""
            QPushButton { background-color: transparent; color: #3C4043; font-size: 26px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #E2E8F0; border-radius: 20px; }
        """)
        sol_panel.addWidget(self.btn_ana_ekrana_don)

        # 2. Mini Takvim
        self.mini_takvim = QCalendarWidget()
        self.mini_takvim.setGridVisible(False)
        self.mini_takvim.setStyleSheet("""
            QCalendarWidget QWidget { alternate-background-color: #FFFFFF; }
            QCalendarWidget QAbstractItemView:enabled { font-size: 12px; color: #3C4043; selection-background-color: #1A73E8; selection-color: white; }
            QCalendarWidget QToolButton { color: #3C4043; font-weight: bold; }
        """)
        self.mini_takvim.selectionChanged.connect(self.mini_takvimden_tarih_secildi)
        sol_panel.addWidget(self.mini_takvim)

        # 3. Filtreler (Odalar)
        lbl_takvimler = QLabel("Odalar")
        lbl_takvimler.setStyleSheet("font-weight: bold; color: #3C4043; margin-top: 10px;")
        sol_panel.addWidget(lbl_takvimler)

        # Dinamik odaların ekleneceği dikey düzen (layout)
        self.oda_layout = QVBoxLayout()
        self.oda_layout.setSpacing(10)
        sol_panel.addLayout(self.oda_layout)
        sol_panel.addStretch()

        ana_layout.addLayout(sol_panel, 1)

        # ==================== SAĞ PANEL (Ana Takvim Alanı) ====================
        sag_panel = QVBoxLayout()
        sag_panel.setSpacing(10)

        # 1. Üst Bar (Tarih Gezinme ve Görünüm Seçimi)
        ust_bar = QHBoxLayout()
        
        self.btn_bugun = QPushButton("Bugün")
        self.btn_bugun.setFixedSize(70, 35)
        self.btn_bugun.setStyleSheet("background-color: white; border: 1px solid #DADCE0; border-radius: 4px; color: #3C4043; font-weight: bold;")
        self.btn_bugun.clicked.connect(self.bugune_git)
        
        self.btn_geri = QPushButton("<")
        self.btn_geri.setFixedSize(35, 35)
        self.btn_geri.setStyleSheet("background-color: transparent; border: none; font-size: 18px; color: #5F6368;")
        self.btn_geri.clicked.connect(self.onceki_hafta)
        
        self.btn_ileri = QPushButton(">")
        self.btn_ileri.setFixedSize(35, 35)
        self.btn_ileri.setStyleSheet("background-color: transparent; border: none; font-size: 18px; color: #5F6368;")
        self.btn_ileri.clicked.connect(self.sonraki_hafta)
        
        self.lbl_ay_yil = QLabel("Ekim 2026")
        self.lbl_ay_yil.setStyleSheet("font-size: 22px; color: #3C4043;")
        
        self.cmb_gorunum = QComboBox()
        self.cmb_gorunum.addItems(["Hafta", "Gün", "Ay"])
        self.cmb_gorunum.setFixedSize(90, 35)
        self.cmb_gorunum.setStyleSheet("background-color: white; border: 1px solid #DADCE0; border-radius: 4px; padding-left: 10px; color: #3C4043;")

        ust_bar.addWidget(self.btn_bugun)
        ust_bar.addWidget(self.btn_geri)
        ust_bar.addWidget(self.btn_ileri)
        ust_bar.addWidget(self.lbl_ay_yil)
        ust_bar.addStretch()
        ust_bar.addWidget(self.cmb_gorunum)
        
        sag_panel.addLayout(ust_bar)

        # 2. Haftalık Izgara Tablosu[cite: 2]
        self.tablo = QTableWidget()
        self.tablo.setRowCount(len(self.saatler))
        self.tablo.setColumnCount(7) # 7 Gün
        self.tablo.setVerticalHeaderLabels(self.saatler)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Google Takvim benzeri temiz grid stili[cite: 2]
        self.tablo.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #DADCE0;
                border: none;
                color: #3C4043;
            }
            QHeaderView::section {
                background-color: white;
                border: none;
                border-bottom: 1px solid #DADCE0;
                border-right: 1px solid #DADCE0;
                padding: 4px;
                font-size: 12px;
                color: #70757A;
            }
        """)
        sag_panel.addWidget(self.tablo)

        ana_layout.addLayout(sag_panel, 5)

    def haftayi_guncelle(self):
        """Seçili tarihe göre haftanın günlerini hesaplar ve tablo başlıklarını günceller."""
        # Pazartesi'yi haftanın ilk günü olarak al (1=Pzt, 7=Paz)
        gun_farki = self.mevcut_tarih.dayOfWeek() - 1 
        pazartesi = self.mevcut_tarih.addDays(-gun_farki)
        
        ay_isimleri = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
        gun_isimleri = ["PZT", "SAL", "ÇAR", "PER", "CUM", "CMT", "PAZ"]
        
        basliklar = []
        for i in range(7):
            aktif_gun = pazartesi.addDays(i)
            # Örn: "PZT\n12" formatı
            basliklar.append(f"{gun_isimleri[i]}\n{aktif_gun.day()}")
            
        self.tablo.setHorizontalHeaderLabels(basliklar)
        self.lbl_ay_yil.setText(f"{ay_isimleri[pazartesi.month()-1]} {pazartesi.year()}")
        
        # Mini takvimi senkronize et
        self.mini_takvim.setSelectedDate(self.mevcut_tarih)
        
        self.tablo.clearContents()
        self.verileri_doldur(pazartesi)

    def odalari_yukle(self):
        # 1. Eski verileri temizle
        for i in reversed(range(self.oda_layout.count())):
            widget = self.oda_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)

        # ÇOK ÖNEMLİ EKLENTİ: Sadece 1 odanın seçilmesine izin veren grup!
        from PySide6.QtWidgets import QButtonGroup
        self.oda_grubu = QButtonGroup(self)
        self.oda_grubu.setExclusive(True) # Bu ayar sayesinde aynı anda sadece biri seçilebilir

        try:
            api_adres = self.api_url if self.api_url else "http://127.0.0.1:8000"
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            
            cevap = requests.get(f"{api_adres}/api/odalar", headers=headers, timeout=5)
            
            if cevap.status_code == 200:
                odalar = cevap.json()
                renkler = ["#1A73E8", "#0F9D58", "#F4B400", "#DB4437", "#9C27B0", "#00BCD4", "#E67C73", "#7986CB"]
                
                for i, oda in enumerate(odalar):
                    oda_adi = oda.get("oda_adi", f"Bilinmeyen Oda {i+1}")
                    oda_id = oda.get("oda_id", i) # Oda ID'sini de saklayacağız
                    renk = oda.get("renk_kodu", renkler[i % len(renkler)])
                    
                    chk_oda = QCheckBox(oda_adi)
                    
                    # İlk odayı varsayılan olarak seçili yapıyoruz
                    if i == 0:
                        chk_oda.setChecked(True)
                        
                    stil = f"""
                        QCheckBox {{ color: #3C4043; font-size: 13px; }} 
                        QCheckBox::indicator:checked {{ 
                            background-color: {renk}; 
                            border: 1px solid {renk}; 
                        }}
                    """
                    chk_oda.setStyleSheet(stil)
                    
                    # Butonu gruba ekliyoruz ki aynı anda 2 tane seçilemesin
                    self.oda_grubu.addButton(chk_oda, id=oda_id)
                    self.oda_layout.addWidget(chk_oda)
                
                # Herhangi bir oda seçimi değiştiğinde tabloyu yeniden yükle
                self.oda_grubu.idToggled.connect(self.haftayi_guncelle)
                    
            else:
                hata_lbl = QLabel("Odalar alınamadı.")
                hata_lbl.setStyleSheet("color: #5F6368;")
                self.oda_layout.addWidget(hata_lbl)
                
        except Exception as e:
            hata_lbl = QLabel("Bağlantı hatası!")
            hata_lbl.setStyleSheet("color: #DC2626; font-weight: bold;")
            self.oda_layout.addWidget(hata_lbl)
            print("Oda çekme hatası:", e)

    def bugune_git(self):
        self.mevcut_tarih = QDate.currentDate()
        self.haftayi_guncelle()

    def onceki_hafta(self):
        self.mevcut_tarih = self.mevcut_tarih.addDays(-7)
        self.haftayi_guncelle()

    def sonraki_hafta(self):
        self.mevcut_tarih = self.mevcut_tarih.addDays(7)
        self.haftayi_guncelle()

    def mini_takvimden_tarih_secildi(self):
        self.mevcut_tarih = self.mini_takvim.selectedDate()
        self.haftayi_guncelle()

    def verileri_doldur(self, pazartesi):
        # Seçili odanın ID'sini bul
        if not hasattr(self, 'oda_grubu') or self.oda_grubu.checkedId() == -1:
            return # Henüz grup oluşmadıysa veya seçili oda yoksa çık
            
        secili_oda_id = self.oda_grubu.checkedId()
        
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        api_adres = self.api_url if self.api_url else "http://127.0.0.1:8000"
        
        try:
            # Tüm randevuları çek (İleride back-end'de direkt oda ID ile filtreleyen bir sorgu yazabilirsin)
            cevap = requests.get(f"{api_adres}/api/randevular", headers=headers, timeout=5)
            
            if cevap.status_code == 200:
                randevular = cevap.json()
                
                for r in randevular:
                    # SADECE SEÇİLİ ODAYA AİT OLANLARI FİLTRELE ve İPTAL EDİLMEMİŞLERİ GÖSTER
                    if r.get("oda_id") == secili_oda_id and r.get("durum") != "IPTAL_EDILDI":
                        
                        baslangic_zaman_metni = r.get("baslangic_zamani", "")
                        
                        # Eğer tarih boş gelmişse bu satırı atla
                        if not baslangic_zaman_metni:
                            continue
                            
                        # Metin formatındaki tarihi QDateTime nesnesine çevir (örn: '2026-10-13T10:00:00')
                        q_tarih = QDateTime.fromString(baslangic_zaman_metni.split('.')[0], "yyyy-MM-ddTHH:mm:ss")
                        
                        # Tarih bu haftanın içindeyse tabloya yerleştir
                        if q_tarih.date() >= pazartesi and q_tarih.date() <= pazartesi.addDays(6):
                            
                            # Sütunu bul (0=Pazartesi, 1=Salı ... 6=Pazar)
                            # QDate.dayOfWeek() Pazartesi'yi 1 verir, biz 0. indexten başlıyoruz
                            sutun_index = q_tarih.date().dayOfWeek() - 1 
                            
                            # Satırı bul (0=08:00, 1=09:00 ...)
                            saat = q_tarih.time().hour()
                            if 8 <= saat <= 18:
                                satir_index = saat - 8
                                
                                # Görsel bloğu oluştur
                                kod = r.get("danisan_kod_id", "Bilinmeyen")
                                item = QTableWidgetItem(f"Danışan: {kod}\nID: {r.get('randevu_id')}")
                                
                                # Seçili odanın rengini arka plan olarak kullan
                                secili_buton = self.oda_grubu.button(secili_oda_id)
                                if secili_buton:
                                    renk_kod = secili_buton.styleSheet().split("background-color: ")[1].split(";")[0]
                                    item.setBackground(QColor(renk_kod))
                                else:
                                    item.setBackground(QColor("#4285F4")) # Varsayılan Google Mavisi
                                    
                                item.setForeground(QColor("white"))
                                item.setTextAlignment(Qt.AlignCenter)
                                
                                # Eğer tabloda ilgili hücre boşsa direkt koy, doluysa üzerine ekle (çakışma durumu)
                                mevcut_item = self.tablo.item(satir_index, sutun_index)
                                if mevcut_item:
                                     yeni_metin = mevcut_item.text() + f"\n---\nDanışan: {kod}\nID: {r.get('randevu_id')}"
                                     mevcut_item.setText(yeni_metin)
                                else:
                                    self.tablo.setItem(satir_index, sutun_index, item)
                                    
        except Exception as e:
            print("Takvime randevular yerleştirilirken hata oluştu:", e)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = HaftalikTakvimEkrani()
    pencere.show()
    sys.exit(app.exec())