import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGridLayout, QStackedWidget, QScrollArea, QComboBox,
    QButtonGroup, QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

# ======================================================================
#  1. YETKİ MATRİSİ  (E = Evet, H = Hayır)
#  Sütun sırası: Psikolog, Memur, Müdür, Danışma Öğrencisi, Proje Asistanı, Admin
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

# (izin adı, kategori, "Psi Mem Müd Öğr Asi Adm")
IZIN_LISTESI = [
    ("Randevu oluşturma",                    "Randevu & Oda",     "EHHEHE"),
    ("Randevu düzenleme",                    "Randevu & Oda",     "EHHEHE"),
    ("Randevu iptal etme",                   "Randevu & Oda",     "EHHEHE"),
    ("Randevu takvimini görüntüleme",        "Randevu & Oda",     "EEEEEE"),
    ("Oda kullanım durumunu görüntüleme",    "Randevu & Oda",     "EEEEEE"),

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
#  2. MENÜ TANIMI  (görünürlük izni + sayfa içi işlem butonları)
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
QWidget#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0A1F5C, stop:1 #0B3AA8);
}
QFrame#logo {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #60A5FA);
    border-radius: 14px;
}
QLabel#bolum { color: #7FA2E8; font-size: 10px; font-weight: 800; letter-spacing: 2px; padding: 14px 6px 4px 6px; }
QPushButton#nav {
    background: transparent; color: #BFD2F7; border: none; border-left: 3px solid transparent;
    text-align: left; padding: 10px 14px; border-radius: 10px; font-size: 13px; font-weight: 600;
}
QPushButton#nav:hover { background: rgba(255,255,255,0.10); color: #FFFFFF; }
QPushButton#nav:checked {
    background: rgba(255,255,255,0.18); color: #FFFFFF; border-left: 3px solid #93C5FD;
}
QFrame#rolKart { background: rgba(255,255,255,0.10); border-radius: 12px; }
QPushButton#cikis {
    background: rgba(255,255,255,0.08); color: #DCE7FF; border: 1px solid rgba(255,255,255,0.20);
    padding: 11px; border-radius: 10px; font-weight: 700; font-size: 13px;
}
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
QComboBox {
    background: #EEF4FF; color: #0A1F5C; border: 1px solid #C7D9FB; border-radius: 10px;
    padding: 8px 14px; font-weight: 700; min-width: 170px;
}
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView {
    background: white; color: #0A1F5C; selection-background-color: #2563EB;
    selection-color: white; border: 1px solid #C7D9FB; outline: none;
}

