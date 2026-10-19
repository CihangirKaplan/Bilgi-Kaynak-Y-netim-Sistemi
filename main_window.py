import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QStackedWidget, QScrollArea, QComboBox,
    QButtonGroup, QGraphicsDropShadowEffect, QSizePolicy, QTableWidget, QHeaderView, QAbstractItemView
)
from oda_yonetimi import OdaFormu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from randevu_ekranlari import RandevuOlusturFormu
from haftalik_takvim import HaftalikTakvimEkrani
from cihaz_ekranlari import CihazYonetimEkrani
from cihaz_rezervasyon_ekranlari import RezervasyonYonetimEkrani
from cihaz_ariza_ekranlari import ArizaYonetimEkrani
from cihaz_kalibrasyon_ekranlari import KalibrasyonYonetimEkrani
from cihaz_bakim_ekranlari import BakimYonetimEkrani # YENİ EKLENDİ!


# ======================================================================
#  1. YETKİ MATRİSİ  (E = Evet, H = Hayır)
# ======================================================================
ROLLER = ["psikolog", "memur", "mudur", "ogrenci", "asistan", "admin"]

ROL_BILGI = {
    "psikolog": {"ad": "Psikolog",          "aciklama": "Klinik Randevu ve Danışmanlık Modülü"},
    "memur":    {"ad": "Memur",             "aciklama": "Cihaz Envanteri ve Yaşam Döngüsü"},
    "mudur":    {"ad": "Müdür (Yönetici)",  "aciklama": "Yönetim Konsolu ve Operasyonel Raporlar"},
    "ogrenci":  {"ad": "Danışma Öğrencisi", "aciklama": "Danışma Masası ve Oda Takibi"},
    "asistan":  {"ad": "Proje Asistanı",    "aciklama": "Destek ve Rezervasyon Modülü"},
    "admin":    {"ad": "Sistem Admin",      "aciklama": "Tam Yetkili Sistem ve Yetki Yönetimi"},
}

IZIN_LISTESI = [
    ("Randevu oluşturma",                    "Randevu & Oda",     "EHHEHE"),
    ("Randevu düzenleme",                    "Randevu & Oda",     "EHHEHE"),
    ("Randevu iptal etme",                   "Randevu & Oda",     "EHHEHE"),
    ("Randevu takvimini görüntüleme",        "Randevu & Oda",     "EEEEEE"),
    ("Oda kullanım durumunu görüntüleme",    "Randevu & Oda",     "EEEEEE"),
    ("Oda yönetimi",                         "Randevu & Oda",     "HEEHHE"),

    ("Cihaz uygunluğunu görüntüleme",        "Cihaz Yönetimi",    "EEEHEE"),
    ("Cihaz envanterini yönetme",            "Cihaz Yönetimi",    "HEEHHE"),
    ("Cihaz rezervasyonu yapma",             "Cihaz Yönetimi",    "HEHHEE"),
    ("Cihaz ekleme",                         "Cihaz Yönetimi",    "HEEHHE"),
    ("Cihaz takip kontrol listesini yönetme","Cihaz Yönetimi",    "HEEHHE"),

    ("Bakım kayıtlarını yönetme",            "Kayıt & Bakım",     "HEEHHE"),
    ("Kalibrasyon kayıtlarını yönetme",      "Kayıt & Bakım",     "HEEHHE"),
    ("Arıza kayıtlarını yönetme",            "Kayıt & Bakım",     "HEEHHE"),
    ("Faaliyet kayıtlarını düzenleme",       "Kayıt & Bakım",     "HEEHEE"),

    ("Kullanıcı oluşturma",                  "Kullanıcı & Denetim","HHEHHE"),
    ("Personel tanımlama",                   "Kullanıcı & Denetim","HHEHHE"),
    ("Kullanıcı pasifleştirme",              "Kullanıcı & Denetim","HHEHHE"),
    ("Rol atama/değiştirme",                 "Kullanıcı & Denetim","HHEHHE"),
    ("Audit kayıtlarını inceleme",           "Kullanıcı & Denetim","HHEHHE"),
    ("Danışma masası oturumunu yönetme",     "Kullanıcı & Denetim","HEEEHE"),

    ("Yeni izin tanımlama",                  "Sistem Yönetimi",   "HHHHHE"),
    ("İzin düzenleme",                       "Sistem Yönetimi",   "HHHHHE"),
    ("Rol-izin yönetme",                     "Sistem Yönetimi",   "HHHHHE"),
    ("Rol oluşturma",                        "Sistem Yönetimi",   "HHHHHE"),
    ("Rol düzenleme",                        "Sistem Yönetimi",   "HHHHHE"),
    ("Faaliyet birimlerini yönetme",         "Sistem Yönetimi",   "HHHHHE"),
]

IZIN = {ad: (kat, kod) for ad, kat, kod in IZIN_LISTESI}

def izin_var(rol, izin_adi):
    return IZIN[izin_adi][1][ROLLER.index(rol)] == "E"

