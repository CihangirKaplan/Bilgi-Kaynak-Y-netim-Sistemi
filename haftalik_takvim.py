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
        self.saatler = [f"{h:02d}:00" for h in range(8, 20)] # 08:00 - 19:00 arası
        
        self.setWindowTitle("CAL-002 - Haftalık Takvim")
        self.resize(1100, 700)
        self.setStyleSheet("background-color: #FFFFFF; font-family: 'Segoe UI', Arial;")
        
        self.init_ui()
        self.haftayi_guncelle()

    def init_ui(self):
        ana_layout = QHBoxLayout(self)
        ana_layout.setContentsMargins(10, 10, 10, 10)
        ana_layout.setSpacing(20)

        # ==================== SOL PANEL (Kenar Çubuğu) ====================
        sol_panel = QVBoxLayout()
        sol_panel.setSpacing(20)
        sol_panel.setAlignment(Qt.AlignTop)
        
        # 1. Oluştur Butonu (Görseldeki gibi büyük ve yuvarlak hatlı)
        self.btn_olustur = QPushButton("+ Oluştur")
        self.btn_olustur.setFixedSize(130, 45)
        self.btn_olustur.setCursor(Qt.PointingHandCursor)
        self.btn_olustur.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                color: #3C4043;
                border: 1px solid #DADCE0;
                border-radius: 22px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F8F9FA; box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3); }
        """)
        sol_panel.addWidget(self.btn_olustur)

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

        # 3. Filtreler (Takvimlerim / Odalar)
        lbl_takvimler = QLabel("Takvimlerim (Odalar)")
        lbl_takvimler.setStyleSheet("font-weight: bold; color: #3C4043; margin-top: 10px;")
        sol_panel.addWidget(lbl_takvimler)

        self.chk_oda1 = QCheckBox("Terapi Odası 1")
        self.chk_oda2 = QCheckBox("Görüntüleme Merkezi")
        self.chk_oda1.setChecked(True)
        self.chk_oda2.setChecked(True)
        # Mavi ve yeşil tik görünümü için basit stil
        chk_stil = "QCheckBox { color: #3C4043; } QCheckBox::indicator:checked { background-color: #1A73E8; border: 1px solid #1A73E8; }"
        self.chk_oda1.setStyleSheet(chk_stil)
        self.chk_oda2.setStyleSheet("QCheckBox { color: #3C4043; } QCheckBox::indicator:checked { background-color: #0F9D58; border: 1px solid #0F9D58; }")
        
        sol_panel.addWidget(self.chk_oda1)
        sol_panel.addWidget(self.chk_oda2)
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
        self.ornek_veri_doldur(pazartesi)

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

    def ornek_veri_doldur(self, pazartesi):
        """Arayüzün nasıl göründüğünü test etmek için örnek bloklar ekler."""
        # Salı günü (Sütun 1), Saat 10:00 (Satır 2)
        item1 = QTableWidgetItem("Danışan: DAN-001\nOda: Terapi 1")
        item1.setBackground(QColor("#4285F4")) # Google Mavi
        item1.setForeground(QColor("white"))
        self.tablo.setItem(2, 1, item1)

        # Perşembe günü (Sütun 3), Saat 14:00 (Satır 6)
        item2 = QTableWidgetItem("Danışan: DAN-002\nOda: MR Merkezi")
        item2.setBackground(QColor("#0F9D58")) # Google Yeşil
        item2.setForeground(QColor("white"))
        self.tablo.setItem(6, 3, item2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = HaftalikTakvimEkrani()
    pencere.show()
    sys.exit(app.exec())