/* ---------- KARTLAR ---------- */
QFrame#hero {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0A1F5C, stop:0.55 #1D4ED8, stop:1 #3B82F6);
    border-radius: 20px;
}
QLabel#heroBaslik { color: white; font-size: 26px; font-weight: 800; }
QLabel#heroAlt { color: #CFE0FF; font-size: 14px; }
QLabel#heroRozet {
    background: rgba(255,255,255,0.20); color: white; border-radius: 10px;
    font-size: 12px; font-weight: 800; padding: 8px 16px; letter-spacing: 1px;
}
QFrame#kart { background: white; border-radius: 16px; }
QLabel#kartBaslik { font-size: 12px; font-weight: 700; color: #6B7FA8; }
QLabel#kartDeger { font-size: 26px; font-weight: 800; color: #1D4ED8; }
QLabel#kartAlt { font-size: 11px; color: #8A9BC0; }
QPushButton#hizli {
    background: white; color: #0A1F5C; border: 1px solid transparent; border-radius: 16px;
    padding: 18px 20px; text-align: left; font-size: 14px; font-weight: 700;
}
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
QPushButton#aksiyon {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6);
    color: white; border: none; border-radius: 10px; padding: 11px 20px; font-size: 13px; font-weight: 700;
}
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
    oturum_kapatildi = Signal()   # "Oturumu Kapat" butonuna basılınca giriş ekranına haber verir

    def __init__(self, aktif_rol="admin", kullanici_adi="", rol_onizleme=False):
        super().__init__()
        self.aktif_rol = aktif_rol.lower() if aktif_rol.lower() in ROLLER else "admin"
        self.kullanici_adi = kullanici_adi          # ekranda görünecek ad soyad
        self.rol_onizleme = rol_onizleme            # sadece geliştirme/test için True
        self.resize(1360, 820)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STIL)

        ana_widget = QWidget()
        self.setCentralWidget(ana_widget)
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
        t1 = QLabel("BKYS")
        t1.setStyleSheet("color:white; font-size:24px; font-weight:900; letter-spacing:3px;")
        t2 = QLabel("Travma Yönetim Sistemi · v1.0")
        t2.setStyleSheet("color:#DCE9FF; font-size:11px; font-weight:600;")
        ll.addWidget(t1)
        ll.addWidget(t2)
        golge(logo, 28, 90, 6)
        sb.addWidget(logo)

        # Kaydırılabilir menü alanı
        self.nav_scroll = QScrollArea()
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav_icerik = QWidget()
        self.nav_layout = QVBoxLayout(nav_icerik)
        self.nav_layout.setContentsMargins(0, 0, 4, 0)
        self.nav_layout.setSpacing(3)
        self.nav_scroll.setWidget(nav_icerik)
        sb.addWidget(self.nav_scroll, 1)

        # Rol kartı
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
        bas = QVBoxLayout()
        bas.setSpacing(0)
        self.lbl_sayfa = QLabel()
        self.lbl_sayfa.setObjectName("sayfaBaslik")
        self.lbl_sayfa_alt = QLabel()
        self.lbl_sayfa_alt.setObjectName("sayfaAlt")
        bas.addWidget(self.lbl_sayfa)
        bas.addWidget(self.lbl_sayfa_alt)
        tb.addLayout(bas)
        tb.addStretch()
        onizleme = QLabel("ROL ÖNİZLEME")
        onizleme.setObjectName("onizleme")
        self.combo_rol = QComboBox()
        for r in ROLLER:
            self.combo_rol.addItem(ROL_BILGI[r]["ad"], r)
        self.combo_rol.setCurrentIndex(ROLLER.index(self.aktif_rol))
        self.combo_rol.currentIndexChanged.connect(
            lambda i: self.rol_uygula(self.combo_rol.itemData(i)))
        tb.addWidget(onizleme)
        tb.addSpacing(8)
        tb.addWidget(self.combo_rol)
        # Gerçek girişte rol değiştirme kapalı (güvenlik)
        onizleme.setVisible(self.rol_onizleme)
        self.combo_rol.setVisible(self.rol_onizleme)
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
        """Seçilen role göre menüyü, sayfaları ve butonları yeniden kurar."""
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

        # eski içerikleri temizle
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
            if not gorunen:
                continue
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

    def sayfa_ac(self, idx):
        self.stack.setCurrentIndex(idx)
        ad, alt = self.sayfa_bilgi[idx]
        self.lbl_sayfa.setText(ad)
        self.lbl_sayfa_alt.setText(alt)

    # ------------------------------------------------------------------
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

        # HERO
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

        # İSTATİSTİK KARTLARI
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
            l1 = QLabel(bs.upper()); l1.setObjectName("kartBaslik")
            l2 = QLabel(dg); l2.setObjectName("kartDeger")
            l3 = QLabel(al); l3.setObjectName("kartAlt")
            kl.addWidget(l1); kl.addWidget(l2); kl.addWidget(l3)
            grid.addWidget(k, 0, i)
        lay.addLayout(grid)

        # HIZLI ERİŞİM (sadece rolün görebildiği modüller)
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

    def sayfa_modul(self, oge):
        rol = self.aktif_rol
        govde = QWidget()
        lay = QVBoxLayout(govde)
        lay.setContentsMargins(4, 4, 4, 20)
        lay.setSpacing(20)

        # Başlık kartı
        bk = kart_olustur()
        bl = QHBoxLayout(bk)
        bl.setContentsMargins(26, 22, 26, 22)
        bl.setSpacing(18)
        ikon = QLabel(oge["ikon"])
        ikon.setObjectName("modulIkon")
        ikon.setFixedSize(64, 64)
        ikon.setAlignment(Qt.AlignCenter)
        mt = QVBoxLayout()
        mt.setSpacing(2)
        m1 = QLabel(oge["ad"]); m1.setObjectName("modulBaslik")
        m2 = QLabel(oge["aciklama"]); m2.setObjectName("modulAlt")
        mt.addWidget(m1); mt.addWidget(m2)

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

        # İşlem butonları: yetkisi olmayan buton HİÇ GÖRÜNMEZ
        if yetkili:
            ab = QHBoxLayout()
            ab.setSpacing(12)
            for etiket, _ in yetkili:
                btn = QPushButton(etiket)
                btn.setObjectName("aksiyon")
                btn.setCursor(Qt.PointingHandCursor)
                ab.addWidget(btn)
            ab.addStretch()
            lay.addLayout(ab)

        # İçerik alanı (veri katmanı buraya bağlanacak)
        ik = kart_olustur()
        ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        il = QVBoxLayout(ik)
        il.setAlignment(Qt.AlignCenter)
        il.setSpacing(6)
        e1 = QLabel(oge["ikon"]); e1.setObjectName("bos"); e1.setAlignment(Qt.AlignCenter)
        e2 = QLabel(f"{oge['ad']} verileri burada listelenecek"); e2.setObjectName("bosBaslik")
        e2.setAlignment(Qt.AlignCenter)
        e3 = QLabel("Bu alan veritabanı katmanına bağlandığında kayıtlar tablo olarak görünecek.")
        e3.setObjectName("bosAlt"); e3.setAlignment(Qt.AlignCenter)
        il.addWidget(e1); il.addWidget(e2); il.addWidget(e3)
        lay.addWidget(ik, 1)
        return govde


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Test için: python bkys_arayuz.py psikolog
    # Roller: admin, psikolog, memur, mudur, ogrenci, asistan
    rol = sys.argv[1] if len(sys.argv) > 1 else "admin"
    pencere = AnaPencere(aktif_rol=rol, rol_onizleme=True)
    pencere.show()
    sys.exit(app.exec())