# ======================================================================
#  2. MENÜ TANIMI
# ======================================================================
MENU = [
    ("GENEL", [
        dict(ikon="📊", ad="Ana Kontrol Paneli", izin=None, dashboard=True),
    ]),
    ("KLİNİK OPERASYON", [
        dict(ikon="📅", ad="Randevu Takvimi", izin="Randevu takvimini görüntüleme",
             aciklama="Randevu takvimi ve seans planlaması",
             aksiyon=[("＋  Yeni Randevu", "Randevu oluşturma"),
                      ("✎  Randevu Düzenle", "Randevu düzenleme"),
                      ("✕  Randevu İptal Et", "Randevu iptal etme")]),
        dict(ikon="🚪", ad="Oda Kullanımı", izin="Oda kullanım durumunu görüntüleme",
             aciklama="Oda doluluk ve kullanım durumu", aksiyon=[]),
        dict(ikon="🛎️", ad="Danışma Masası", izin="Danışma masası oturumunu yönetme",
             aciklama="Danışma masası oturum yönetimi",
             aksiyon=[("▶  Oturumu Yönet", "Danışma masası oturumunu yönetme")]),
    ]),
    ("CİHAZ YAŞAM DÖNGÜSÜ", [
        dict(ikon="🔎", ad="Cihaz Uygunluğu", izin="Cihaz uygunluğunu görüntüleme",
             aciklama="Cihazların anlık uygunluk durumu", aksiyon=[]),
        dict(ikon="⚙️", ad="Cihaz Envanteri", izin="Cihaz envanterini yönetme",
             aciklama="Envanter kayıtları ve cihaz yönetimi",
             aksiyon=[("＋  Cihaz Ekle", "Cihaz ekleme"),
                      ("☑  Takip Kontrol Listesi", "Cihaz takip kontrol listesini yönetme"),
                      ("✎  Envanteri Düzenle", "Cihaz envanterini yönetme")]),
        dict(ikon="📌", ad="Cihaz Rezervasyonu", izin="Cihaz rezervasyonu yapma",
             aciklama="Cihaz rezervasyon işlemleri",
             aksiyon=[("＋  Yeni Rezervasyon", "Cihaz rezervasyonu yapma")]),
        dict(ikon="🛠️", ad="Bakım Kayıtları", izin="Bakım kayıtlarını yönetme",
             aciklama="Periyodik bakım kayıtları",
             aksiyon=[("＋  Bakım Kaydı", "Bakım kayıtlarını yönetme")]),
        dict(ikon="🎯", ad="Kalibrasyon", izin="Kalibrasyon kayıtlarını yönetme",
             aciklama="Kalibrasyon planı ve sertifikaları",
             aksiyon=[("＋  Kalibrasyon Kaydı", "Kalibrasyon kayıtlarını yönetme")]),
        dict(ikon="⚠️", ad="Arıza Kayıtları", izin="Arıza kayıtlarını yönetme",
             aciklama="Arıza bildirimi ve takibi",
             aksiyon=[("＋  Arıza Kaydı", "Arıza kayıtlarını yönetme")]),
        dict(ikon="📝", ad="Faaliyet Kayıtları", izin="Faaliyet kayıtlarını düzenleme",
             aciklama="Faaliyet kayıtlarının düzenlenmesi",
             aksiyon=[("✎  Faaliyet Düzenle", "Faaliyet kayıtlarını düzenleme")]),
    ]),
    ("YÖNETİM & DENETİM", [
        dict(ikon="👥", ad="Kullanıcı & Personel", izin="Kullanıcı oluşturma",
             aciklama="Kullanıcı, personel ve rol atama işlemleri",
             aksiyon=[("＋  Kullanıcı Oluştur", "Kullanıcı oluşturma"),
                      ("🧑‍💼  Personel Tanımla", "Personel tanımlama"),
                      ("⏸  Kullanıcı Pasifleştir", "Kullanıcı pasifleştirme"),
                      ("🔁  Rol Ata / Değiştir", "Rol atama/değiştirme")]),
        dict(ikon="🧾", ad="Audit Kayıtları", izin="Audit kayıtlarını inceleme",
             aciklama="Sistem denetim izleri", aksiyon=[]),
        dict(ikon="🏢", ad="Oda Yönetimi", izin="Oda yönetimi",
             aciklama="Sistemdeki fiziksel odaların tanımlanması ve düzenlenmesi",
             aksiyon=[("＋  Yeni Oda Ekle", "Oda yönetimi"),
                      ("✎  Odayı Düzenle", "Oda yönetimi"),
                      ("✕  Odayı Pasife Al", "Oda yönetimi")]),
    ]),
    ("SİSTEM", [
        dict(ikon="🛡️", ad="Rol & İzin Yönetimi", izin="Rol-izin yönetme",
             aciklama="Rol, izin ve faaliyet birimi yönetimi",
             aksiyon=[("＋  Rol Oluştur", "Rol oluşturma"),
                      ("✎  Rol Düzenle", "Rol düzenleme"),
                      ("＋  Yeni İzin Tanımla", "Yeni izin tanımlama"),
                      ("✎  İzin Düzenle", "İzin düzenleme"),
                      ("🏢  Faaliyet Birimleri", "Faaliyet birimlerini yönetme")]),
    ]),
]

