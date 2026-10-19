import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QLabel, 
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

class DashboardEkrani(QWidget):
    def __init__(self, api_url, token):
        super().__init__()
        self.api_url = api_url
        self.token = token
        
        # Ana Düzen
        ana_layout = QVBoxLayout(self)
        ana_layout.setContentsMargins(20, 20, 20, 20)
        ana_layout.setSpacing(20)

        # 1. BÖLÜM: ÜST İSTATİSTİK KARTLARI
        kart_layout = QGridLayout()
        kart_layout.setSpacing(15)
        
        self.lbl_degerler = {}
        
        # Kartlar: Başlık, JSON Anahtarı, Renk, Satır, Sütun
        kartlar = [
            ("Bugünkü Randevular", "bugunku_randevu_sayisi", "#3498DB", 0, 0),
            ("Aktif Cihazlar", "aktif_cihaz", "#27AE60", 0, 1),
            ("Bakımdaki Cihazlar", "bakimdaki_cihaz", "#F39C12", 0, 2),
            ("Arızalı Cihazlar", "arizali_cihaz", "#E74C3C", 1, 0),
            ("Açık Arızalar", "acik_ariza_sayisi", "#C0392B", 1, 1),
            ("Toplam Cihaz", "toplam_cihaz", "#8E44AD", 1, 2)
        ]

        for baslik, anahtar, renk, r, c in kartlar:
            kart, lbl_deger = self.kart_olustur(baslik, renk)
            self.lbl_degerler[anahtar] = lbl_deger
            kart_layout.addWidget(kart, r, c)
            
        ana_layout.addLayout(kart_layout)

        # 2. BÖLÜM: YAKLAŞAN İŞLEMLER TABLOSU
        lbl_tablo_baslik = QLabel("⚠️ Yaklaşan Bakımlar ve Kalibrasyonlar (Son 30 Gün)")
        lbl_tablo_baslik.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50; margin-top: 15px;")
        ana_layout.addWidget(lbl_tablo_baslik)

        self.tablo = QTableWidget(0, 4)
        self.tablo.setHorizontalHeaderLabels(["Cihaz", "İşlem Türü", "Son Tarih", "Kalan Gün"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)

        # --- İŞTE TABLOYU KURTARAN KODLAR ---
        from PySide6.QtWidgets import QSizePolicy
        self.tablo.setMinimumHeight(250) # Tablonun boyunu uzattık
        self.tablo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) # Aşağı doğru esnemesine izin verdik
        # ------------------------------------

        self.tablo.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #BDC3C7; border-radius: 5px; }
            QHeaderView::section { background-color: #34495E; color: white; padding: 8px; font-weight: bold; border: none; }
        """)
        ana_layout.addWidget(self.tablo)

        # Sayfa açılır açılmaz verileri çeker
        self.verileri_yukle()

    def kart_olustur(self, baslik, renk):
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: white; border-radius: 8px;
                border-left: 6px solid {renk};
                border-top: 1px solid #E5E7EB; border-right: 1px solid #E5E7EB; border-bottom: 1px solid #E5E7EB;
            }}
        """)
        layout = QVBoxLayout(frame)
        
        lbl_baslik = QLabel(baslik)
        lbl_baslik.setStyleSheet("font-size: 14px; color: #7F8C8D; font-weight: bold; border: none;")
        
        lbl_deger = QLabel("0")
        lbl_deger.setStyleSheet(f"font-size: 28px; color: {renk}; font-weight: bold; border: none;")
        lbl_deger.setAlignment(Qt.AlignLeft)
        
        layout.addWidget(lbl_baslik)
        layout.addWidget(lbl_deger)
        
        return frame, lbl_deger

    def verileri_yukle(self):
        # 1. Özet Verilerini Çekip Kartlara Basma
        try:
            res_ozet = requests.get(f"{self.api_url}/api/dashboard/ozet", headers={"Authorization": f"Bearer {self.token}"})
            if res_ozet.status_code == 200:
                veri = res_ozet.json()
                for anahtar, lbl in self.lbl_degerler.items():
                    lbl.setText(str(veri.get(anahtar, 0)))
        except Exception as e:
            print("Özet yükleme hatası:", e)

        # 2. Yaklaşan İşlemleri Çekip Tabloya Basma
        self.tablo.setRowCount(0)
        try:
            res_islem = requests.get(f"{self.api_url}/api/dashboard/yaklasan-islemler", headers={"Authorization": f"Bearer {self.token}"})
            if res_islem.status_code == 200:
                islemler = res_islem.json()
                
                # TABLOYU DOLDURMA MANTIĞI SAĞLAMA ALINDI
                self.tablo.setRowCount(len(islemler))
                
                for i, islem in enumerate(islemler):
                    item_cihaz = QTableWidgetItem(islem["cihaz_adi"])
                    item_turu = QTableWidgetItem(islem["islem_turu"])
                    item_turu.setTextAlignment(Qt.AlignCenter)
                    item_tarih = QTableWidgetItem(islem["tarih"])
                    item_tarih.setTextAlignment(Qt.AlignCenter)
                    item_kalan = QTableWidgetItem(f"{islem['kalan_gun']} Gün")
                    item_kalan.setTextAlignment(Qt.AlignCenter)

                    arkaplan = QColor("#FADBD8") if islem["durum_kodu"] == "KRITIK" else QColor("#FCF3CF")
                    metin_renk = QColor("#922B21") if islem["durum_kodu"] == "KRITIK" else QColor("#9A7D0A")

                    for item in (item_cihaz, item_turu, item_tarih, item_kalan):
                        item.setBackground(arkaplan)
                        item.setForeground(metin_renk)
                        
                    self.tablo.setItem(i, 0, item_cihaz)
                    self.tablo.setItem(i, 1, item_turu)
                    self.tablo.setItem(i, 2, item_tarih)
                    self.tablo.setItem(i, 3, item_kalan)
        except Exception as e:
            print("Tablo yükleme hatası:", e) # Sessizce yutmasını engelledik!