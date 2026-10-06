import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout)
from PySide6.QtCore import Qt

class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BKYS — Travma Uygulama ve Araştırma Merkezi")
        self.resize(1100, 700)
        
        # Genel uygulama arkaplanı (Açık kurumsal gri)
        self.setStyleSheet("background-color: #F4F6F9; font-family: 'Segoe UI', Arial, sans-serif;")
        
        # ANA MERKEZ WIDGET
        ana_widget = QWidget()
        self.setCentralWidget(ana_widget)
        
        # Ana Düzen: Solda Sidebar, Sağda İçerik Alanı (Yatay yerleşim)
        ana_layout = QHBoxLayout(ana_widget)
        ana_layout.setContentsMargins(0, 0, 0, 0)
        ana_layout.setSpacing(0)
        
        # ==========================================
        # 1. SOL MENÜ (SIDEBAR)
        # ==========================================
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #1E293B; color: white;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 30, 20, 20)
        
        # Sidebar Logo / Başlık
        logo_label = QLabel("<b>BKYS v1.0</b><br><span style='font-size: 11px; color: #94A3B8;'>Merkezi Yönetim Sistemi</span>")
        logo_label.setStyleSheet("font-size: 16px; color: #FFFFFF; margin-bottom: 20px;")
        sidebar_layout.addWidget(logo_label)
        
        # Menü Butonları Stil Fonksiyonu
        menu_stil = """
            QPushButton {
                background-color: transparent;
                color: #CBD5E1;
                border: none;
                text-align: left;
                padding: 12px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #FFFFFF;
            }
        """
        
        btn_dashboard = QPushButton("📊  Ana Panel (Dashboard)")
        btn_randevu = QPushButton("📅  Randevu Yönetimi")
        btn_cihaz = QPushButton("⚙️  Cihaz Envanteri")
        btn_oda = QPushButton("🚪  Oda & Takvim")
        btn_ayar = QPushButton("🛠️  Yönetici Konsolu")
        
        for btn in [btn_dashboard, btn_randevu, btn_cihaz, btn_oda, btn_ayar]:
            btn.setStyleSheet(menu_stil)
            sidebar_layout.addWidget(btn)
            
        sidebar_layout.addStretch() # Butonları yukarı iter
        
        # Çıkış Butonu
        btn_cikis = QPushButton("🚪  Güvenli Çıkış")
        btn_cikis.setStyleSheet("""
            QPushButton {
                background-color: #7F1D1D;
                color: #FCA5A5;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #991B1B; color: white; }
        """)
        sidebar_layout.addWidget(btn_cikis)
        
        ana_layout.addWidget(sidebar)
        
        # ==========================================
        # 2. SAĞ TARAF (İÇERİK VE HEADER ALANI)
        # ==========================================
        sag_taraf_widget = QWidget()
        sag_taraf_layout = QVBoxLayout(sag_taraf_widget)
        sag_taraf_layout.setContentsMargins(30, 25, 30, 25)
        sag_taraf_layout.setSpacing(20)
        
        # Üst Header
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: white; border-radius: 8px; padding: 15px;")
        header_layout = QHBoxLayout(header_frame)
        
        baslik = QLabel("<b>Operasyonel Kontrol Paneli</b>")
        baslik.setStyleSheet("font-size: 18px; color: #0F172A;")
        
        aktif_kullanici = QLabel("👤 Aktif Personel: <b>Psikolog (Test)</b>")
        aktif_kullanici.setStyleSheet("font-size: 13px; color: #64748B;")
        
        header_layout.addWidget(baslik)
        header_layout.addStretch()
        header_layout.addWidget(aktif_kullanici)
        
        sag_taraf_layout.addWidget(header_frame)
        
        # Modern Grid Kartlar Alanı (İçerik)
        icerik_grid = QGridLayout()
        icerik_grid.setSpacing(20)
        
        # Örnek Şık Kartlar Oluşturalım
        def kart_olustur(baslik_metin, deger_metin, renk):
            kart = QFrame()
            kart.setStyleSheet(f"background-color: white; border-radius: 8px; border-left: 5px solid {renk};")
            k_layout = QVBoxLayout(kart)
            
            b_label = QLabel(baslik_metin)
            b_label.setStyleSheet("font-size: 13px; color: #64748B; font-weight: bold;")
            
            d_label = QLabel(deger_metin)
            d_label.setStyleSheet(f"font-size: 22px; color: {renk}; font-weight: bold;")
            
            k_layout.addWidget(b_label)
            k_layout.addWidget(d_label)
            return kart

        # Kartları yerleştiriyoruz
        icerik_grid.addWidget(kart_olustur("Aktif Randevular", "12", "#1A73E8"), 0, 0)
        icerik_grid.addWidget(kart_olustur("Kullanılabilir Cihazlar", "24", "#10B981"), 0, 1)
        icerik_grid.addWidget(kart_olustur("Bakımdaki Cihazlar", "2", "#F59E0B"), 0, 2)
        
        # Büyük Alt Alan (Modül Yükleme Alanı)
        alt_alan = QFrame()
        alt_alan.setStyleSheet("background-color: white; border-radius: 8px;")
        alt_layout = QVBoxLayout(alt_alan)
        
        alt_baslik = QLabel("<b>Sistem Durumu ve Hızlı Bakış</b>")
        alt_baslik.setStyleSheet("font-size: 15px; color: #1E293B; margin-bottom: 10px;")
        
        alt_aciklama = QLabel(
            "• Veritabanı Mimarisi: PostgreSQL (5NF Uyumlu)\n"
            "• API Durumu: FastAPI Aktif ve Çalışır Durumda\n"
            "• Güvenlik Duvarı: JWT & Bcrypt Entegrasyon Hazır"
        )
        alt_aciklama.setStyleSheet("font-size: 14px; color: #475569; line-height: 160%;")
        
        alt_layout.addWidget(alt_baslik)
        alt_layout.addWidget(alt_aciklama)
        alt_layout.addStretch()
        
        sag_taraf_layout.addLayout(icerik_grid)
        sag_taraf_layout.addWidget(alt_alan)
        
        ana_layout.addWidget(sag_taraf_widget)
        
        # Alt Durum Çubuğu
        self.statusBar().showMessage("Sistem Çevrim İçi | Güvenlik Modülü: Aktif | 5NF Veritabanı Bağlı")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pencere = AnaPencere()
    pencere.show()
    sys.exit(app.exec())