# ======================================================================
#  3. KURUMSAL MAVİ TEMA
# ======================================================================
STIL = """
* { font-family: 'Segoe UI', 'Inter', Arial; }
QMainWindow { background: #EAF0FA; }
QLabel { background: transparent; color: #0F2552; }

/* ---------- SIDEBAR ---------- */
QWidget#sidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A1F5C, stop:1 #0B3AA8); }
QFrame#logo { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #60A5FA); border-radius: 14px; }
QLabel#bolum { color: #7FA2E8; font-size: 10px; font-weight: 800; letter-spacing: 2px; padding: 14px 6px 4px 6px; }
QPushButton#nav { background: transparent; color: #BFD2F7; border: none; border-left: 3px solid transparent; text-align: left; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600; }
QPushButton#nav:hover { background: rgba(255,255,255,0.10); color: #FFFFFF; }
QPushButton#nav:checked { background: rgba(255,255,255,0.18); color: #FFFFFF; border-left: 3px solid #93C5FD; }
QFrame#rolKart { background: rgba(255,255,255,0.10); border-radius: 12px; }
QPushButton#cikis { background: rgba(255,255,255,0.08); color: #DCE7FF; border: 1px solid rgba(255,255,255,0.20); padding: 11px; border-radius: 10px; font-weight: 700; font-size: 13px; }
QPushButton#cikis:hover { background: #DC2626; color: white; border: 1px solid #DC2626; }
QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(120,150,210,0.45); border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

/* ---------- ÜST BAR ---------- */
QFrame#topbar { background: white; border-radius: 16px; }
QLabel#sayfaBaslik { font-size: 20px; font-weight: 800; color: #0A1F5C; }
QLabel#sayfaAlt { font-size: 12px; color: #6B7FA8; }
QLabel#onizleme { font-size: 11px; font-weight: 700; color: #6B7FA8; }
QComboBox { background: #EEF4FF; color: #0A1F5C; border: 1px solid #C7D9FB; border-radius: 10px; padding: 8px 14px; font-weight: 700; min-width: 170px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: white; color: #0A1F5C; selection-background-color: #2563EB; selection-color: white; border: 1px solid #C7D9FB; outline: none; }

/* ---------- KARTLAR ---------- */
QFrame#hero { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A1F5C, stop:0.55 #1D4ED8, stop:1 #3B82F6); border-radius: 20px; }
QLabel#heroBaslik { color: white; font-size: 26px; font-weight: 800; }
QLabel#heroAlt { color: #CFE0FF; font-size: 14px; }
QLabel#heroRozet { background: rgba(255,255,255,0.20); color: white; border-radius: 10px; font-size: 12px; font-weight: 800; padding: 8px 16px; letter-spacing: 1px; }
QFrame#kart { background: white; border-radius: 16px; }
QLabel#kartBaslik { font-size: 12px; font-weight: 700; color: #6B7FA8; }
QLabel#kartDeger { font-size: 26px; font-weight: 800; color: #1D4ED8; }
QLabel#kartAlt { font-size: 11px; color: #8A9BC0; }
QPushButton#hizli { background: white; color: #0A1F5C; border: 1px solid transparent; border-radius: 16px; padding: 18px 20px; text-align: left; font-size: 14px; font-weight: 700; }
QPushButton#hizli:hover { background: #F3F8FF; border: 1px solid #3B82F6; color: #1D4ED8; }
QLabel#kategori { font-size: 13px; font-weight: 800; color: #0A1F5C; }
QLabel#izinAdi { font-size: 12px; color: #1E3A8A; }
QLabel#izinAdiPasif { font-size: 12px; color: #A3B1CE; }
QLabel#izinOn  { background: #DBEAFE; color: #1D4ED8; border-radius: 9px; font-size: 11px; font-weight: 800; padding: 2px 10px; }
QLabel#izinOff { background: #F1F4FA; color: #A3B1CE; border-radius: 9px; font-size: 11px; font-weight: 800; padding: 2px 10px; }

/* ---------- MODÜL SAYFASI ---------- */
QLabel#modulIkon { background: #DBEAFE; border-radius: 16px; font-size: 26px; }
QLabel#modulBaslik { font-size: 22px; font-weight: 800; color: #0A1F5C; }
QLabel#modulAlt { font-size: 13px; color: #6B7FA8; }
QLabel#rozetYetki { background: #DBEAFE; color: #1D4ED8; border-radius: 10px; font-size: 11px; font-weight: 800; padding: 7px 14px; }
QLabel#rozetOkunur { background: #FEF3C7; color: #B45309; border-radius: 10px; font-size: 11px; font-weight: 800; padding: 7px 14px; }
QPushButton#aksiyon { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6); color: white; border: none; border-radius: 10px; padding: 11px 20px; font-size: 13px; font-weight: 700; }
QPushButton#aksiyon:hover { background: #1E40AF; }
QPushButton#aksiyon:pressed { background: #172554; }
QLabel#bos { font-size: 40px; }
QLabel#bosBaslik { font-size: 16px; font-weight: 800; color: #0A1F5C; }
QLabel#bosAlt { font-size: 12px; color: #8A9BC0; }
QStatusBar { background: #0A1F5C; color: #BFD2F7; font-size: 12px; padding: 4px; }
"""

def golge(widget, blur=32, alpha=38, dy=8):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QColor(10, 31, 92, alpha))
    widget.setGraphicsEffect(eff)

def kart_olustur():
    k = QFrame()
    k.setObjectName("kart")
    golge(k, 26, 28, 5)
    return k

# ======================================================================
#  4. ANA PENCERE
# ======================================================================
class AnaPencere(QMainWindow):
    oturum_kapatildi = Signal()

    def __init__(self, aktif_rol="admin", kullanici_adi="", rol_onizleme=False, token="", kullanici_id=1):
        super().__init__()
        self.aktif_rol = aktif_rol.lower() if aktif_rol.lower() in ROLLER else "admin"
        self.kullanici_adi = kullanici_adi
        self.rol_onizleme = rol_onizleme

        self.api_url = "http://127.0.0.1:8000"
        self.token = token
        self.kullanici_id = kullanici_id

        self.resize(1360, 820)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STIL)

        # 1. MASTER STACK (Ana Katman Geçişi İçin)
        self.master_stack = QStackedWidget()
        self.setCentralWidget(self.master_stack)

        # INDEX 0: Normal Dashboard (Sol Menü + Sağ İçerik)
        ana_widget = QWidget()
        self.master_stack.addWidget(ana_widget)

        # INDEX 1: Tam Ekran Takvim (Üstünde Geri Ok Butonu ile)
        self.tam_ekran_takvim = QWidget()
        self.tam_ekran_takvim.setStyleSheet("background-color: white;")
        te_layout = QVBoxLayout(self.tam_ekran_takvim)
        te_layout.setContentsMargins(0, 0, 0, 0)
        te_layout.setSpacing(0)

        # Koyu Mavi Üst Bar ve Geri Butonu
        ust_bar = QFrame()
        ust_bar.setStyleSheet("background-color: #0A1F5C; padding: 12px;")
        ust_layout = QHBoxLayout(ust_bar)
        self.btn_geri = QPushButton("⬅ Ana Ekrana Dön")
        self.btn_geri.setStyleSheet("color: white; font-weight: bold; font-size: 16px; border: none; background: transparent;")
        self.btn_geri.setCursor(Qt.PointingHandCursor)
        self.btn_geri.clicked.connect(self.ana_ekrana_don) # 0'a, yani ana menüye dön

        ust_layout.addWidget(self.btn_geri)
        ust_layout.addStretch()
        te_layout.addWidget(ust_bar)

        # Takvim bileşenimizi buraya tam ekran olarak yerleştiriyoruz
        self.takvim_widget = HaftalikTakvimEkrani(api_url=self.api_url, token=self.token)
        te_layout.addWidget(self.takvim_widget)

        self.master_stack.addWidget(self.tam_ekran_takvim) # INDEX 1 olarak eklendi

        # Ana layout (Sol menü ve sağ panel) Index 0'ın içine kurulmaya devam ediyor
        ana = QHBoxLayout(ana_widget)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(0)

        # ---------------- SOL MENÜ ----------------
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(18, 24, 18, 18)
        sb.setSpacing(6)

        logo = QFrame()
        logo.setObjectName("logo")
        ll = QVBoxLayout(logo)
        ll.setContentsMargins(18, 14, 18, 14)
        ll.setSpacing(0)
        t1 = QLabel("TKYS")
        t1.setStyleSheet("color:white; font-size:24px; font-weight:900; letter-spacing:3px;")
        t2 = QLabel("Travma Kaynak Yönetim Sistemi · v1.0")
        t2.setStyleSheet("color:#DCE9FF; font-size:11px; font-weight:600;")
        ll.addWidget(t1)
        ll.addWidget(t2)
        golge(logo, 28, 90, 6)
        sb.addWidget(logo)

        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_icerik = QWidget()
        self.nav_layout = QVBoxLayout(nav_icerik)
        self.nav_layout.setContentsMargins(0, 0, 4, 0)
        self.nav_layout.setSpacing(3)
        self.nav_scroll.setWidget(nav_icerik)
        sb.addWidget(self.nav_scroll, 1)

        rol_kart = QFrame()
        rol_kart.setObjectName("rolKart")
        rk = QVBoxLayout(rol_kart)
        rk.setContentsMargins(14, 12, 14, 12)
        rk.setSpacing(2)
        self.lbl_rol_ust = QLabel("AKTİF OTURUM")
        self.lbl_rol_ust.setStyleSheet("color:#8FB1F0; font-size:10px; font-weight:800; letter-spacing:2px;")
        self.lbl_rol_ad = QLabel()
        self.lbl_rol_ad.setStyleSheet("color:white; font-size:15px; font-weight:800;")
        rk.addWidget(self.lbl_rol_ust)
        rk.addWidget(self.lbl_rol_ad)
        self.lbl_kullanici = QLabel()
        self.lbl_kullanici.setStyleSheet("color:#8FB1F0; font-size:12px; font-weight:600;")
        rk.addWidget(self.lbl_kullanici)
        sb.addWidget(rol_kart)

        btn_cikis = QPushButton("⏻   Oturumu Kapat")
        btn_cikis.setObjectName("cikis")
        btn_cikis.setCursor(Qt.PointingHandCursor)
        btn_cikis.clicked.connect(self.oturum_kapat)
        sb.addWidget(btn_cikis)
        ana.addWidget(sidebar)

        # ---------------- SAĞ ALAN ----------------
        sag = QWidget()
        sag_l = QVBoxLayout(sag)
        sag_l.setContentsMargins(28, 24, 28, 18)
        sag_l.setSpacing(20)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        golge(topbar, 26, 26, 5)
        tb = QHBoxLayout(topbar)
        tb.setContentsMargins(24, 14, 20, 14)

        tb.addStretch()

        onizleme = QLabel("ROL ÖNİZLEME")
        onizleme.setObjectName("onizleme")
        self.combo_rol = QComboBox()
        for r in ROLLER:
            self.combo_rol.addItem(ROL_BILGI[r]["ad"], r)
        self.combo_rol.setCurrentIndex(ROLLER.index(self.aktif_rol))
        self.combo_rol.currentIndexChanged.connect(lambda i: self.rol_uygula(self.combo_rol.itemData(i)))
        tb.addWidget(onizleme)
        tb.addSpacing(8)
        tb.addWidget(self.combo_rol)

        # Sadece admin rol önizlemesi yaparken görünür, yoksa tamamen kaybolur
        topbar.setVisible(self.rol_onizleme)
        sag_l.addWidget(topbar)

        self.stack = QStackedWidget()
        sag_l.addWidget(self.stack, 1)
        ana.addWidget(sag, 1)

        self.nav_grup = QButtonGroup(self)
        self.nav_grup.setExclusive(True)
        self.sayfa_bilgi = []

        self.rol_uygula(self.aktif_rol)

    # ------------------------------------------------------------------
    def rol_uygula(self, rol):
        self.aktif_rol = rol
        info = ROL_BILGI[rol]
        self.setWindowTitle(f"BKYS — Travma Yönetim Sistemi  [{info['ad'].upper()} OTURUMU]")
        if self.kullanici_adi:
            self.lbl_rol_ad.setText(self.kullanici_adi)
            self.lbl_kullanici.setText(info["ad"])
            self.lbl_kullanici.setVisible(True)
        else:
            self.lbl_rol_ad.setText(info["ad"])
            self.lbl_kullanici.setVisible(False)

        while self.nav_layout.count():
            it = self.nav_layout.takeAt(0)
            w = it.widget()
            if w:
                if isinstance(w, QPushButton):
                    self.nav_grup.removeButton(w)
                w.setParent(None)
                w.deleteLater()
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()

        self.sayfa_bilgi = []
        self.nav_btnler = {}

        ilk_btn = None
        for bolum, ogeler in MENU:
            gorunen = [o for o in ogeler if o["izin"] is None or izin_var(rol, o["izin"])]
            if not gorunen: continue

            lbl = QLabel(bolum)
            lbl.setObjectName("bolum")
            self.nav_layout.addWidget(lbl)

            for oge in gorunen:
                sayfa = self.sayfa_dashboard() if oge.get("dashboard") else self.sayfa_modul(oge)
                idx = self.stack.addWidget(sayfa)
                self.sayfa_bilgi.append((oge["ad"], oge.get("aciklama", info["aciklama"])))

                btn = QPushButton(f"{oge['ikon']}   {oge['ad']}")
                btn.setObjectName("nav")
                btn.setCheckable(True)
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda _=False, i=idx: self.sayfa_ac(i))
                self.nav_grup.addButton(btn)
                self.nav_btnler[oge['ad']] = btn
                self.nav_layout.addWidget(btn)
                if ilk_btn is None:
                    ilk_btn = btn
        self.nav_layout.addStretch()

        if ilk_btn:
            ilk_btn.setChecked(True)
            self.sayfa_ac(0)

        aktif = sum(1 for a in IZIN if izin_var(rol, a))
        self.statusBar().showMessage(
            f"Sistem Çevrim İçi  |  Güvenlik Denetimi: Başarılı  |  Aktif Oturum: {info['ad']}  |  Yetki: {aktif}/{len(IZIN)}")

    def oturum_kapat(self):
        self.oturum_kapatildi.emit()
        self.close()

    def yeni_oda_formunu_ac(self):
        self.oda_ekle_penceresi = OdaFormu(api_url=self.api_url, token=self.token)

        orijinal_close = self.oda_ekle_penceresi.closeEvent
        def kapanma_yakala(event):
            self.odalari_getir()
            if orijinal_close:
                orijinal_close(event)
            else:
                event.accept()

        self.oda_ekle_penceresi.closeEvent = kapanma_yakala
        self.oda_ekle_penceresi.show()

    def odayi_duzenle(self):
        if not hasattr(self, 'oda_tablosu'): return

        from PySide6.QtWidgets import QMessageBox
        secili_satirlar = self.oda_tablosu.selectionModel().selectedRows()

        if not secili_satirlar:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen düzenlemek istediğiniz odayı tablodan seçin.")
            return

        satir = secili_satirlar[0].row()

        oda_id = int(self.oda_tablosu.item(satir, 0).text())
        oda_adi = self.oda_tablosu.item(satir, 1).text()
        kapasite = int(self.oda_tablosu.item(satir, 2).text())
        aktif_mi = "Aktif" in self.oda_tablosu.item(satir, 3).text()

        eski_veriler = {
            "oda_adi": oda_adi,
            "kapasite": kapasite,
            "aktif_mi": aktif_mi
        }

        from oda_yonetimi import OdaFormu
        self.oda_duzenle_penceresi = OdaFormu(
            api_url=self.api_url, token=self.token, oda_id=oda_id, eski_veriler=eski_veriler
        )

        orijinal_close = self.oda_duzenle_penceresi.closeEvent
        def kapanma_yakala(event):
            self.odalari_getir()
            if orijinal_close:
                orijinal_close(event)
            else:
                event.accept()

        self.oda_duzenle_penceresi.closeEvent = kapanma_yakala
        self.oda_duzenle_penceresi.show()

    def odayi_pasife_al(self):
        if not hasattr(self, 'oda_tablosu'): return

        from PySide6.QtWidgets import QMessageBox
        import requests

        secili_satirlar = self.oda_tablosu.selectionModel().selectedRows()
        if not secili_satirlar:
            QMessageBox.warning(self, "Seçim Yapılmadı", "Lütfen pasife almak istediğiniz odayı tablodan seçin.")
            return

        satir = secili_satirlar[0].row()
        oda_id = int(self.oda_tablosu.item(satir, 0).text())
        oda_adi = self.oda_tablosu.item(satir, 1).text()

        cevap = QMessageBox.question(
            self, "Onay",
            f"'{oda_adi}' adlı odayı pasife almak istediğinize emin misiniz?\nBu işlem randevu sistemini etkileyebilir.",
            QMessageBox.Yes | QMessageBox.No
        )

        if cevap == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            try:
                res = requests.patch(
                    f"{self.api_url}/api/odalar/{oda_id}",
                    json={"aktif_mi": False},
                    headers=headers,
                    timeout=5
                )

                if res.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Oda başarıyla pasife alındı.")
                    self.odalari_getir()
                else:
                    QMessageBox.warning(self, "Hata", f"İşlem başarısız (Kod: {res.status_code})")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")

    def sayfa_ac(self, idx):
        ad, alt = self.sayfa_bilgi[idx]

        if ad == "Oda Kullanımı":
            self.master_stack.setCurrentIndex(1)
            self.stack.setCurrentIndex(idx)
        else:
            self.master_stack.setCurrentIndex(0)
            self.stack.setCurrentIndex(idx)

    def ana_ekrana_don(self):
        self.master_stack.setCurrentIndex(0)
        if "Ana Kontrol Paneli" in self.nav_btnler:
            self.nav_btnler["Ana Kontrol Paneli"].setChecked(True)
            for i, (ad, _) in enumerate(self.sayfa_bilgi):
                if ad == "Ana Kontrol Paneli":
                    self.sayfa_ac(i)
                    break

    def odalari_getir(self):
        if not hasattr(self, 'oda_tablosu'):
            return

        import requests
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = requests.get(f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if cevap.status_code == 200:
                odalar = cevap.json()
                self.oda_tablosu.setRowCount(len(odalar))

                for satir, oda in enumerate(odalar):
                    item_id = QTableWidgetItem(str(oda["oda_id"]))
                    item_ad = QTableWidgetItem(oda["oda_adi"])
                    item_kapasite = QTableWidgetItem(str(oda["kapasite"]))

                    durum = "🟢 Aktif" if oda["aktif_mi"] else "🔴 Pasif"
                    item_durum = QTableWidgetItem(durum)

                    item_id.setTextAlignment(Qt.AlignCenter)
                    item_ad.setTextAlignment(Qt.AlignCenter)
                    item_kapasite.setTextAlignment(Qt.AlignCenter)
                    item_durum.setTextAlignment(Qt.AlignCenter)

                    self.oda_tablosu.setItem(satir, 0, item_id)
                    self.oda_tablosu.setItem(satir, 1, item_ad)
                    self.oda_tablosu.setItem(satir, 2, item_kapasite)
                    self.oda_tablosu.setItem(satir, 3, item_durum)
        except Exception as e:
            print("Oda verileri çekilirken hata oluştu:", e)

    def kaydirmali(self, icerik):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setWidget(icerik)
        return sc

    def sayfa_dashboard(self):
        rol = self.aktif_rol
        info = ROL_BILGI[rol]
        govde = QWidget()
        lay = QVBoxLayout(govde)
        lay.setContentsMargins(4, 4, 4, 20)
        lay.setSpacing(20)

        hero = QFrame()
        hero.setObjectName("hero")
        golge(hero, 36, 70, 10)
        h = QHBoxLayout(hero)
        h.setContentsMargins(34, 30, 34, 30)
        sol = QVBoxLayout()
        sol.setSpacing(4)

        b = QLabel(f"Hoş Geldiniz, {self.kullanici_adi or info['ad']}")
        b.setObjectName("heroBaslik")
        a = QLabel(info["aciklama"])
        a.setObjectName("heroAlt")

        sol.addWidget(b)
        sol.addWidget(a)

        rozet = QLabel(f"●  AKTİF ROL: {info['ad'].upper()}")
        rozet.setObjectName("heroRozet")

        h.addLayout(sol)
        h.addStretch()
        h.addWidget(rozet, 0, Qt.AlignVCenter)
        lay.addWidget(hero)

        erisilebilir = [o for _, og in MENU for o in og
                        if o["izin"] is not None and izin_var(rol, o["izin"])]

        grid = QGridLayout()
        grid.setSpacing(18)
        kartlar = [
            ("Aktif Rol", info["ad"], "Oturum sahibi"),
            ("Erişilebilir Modül", str(len(erisilebilir)), "Menüde görünen modüller"),
            ("Güvenlik Durumu", "Korumalı", "Güvenlik denetimi başarılı"),
            ("Veritabanı", "Bağlı", "Senkronizasyon aktif"),
        ]
        for i, (bs, dg, al) in enumerate(kartlar):
            k = kart_olustur()
            kl = QVBoxLayout(k)
            kl.setContentsMargins(22, 18, 22, 18)
            kl.setSpacing(2)

            l1 = QLabel(bs.upper())
            l1.setObjectName("kartBaslik")
            l2 = QLabel(dg)
            l2.setObjectName("kartDeger")
            l3 = QLabel(al)
            l3.setObjectName("kartAlt")

            kl.addWidget(l1)
            kl.addWidget(l2)
            kl.addWidget(l3)
            grid.addWidget(k, 0, i)
        lay.addLayout(grid)

        baslik = QLabel("Hızlı Erişim")
        baslik.setStyleSheet("font-size:17px; font-weight:800; color:#0A1F5C;")
        lay.addWidget(baslik)

        hg = QGridLayout()
        hg.setSpacing(18)
        for n, oge in enumerate(erisilebilir):
            btn = QPushButton(f"{oge['ikon']}   {oge['ad']}")
            btn.setObjectName("hizli")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(78)
            golge(btn, 22, 24, 4)
            btn.clicked.connect(lambda _=False, ad=oge["ad"]: self.nav_btnler[ad].click())
            hg.addWidget(btn, n // 4, n % 4)
        lay.addLayout(hg)
        lay.addStretch()
        return self.kaydirmali(govde)

    # ---------------- EKRANLAR: BUTONLARIN DİNAMİK EKLENDİĞİ YER ----------------
    def sayfa_modul(self, oge):
        rol = self.aktif_rol
        govde = QWidget()
        lay = QVBoxLayout(govde)
        lay.setContentsMargins(4, 4, 4, 20)
        lay.setSpacing(20)

        # 1. Modül Başlığı ve İkonu
        bk = kart_olustur()
        bl = QHBoxLayout(bk)
        bl.setContentsMargins(15, 10, 15, 10)
        bl.setSpacing(15)

        ikon = QLabel(oge["ikon"])
        ikon.setObjectName("modulIkon")
        ikon.setFixedSize(64, 64)
        ikon.setAlignment(Qt.AlignCenter)

        mt = QVBoxLayout()
        mt.setSpacing(2)
        m1 = QLabel(oge["ad"])
        m1.setObjectName("modulBaslik")
        m2 = QLabel(oge["aciklama"])
        m2.setObjectName("modulAlt")
        mt.addWidget(m1)
        mt.addWidget(m2)

        yetkili = [a for a in oge["aksiyon"] if izin_var(rol, a[1])]
        if yetkili:
            rozet = QLabel(f"●  {len(yetkili)} İŞLEM YETKİSİ")
            rozet.setObjectName("rozetYetki")
        else:
            rozet = QLabel("●  SALT OKUNUR")
            rozet.setObjectName("rozetOkunur")

        bl.addWidget(ikon)
        bl.addLayout(mt)
        bl.addStretch()
        bl.addWidget(rozet, 0, Qt.AlignVCenter)
        lay.addWidget(bk)

        # 2. Yetki Butonlarının Eklenmesi ve Routing Bağlantıları
        if yetkili:
            ab = QHBoxLayout()
            ab.setSpacing(12)
            for etiket, izin_kodu in yetkili:
                btn = QPushButton(etiket)
                btn.setObjectName("aksiyon")
                btn.setCursor(Qt.PointingHandCursor)

                # İzin koduna veya etikete bakarak ilgili fonksiyonları bağla
                if izin_kodu == "Randevu oluşturma":
                    btn.clicked.connect(self.yeni_randevu_ekrani_ac)
                elif izin_kodu == "Arıza kayıtlarını yönetme":
                    btn.clicked.connect(self.yeni_ariza_bildirimi_ac)
                elif izin_kodu == "Randevu düzenleme":
                    btn.clicked.connect(lambda: self.randevu_ana_ekrani.duzenle_secilen() if hasattr(self, 'randevu_ana_ekrani') else None)
                elif izin_kodu == "Randevu iptal etme":
                    btn.clicked.connect(lambda: self.randevu_ana_ekrani.iptal_et_secilen() if hasattr(self, 'randevu_ana_ekrani') else None)
                elif izin_kodu == "Cihaz ekleme":
                    btn.clicked.connect(self.cihaz_ekle_tetikle)
                elif izin_kodu == "Cihaz envanterini yönetme":
                    btn.clicked.connect(self.cihaz_envanter_duzenle_tetikle)
                elif izin_kodu == "Cihaz rezervasyonu yapma":
                    btn.clicked.connect(self.yeni_rezervasyon_ekrani_ac)
                elif izin_kodu == "Cihaz takip kontrol listesini yönetme":
                    btn.clicked.connect(self.takip_listesi_tetikle)
                elif etiket == "＋  Yeni Oda Ekle":
                    btn.clicked.connect(self.yeni_oda_formunu_ac)
                elif etiket == "✎  Odayı Düzenle":
                    btn.clicked.connect(self.odayi_duzenle)
                elif etiket == "✕  Odayı Pasife Al":
                    btn.clicked.connect(self.odayi_pasife_al)
                elif etiket == "＋  Kalibrasyon Kaydı":
                    btn.clicked.connect(lambda: self.aktif_kalibrasyon_ekrani.yeni_ekle() if hasattr(self, 'aktif_kalibrasyon_ekrani') else None)

                # --- YENİ EKLENEN BAKIM BUTONU ---
                elif etiket == "＋  Bakım Kaydı":
                    btn.clicked.connect(self.yeni_bakim_ekrani_ac)


                ab.addWidget(btn)
            ab.addStretch()
            lay.addLayout(ab)

        # 3. SAYFA İÇERİĞİNİN (TABLOLARIN vs.) YÜKLENDİĞİ YER
        if oge["ad"] == "Cihaz Envanteri":
            cihaz_yetkisi = izin_var(rol, "Cihaz ekleme") or izin_var(rol, "Cihaz envanterini yönetme")
            self.aktif_cihaz_ekrani = CihazYonetimEkrani(
                api_url=self.api_url,
                token=self.token,
                yetkili_mi=cihaz_yetkisi
            )
            lay.addWidget(self.aktif_cihaz_ekrani, 1)

        elif oge["ad"] == "Kalibrasyon":
         self.aktif_kalibrasyon_ekrani = KalibrasyonYonetimEkrani(
             api_url=self.api_url,
             token=self.token
         )
         lay.addWidget(self.aktif_kalibrasyon_ekrani, 1)

        elif oge["ad"] == "Cihaz Rezervasyonu":
            rezervasyon_yetkisi = izin_var(rol, "Cihaz rezervasyonu yapma") or izin_var(rol, "REZERVASYON_IPTAL")
            self.aktif_rezervasyon_ekrani = RezervasyonYonetimEkrani(
                api_url=self.api_url,
                token=self.token,
                yetkili_mi=rezervasyon_yetkisi
            )
            lay.addWidget(self.aktif_rezervasyon_ekrani, 1)

        elif oge["ad"] == "Arıza Kayıtları":
            ariza_yetkisi = izin_var(rol, "Arıza kayıtlarını yönetme")
            self.aktif_ariza_ekrani = ArizaYonetimEkrani(
                api_url=self.api_url,
                token=self.token,
                yetkili_mi=ariza_yetkisi
            )
            lay.addWidget(self.aktif_ariza_ekrani, 1)

        # =========================================================
        # CİHAZ BAKIM KAYITLARI (MNT-002) YÖNLENDİRMESİ
        # =========================================================
        elif oge["ad"] == "Bakım Kayıtları":
            self.aktif_bakim_ekrani = BakimYonetimEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.aktif_bakim_ekrani, 1)

        elif oge["ad"] == "Oda Yönetimi":
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)

            self.oda_tablosu = QTableWidget()
            self.oda_tablosu.setColumnCount(4)
            self.oda_tablosu.setHorizontalHeaderLabels(["Oda ID", "Oda Adı", "Kapasite", "Durum"])
            self.oda_tablosu.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.oda_tablosu.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.oda_tablosu.setSelectionBehavior(QAbstractItemView.SelectRows)

            self.oda_tablosu.setStyleSheet("""
                QTableWidget {
                    background-color: white;
                    border: 1px solid #D0D7E5;
                    border-radius: 8px;
                    gridline-color: #E2E8F0;
                }
                QHeaderView::section {
                    background-color: #0A1F5C;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border: none;
                }
            """)
            il.addWidget(self.oda_tablosu)
            self.odalari_getir()
            lay.addWidget(ik, 1)

        elif oge["ad"] == "Randevu Takvimi":
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)

            from randevu_ekranlari import RandevuAnaEkrani
            self.randevu_ana_ekrani = RandevuAnaEkrani(api_url=self.api_url, token=self.token,mevcut_psikolog_id=self.kullanici_id)
            il.addWidget(self.randevu_ana_ekrani)

            lay.addWidget(ik, 1)
        else:
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)
            il.setAlignment(Qt.AlignCenter)
            il.setSpacing(6)

            e1 = QLabel(oge["ikon"])
            e1.setObjectName("bos")
            e1.setAlignment(Qt.AlignCenter)
            e2 = QLabel(f"{oge['ad']} verileri burada listelenecek")
            e2.setObjectName("bosBaslik")
            e2.setAlignment(Qt.AlignCenter)
            e3 = QLabel("Bu alan veritabanı katmanına bağlandığında kayıtlar tablo olarak görünecek.")
            e3.setObjectName("bosAlt")
            e3.setAlignment(Qt.AlignCenter)

            il.addWidget(e1)
            il.addWidget(e2)
            il.addWidget(e3)
            lay.addWidget(ik, 1)

        return govde

    def yeni_randevu_ekrani_ac(self):
        self.randevu_formu = RandevuOlusturFormu(
            api_url=self.api_url, token=self.token, mevcut_psikolog_id=self.kullanici_id
        )
        orijinal_close = self.randevu_formu.closeEvent
        def kapanma_yakala(event):
            if hasattr(self, 'randevu_ana_ekrani'):
                self.randevu_ana_ekrani.verileri_cek()
            if orijinal_close: orijinal_close(event)
            else: event.accept()
        self.randevu_formu.closeEvent = kapanma_yakala
        self.randevu_formu.show()

    def randevu_listesi_ekrani_ac(self):
        self.liste_formu = RandevuListesiFormu(
            api_url=self.api_url, token=self.token, mevcut_psikolog_id=self.kullanici_id
        )
        self.liste_formu.finished.connect(lambda: self.randevu_ana_ekrani.verileri_cek() if hasattr(self, 'randevu_ana_ekrani') else None)
        self.liste_formu.show()

    def cihaz_ekle_tetikle(self):
        if hasattr(self, 'aktif_cihaz_ekrani'):
            self.aktif_cihaz_ekrani.yeni_cihaz_ekle()

    def cihaz_envanter_duzenle_tetikle(self):
        if hasattr(self, 'aktif_cihaz_ekrani'):
            self.aktif_cihaz_ekrani.envanter_duzenle_liste_ac()

    def takip_listesi_tetikle(self):
        QMessageBox.information(self, "Bilgi", "Takip Kontrol Listesi modülü yapım aşamasındadır.")

    def yeni_rezervasyon_ekrani_ac(self):
        if hasattr(self, 'aktif_rezervasyon_ekrani'):
            self.aktif_rezervasyon_ekrani.yeni_rezervasyon_olustur()

    def yeni_ariza_bildirimi_ac(self):
        if hasattr(self, 'aktif_ariza_ekrani'):
            self.aktif_ariza_ekrani.yeni_ariza_bildirimi()

    def yeni_bakim_ekrani_ac(self):
        """Ana yetki kartındaki 'Bakım Kaydı' butonuna basılınca formu açar."""
        if hasattr(self, 'aktif_bakim_ekrani'):
            self.aktif_bakim_ekrani.yeni_bakim_ekle()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    rol = sys.argv[1] if len(sys.argv) > 1 else "admin"
    pencere = AnaPencere(aktif_rol=rol, rol_onizleme=True)
    pencere.show()
    sys.exit(app.exec())
