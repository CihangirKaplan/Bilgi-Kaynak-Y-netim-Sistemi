import base64
import json
import time
from PySide6.QtCore import QTimer
from api_yoneticisi import oturum_olaylari
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)

import os
import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMenu, QGridLayout, QStackedWidget, QScrollArea, QComboBox,
    QButtonGroup, QGraphicsDropShadowEffect, QSizePolicy, QTableWidget, QHeaderView, QAbstractItemView, QTableWidgetItem
)
from oda_yonetimi import OdaFormu
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QColor
from randevu_ekranlari import RandevuOlusturFormu
from haftalik_takvim import HaftalikTakvimEkrani
from cihaz_ekranlari import CihazYonetimEkrani
from cihaz_rezervasyon_ekranlari import RezervasyonYonetimEkrani
from cihaz_ariza_ekranlari import ArizaYonetimEkrani
from cihaz_uygunluk_ekrani import CihazUygunlukEkrani
from cihaz_kalibrasyon_ekranlari import KalibrasyonYonetimEkrani
from cihaz_bakim_ekranlari import BakimYonetimEkrani # YENİ EKLENDİ!
from dashboard_ekrani import DashboardEkrani
from k_personel_ekranlari import KullaniciPersonelEkrani
from faaliyet_dialog import FaaliyetEkleDialog
from sayfalar_rol_izin import RolIzinSayfasi
from rol_izin_diyaloglari import RolOlusturDialog, IzinDuzenleDialog

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


def dinamik_rol_tanimla(rol_kodu, rol_adi):
    """Sunucudan doğrulanmış, yeni bir rolü arayüze tanıtır.

    Bu işlem rolün izinlerini vermez; izinler API'den alınır.
    """
    if not rol_kodu.startswith("rol_"):
        return

    if not rol_adi or not str(rol_adi).strip():
        raise ValueError("Rol adı bulunamadı.")

    if rol_kodu not in ROLLER:
        ROLLER.append(rol_kodu)

    ROL_BILGI[rol_kodu] = {
        "ad": str(rol_adi).strip().title(),
        "aciklama": "Rolünüze tanımlanan yetkiler kapsamında işlem yapabilirsiniz.",
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
    ("Cihaz raporlarını görüntüleme",        "Cihaz Yönetimi",    "HEEHHE"),

    ("Bakım kayıtlarını yönetme",            "Kayıt & Bakım",     "HEEHHE"),
    ("Kalibrasyon kayıtlarını yönetme",      "Kayıt & Bakım",     "HEEHHE"),
    ("Arıza kayıtlarını yönetme",            "Kayıt & Bakım",     "HEEHHE"),
    ("Faaliyet kayıtlarını düzenleme",       "Kayıt & Bakım",     "HEEHEE"),

    ("Kullanıcı oluşturma",                  "Kullanıcı & Denetim","HHEHHE"),
    ("Personel tanımlama",                   "Kullanıcı & Denetim","HHEHHE"),
    ("Kullanıcı pasifleştirme",              "Kullanıcı & Denetim","HHEHHE"),
    ("Rol atama/değiştirme",                 "Kullanıcı & Denetim","HHEHHE"),
    ("Audit kayıtlarını inceleme",           "Kullanıcı & Denetim","HHEHHE"),
    ("Danışma masası oturumunu yönetme",     "Kullanıcı & Denetim","HHHEHH"),
    ("Danışma masası yönetimi",               "Kullanıcı & Denetim","HEHHHE"),
    ("Danışma masası raporlarını görüntüleme", "Kullanıcı & Denetim","HEEHHE"),
    ("İzin düzenleme",                       "Sistem Yönetimi",   "HHHHHE"),
    ("Rol-izin yönetme",                     "Sistem Yönetimi",   "HHHHHE"),
    ("Rol oluşturma",                        "Sistem Yönetimi",   "HHHHHE"),
    ("Rol düzenleme",                        "Sistem Yönetimi",   "HHHHHE"),
    ("Faaliyet birimlerini yönetme",         "Sistem Yönetimi",   "HHHHHE"),
]

IZIN = {ad: (kat, kod) for ad, kat, kod in IZIN_LISTESI}

# Parola sıfırlama: yalnızca ADMIN rolüne açık.
# Mevcut ADMIN yetkisinin rol maskesi kullanılır.
IZIN["Kullanıcı parola sıfırlama"] = (
    IZIN["Kullanıcı oluşturma"][0],
    IZIN["Faaliyet birimlerini yönetme"][1],
)

# Ekrandaki izin adı -> sunucunun gerçekte istediği izin kod(lar)ı (rol_izinleri tablosu).
# Menü, kullanıcının sunucudan aldığı izinlere (/api/yetkilerim) göre çizilir; bu tablo ekran
# adlarını sunucudaki kodlara çevirir. Birden fazla kod varsa hepsi gerekir.
# Karşılık, sunucunun uçlarda GERÇEKTE kontrol ettiği koddur (menü, tıklayınca 403 verecek
# bir düğmeyi göstermesin diye): örn. bakım ve kalibrasyon uçları CIHAZ_ENVANTER_YONET ister.
IZIN_KODLARI = {
    "Randevu oluşturma": ("RANDEVU_OLUSTUR",),
    "Randevu düzenleme": ("RANDEVU_DUZENLE",),
    "Randevu iptal etme": ("RANDEVU_IPTAL",),
    "Randevu takvimini görüntüleme": ("TAKVIM_GORUNTULE",),
    "Oda kullanım durumunu görüntüleme": ("ODA_DURUMU_GORUNTULE",),
    "Oda yönetimi": ("ODA_EKLE", "ODA_DUZENLE"),
    "Cihaz uygunluğunu görüntüleme": ("CIHAZ_UYGUNLUK_GORUNTULE",),
    "Cihaz envanterini yönetme": ("CIHAZ_ENVANTER_YONET",),
    "Cihaz rezervasyonu yapma": ("CIHAZ_REZERVASYON",),
    "Cihaz ekleme": ("CIHAZ_EKLE",),
    "Cihaz takip kontrol listesini yönetme": ("CIHAZ_TAKIP_KONTROL_LISTESI",),
    "Cihaz raporlarını görüntüleme": ("CIHAZ_ENVANTER_YONET",),
    "Bakım kayıtlarını yönetme": ("BAKIM_KAYITLARI_YONET",),
    "Kalibrasyon kayıtlarını yönetme": ("KALIBRASYON_KAYITLARI_YONET",),
    "Arıza kayıtlarını yönetme": ("ARIZA_KAYITLARI_YONET",),
    "Faaliyet kayıtlarını düzenleme": ("FAALIYET_KAYITLARI_DUZENLE",),
    "Kullanıcı oluşturma": ("KULLANICI_OLUSTUR",),
    "Personel tanımlama": ("PERSONEL_TANIMLA",),
    "Kullanıcı pasifleştirme": ("KULLANICI_PASIFLESTIR",),
    "Kullanıcı parola sıfırlama": ("KULLANICI_PAROLA_SIFIRLA",),
    "Rol atama/değiştirme": ("ROL_ATAMA_DEGISTIRME",),
    "Audit kayıtlarını inceleme": ("AUDIT_KAYITLARI_INCELE",),
    "Danışma masası oturumunu yönetme": ("DANISMA_OTURUMU_YONET",),
    "Danışma masası yönetimi": ("DANISMA_OTURUMU_YONETIM",),
    "Danışma masası raporlarını görüntüleme": ("DANISMA_OTURUMU_GORUNTULE",),
    "İzin düzenleme": ("IZIN_DUZENLE",),
    "Rol-izin yönetme": ("ROL_IZIN_YONET",),
    "Rol oluşturma": ("ROL_OLUSTUR",),
    "Rol düzenleme": ("ROL_DUZENLE",),
    # İSTİSNA: bu düğme Faaliyet Kayıtları sayfasında durur ve yalnızca Admin içindir; bu amaçla
    # tanımlı izne (FAALIYET_BIRIMI_DUZENLE, yalnızca Admin'de) eşleştirilir. Sunucudaki faaliyet
    # birimi yazma uçları şu an daha geniş olan FAALIYET_KAYITLARI_DUZENLE'yi istiyor (Memur, Müdür
    # ve Proje Asistanı da sahip); bu ayrı bir yetki tutarsızlığıdır. O koda eşleştirilseydi
    # düğme bu rollere de görünürdü.
    "Faaliyet birimlerini yönetme": ("FAALIYET_BIRIMI_DUZENLE",),
}

# Kişisel paneller: izin olsa bile yalnızca belirtilen roller için gösterilir. Danışma Masası
# öğrenci paneli kişiseldir (kullanıcının kendi öğrenci kaydına bağlı vardiya); veritabanında
# Admin bütün izinlere sahip olsa da Admin'in öğrenci kaydı olmadığından bu panel ona gösterilmez.
IZIN_SADECE_ROL = {
    "Danışma masası oturumunu yönetme": {"ogrenci"},
}

# Giriş sonrası sunucudan alınan izinler (rol -> izin kodları). Alınamazsa o rol için boş kalır
# ve yukarıdaki elle yazılmış tabloya (IZIN_LISTESI) dönülür.
_SUNUCU_YETKILERI = {}


def yetkileri_ayarla(rol, kodlar):
    """Sunucudan alınan izin kodlarını kaydeder."""
    _SUNUCU_YETKILERI[rol] = frozenset(kodlar)


def yetkileri_temizle(rol):
    """Bu rol için sunucu yetkilerini siler (elle yazılmış tabloya dönülür)."""
    _SUNUCU_YETKILERI.pop(rol, None)


def cihaz_ozeti_gorebilir_mi(rol):
    """Ana paneldeki cihaz kartları, bildirimler ve yaklaşan işlemler.

    Sunucudaki /api/dashboard/ozet, /bugunku-rezervasyonlar ve /yaklasan-islemler uçları
    CIHAZ_ENVANTER_YONET ister; istemci de aynı izne bakar, böylece ikisi hiç ayrışmaz.
    """
    return izin_var(rol, "Cihaz envanterini yönetme")


def izin_var(rol, izin_adi):
    """Rolün bu izne sahip olup olmadığı. Bilinmeyen izin adı 'yok' sayılır (çökmez)."""
    if izin_adi == "Bakım/kalibrasyon planlarını yönetme":
        return (
            izin_var(rol, "Bakım kayıtlarını yönetme")
            or izin_var(rol, "Kalibrasyon kayıtlarını yönetme")
        )
    if izin_adi not in IZIN:
        return False
    kodlar = _SUNUCU_YETKILERI.get(rol)
    if kodlar is None:
        # Dinamik rollerde sunucu izinleri zorunludur.
        # Bağlantı/izin yükleme hatasında hiçbir yetki verilmez.
        if rol.startswith("rol_"):
            return False
        # Mevcut rollerin eski davranışı korunur.
        return IZIN[izin_adi][1][ROLLER.index(rol)] == "E"
    sadece = IZIN_SADECE_ROL.get(izin_adi)
    if sadece is not None and rol not in sadece:
        return False
    return all(kod in kodlar for kod in IZIN_KODLARI[izin_adi])

# ======================================================================
#  2. MENÜ TANIMI
# ======================================================================
MENU = [
    ("GENEL", [
        dict(ikon="📊", ad="Ana Kontrol Paneli", izin=None, dashboard=True),
    ]),
    ("KLİNİK OPERASYON", [
        dict(ikon="📅", ad="Randevu Yönetimi", izin="Randevu takvimini görüntüleme",
             aciklama="Randevuları listeleme, düzenleme ve iptal etme",
             aksiyon=[("＋  Yeni Randevu", "Randevu oluşturma"),
                      ("✎  Randevu Düzenle", "Randevu düzenleme"),
                      ("✓  Tamamlandı", "Randevu düzenleme"),
                      ("✗  Gelmedi", "Randevu düzenleme"),
                      ("✕  Randevu İptal Et", "Randevu iptal etme")]),
        dict(ikon="👤", ad="Danışanlar", izin="Randevu oluşturma",
             aciklama="Psikologlara göre danışanlar, bilgileri, randevu özeti ve geçmişi",
             aksiyon=[("＋  Yeni Danışan", "Randevu oluşturma")]),
        dict(ikon="🚪", ad="Oda Kullanımı", izin="Oda kullanım durumunu görüntüleme",
             aciklama="Oda doluluk ve kullanım durumu", aksiyon=[]),
    ]),
    ("ÖĞRENCİ & FAALİYET YÖNETİMİ", [
        dict(
            ikon="👥",
            ad="Öğrenciler",
            izin="Faaliyet kayıtlarını düzenleme",
            aciklama="Öğrenci kayıtları ve aktiflik yönetimi",
            aksiyon=[]
        ),
        dict(ikon="📝", ad="Faaliyet Kayıtları", izin="Faaliyet kayıtlarını düzenleme",
             aciklama="Faaliyet kayıtlarının düzenlenmesi",
             aksiyon=[("＋  Yeni Faaliyet Ekle", "Faaliyet kayıtlarını düzenleme"),
                      ("✎  Faaliyet Düzenle", "Faaliyet kayıtlarını düzenleme"),
                      ("🏢  Faaliyet Birimleri", "Faaliyet birimlerini yönetme"),
                      ("📋  Faaliyet Türleri", "Faaliyet kayıtlarını düzenleme"),
                      ("🗑️ Faaliyet Sil", "Faaliyet kayıtlarını düzenleme")]),
        dict(
            ikon="🏆",
            ad="Puan Raporu",
            izin="Faaliyet kayıtlarını düzenleme",
            aciklama="Öğrencilerin faaliyet puanlarına göre sıralaması ve Excel raporu",
            aksiyon=[]
        ),
        dict(ikon="🛎️", ad="Danışma Masası",
             izin="Danışma masası oturumunu yönetme",
             aciklama="Görev başlatma, bitirme ve geçmiş görevler",
             aksiyon=[]),
        dict(ikon="📋", ad="Danışma Masası Yönetimi",
             izin="Danışma masası yönetimi",
             aciklama="Öğrencilerin görevlerini takip etme ve onaylama",
             aksiyon=[]),
        dict(ikon="📊", ad="Danışma Masası Raporları",
             izin="Danışma masası raporlarını görüntüleme",
             aciklama="Öğrencilerin çalışma süreleri ve görev raporları",
             aksiyon=[]),
    ]),
    ("CİHAZ YAŞAM DÖNGÜSÜ", [
        dict(ikon="🔎", ad="Cihaz Uygunluğu", izin="Cihaz uygunluğunu görüntüleme",
             aciklama="Cihazların haftalık uygunluk takvimi",
             aksiyon=[("＋  Rezervasyon Yap", "Cihaz rezervasyonu yapma"),
                      ("⚠  Arıza Bildir", "Arıza kayıtlarını yönetme")]),
        dict(ikon="⚙️", ad="Cihaz Envanteri", izin="Cihaz envanterini yönetme",
             aciklama="Envanter kayıtları ve cihaz yönetimi",
             aksiyon=[("＋  Cihaz Ekle", "Cihaz ekleme"),
                      ("✎  Envanteri Düzenle", "Cihaz envanterini yönetme")]),
        dict(ikon="📌", ad="Cihaz Rezervasyonu", izin="Cihaz rezervasyonu yapma",
             aciklama="Cihaz rezervasyon işlemleri",
             aksiyon=[("＋  Yeni Rezervasyon", "Cihaz rezervasyonu yapma")]),
        dict(ikon="🛠️", ad="Bakım Kayıtları", izin="Bakım kayıtlarını yönetme",
             aciklama="Periyodik bakım kayıtları",
             aksiyon=[("＋  Bakım Kaydı", "Bakım kayıtlarını yönetme")]),
        dict(ikon="🗓️", ad="Bakım Planları", izin="Bakım/kalibrasyon planlarını yönetme",
             aciklama="Cihazların tekrar aralığı, uyarı süresi ve sonraki bakım/kalibrasyon tarihi",
             aksiyon=[("＋  Yeni Plan", "Bakım/kalibrasyon planlarını yönetme")]),
        dict(ikon="🎯", ad="Kalibrasyon", izin="Kalibrasyon kayıtlarını yönetme",
             aciklama="Kalibrasyon planı ve sertifikaları",
             aksiyon=[("＋  Kalibrasyon Kaydı", "Kalibrasyon kayıtlarını yönetme")]),
        dict(ikon="⚠️", ad="Arıza Kayıtları", izin="Arıza kayıtlarını yönetme",
             aciklama="Arıza bildirimi ve takibi",
             aksiyon=[("＋  Arıza Kaydı", "Arıza kayıtlarını yönetme")]),
        dict(ikon="📈", ad="Cihaz Raporları", izin="Cihaz raporlarını görüntüleme",
             aciklama="Bakım, kalibrasyon ve arıza raporları", aksiyon=[]),

    ]),
    ("YÖNETİM & DENETİM", [
        dict(ikon="👥", ad="Kullanıcı & Personel", izin="Kullanıcı oluşturma",
             aciklama="Kullanıcı, personel ve rol atama işlemleri",
             aksiyon=[("＋  Kullanıcı Oluştur", "Kullanıcı oluşturma"),
                      ("⏸  Aktiflik Düzenle", "Kullanıcı pasifleştirme"),
                      ("🔁  Rol Ata / Değiştir", "Rol atama/değiştirme"),
                      ("🏠  Oda Yetkileri", "Rol atama/değiştirme"),
                      ("🔑  Parola Sıfırla", "Kullanıcı parola sıfırlama")]),
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
                      ("✎  İzin Düzenle", "İzin düzenleme")]),
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
QPushButton#aksiyon { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #3B82F6); color: white; border: none; border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 700; }
QPushButton#aksiyon:hover { background: #1E40AF; }
QPushButton#aksiyon:pressed { background: #172554; }
QToolTip { background-color: #0A1F5C; color: white; border: 1px solid #426BA5; padding: 6px 10px; font-size: 12px; }
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

# TKYS_DASHBOARD_KOMPAKT_V1
def _tkys_dashboard_kompakt(sayfa):
    """Ana kontrol panelindeki karsilama alanini sadelestirir."""
    import unicodedata
    from PySide6.QtWidgets import QLabel

    if sayfa is None or not hasattr(sayfa, "findChildren"):
        return sayfa

    def normal(metin):
        metin = unicodedata.normalize("NFKD", str(metin))
        return "".join(
            h for h in metin
            if not unicodedata.combining(h)
        ).casefold()

    etiketler = sayfa.findChildren(QLabel)

    baslik = next(
        (
            e for e in etiketler
            if "hos geldiniz" in normal(e.text())
        ),
        None
    )

    rol = next(
        (
            e for e in etiketler
            if "aktif rol" in normal(e.text())
        ),
        None
    )

    if baslik is None or rol is None:
        return sayfa

    panel = baslik.parentWidget()

    while panel is not None and panel is not sayfa:
        if panel.isAncestorOf(rol):
            break
        panel = panel.parentWidget()
    else:
        return sayfa

    for etiket in panel.findChildren(QLabel):
        if etiket is not baslik:
            etiket.hide()

    rozet = rol

    while (
        rozet.parentWidget() is not None
        and rozet.parentWidget() is not panel
    ):
        rozet = rozet.parentWidget()

    rozet.hide()

    baslik.setStyleSheet(
        baslik.styleSheet()
        + "; font-size: 22px; font-weight: 700;"
    )

    yerlesim = panel.layout()

    if yerlesim is not None:
        yerlesim.setContentsMargins(24, 8, 24, 8)
        yerlesim.setSpacing(0)

    panel.setFixedHeight(80)

    return sayfa


class AnaPencere(QMainWindow):
    oturum_kapatildi = Signal()

    def __init__(self, aktif_rol=None, kullanici_adi="", rol_onizleme=False, token="", kullanici_id=1):
        super().__init__()
        if not isinstance(aktif_rol, str) or aktif_rol.lower() not in ROLLER:
            raise ValueError("Geçersiz kullanıcı rolü.")

        self.aktif_rol = aktif_rol.lower()
        self.kullanici_adi = kullanici_adi
        self.rol_onizleme = rol_onizleme

        self.api_url = os.getenv("TKYS_API_URL", "http://127.0.0.1:8000")
        self.token = token
        self.kullanici_id = kullanici_id

        # Menü, sunucunun gerçekte uyguladığı yetkilere göre çizilir.
        self._yetkileri_sunucudan_al()

        # JWT bitiş zamanını takip et
        self._token_bitis_zamani = self._token_bitisini_oku()

        self._oturum_kapatiliyor = False

        oturum_olaylari.token_reddedildi.connect(
            self._api_token_reddedildi
        )

        self._oturum_zamanlayici = QTimer(self)
        self._oturum_zamanlayici.setInterval(1000)
        self._oturum_zamanlayici.timeout.connect(
            self._oturum_suresini_kontrol_et
        )

        if self.token:
            self._oturum_zamanlayici.start()
            QTimer.singleShot(
                0, self._oturum_suresini_kontrol_et
            )

        self._yetki_zamanlayicisini_kur()

        self.resize(1360, 820)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STIL)

        # 1. MASTER STACK (Ana Katman Geçişi İçin)
        self.master_stack = QStackedWidget()
        self.setCentralWidget(self.master_stack)

        # Tum ekranlarda gorunen ust gezinme cubugu
        from PySide6.QtWidgets import QToolBar, QSizePolicy

        self.gezinme_cubugu = QToolBar("Gezinme", self)
        self.gezinme_cubugu.setMovable(False)
        self.gezinme_cubugu.setFloatable(False)
        self.gezinme_cubugu.setStyleSheet("""
            QToolBar {
                background: white;
                border: none;
                border-bottom: 1px solid #DCE5F2;
                padding: 6px 16px;
                spacing: 10px;
            }
        """)

        self.addToolBar(Qt.TopToolBarArea, self.gezinme_cubugu)

        bosluk = QWidget()
        bosluk.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Preferred
        )
        self.btn_menu = QPushButton("☰")
        self.btn_menu.setCursor(Qt.PointingHandCursor)
        self.btn_menu.setToolTip("Sol menüyü daralt / genişlet")
        self.btn_menu.clicked.connect(self._sol_menu_degistir)
        self.gezinme_cubugu.addWidget(self.btn_menu)

        self.ust_baslik = QLabel("TKYS")
        self.gezinme_cubugu.addWidget(self.ust_baslik)
        self.ust_sayfa = QLabel("")
        self.ust_sayfa.setStyleSheet("color: #BFD3F2; font-size: 15px; font-weight: 700;")
        self.gezinme_cubugu.addWidget(self.ust_sayfa)

        self.gezinme_cubugu.addWidget(bosluk)


        self.btn_bildirim = QPushButton("")
        self.btn_bildirim.setToolTip("Tüm Bildirimler")
        self.btn_bildirim.setCursor(Qt.PointingHandCursor)
        self.btn_bildirim.setStyleSheet("""
            QPushButton {
                background: #EAF0FA;
                color: #0A1F5C;
                border: none;
                border-radius: 8px;
                padding: 9px 15px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #DCE7FA;
            }
        """)
        self.btn_bildirim.clicked.connect(self._bildirim_menusunu_ac)
        self.gezinme_cubugu.addWidget(self.btn_bildirim)

        self.btn_ana_sayfa = QPushButton("🏠  Ana Sayfa")
        self.btn_ana_sayfa.setCursor(Qt.PointingHandCursor)
        self.btn_ana_sayfa.setToolTip("Ana kontrol paneline dön")
        self.btn_ana_sayfa.setStyleSheet("""
            QPushButton {
                background: #EAF0FA;
                color: #0A1F5C;
                border: none;
                border-radius: 8px;
                padding: 9px 15px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #DCE7FA;
            }
        """)

        self.btn_ana_sayfa.clicked.connect(self.ana_ekrana_don)
        self.gezinme_cubugu.addWidget(self.btn_ana_sayfa)

        self.gezinme_cubugu.setFixedHeight(60)
        self.gezinme_cubugu.setStyleSheet("""
            QToolBar {
                background: #082B66;
                border: none;
                border-bottom: 2px solid #426BA5;
                padding: 6px 16px;
                spacing: 10px;
            }
        """)

        # TKYS_UST_CERCEVESIZ_V1
        # TKYS_UST_ZEMINSIZ_V1
        ust_buton_stili = """
QPushButton {
    background: transparent;
    color: white;
    border: none;
    border-radius: 9px;
    padding: 0px 12px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton:hover {
    background: #30568A;
}
QPushButton:pressed {
    background: #193864;
}
"""

        self.btn_menu.setStyleSheet(
            ust_buton_stili + """
            QPushButton {
                font-family: Arial;
                font-size: 23px;
                font-weight: 600;
                padding: 0px;
            }
            """
        )
        self.btn_menu.setFixedSize(46, 40)
        self.btn_menu.setText("☰")
        self.btn_bildirim.setStyleSheet(ust_buton_stili)
        # TKYS_UST_UCLU_KUTU_DOLU_ZIL_V1
        self.btn_ana_sayfa.setStyleSheet("""
            QPushButton {
                background: #244574;
                color: white;
                border: 1px solid #385A87;
                border-radius: 9px;
                padding: 0px 12px;
            }
            QPushButton:hover {
                background: #30568A;
            }
        """)
        self.btn_ana_sayfa.setText("")

        from PySide6.QtCore import QSize
        from tkys_ust_ikonlar import ust_ikonu, ust_pixmap

        self.btn_bildirim.setIcon(ust_ikonu("bell_outline"))
        self.btn_bildirim.setIconSize(QSize(20, 20))

        self.btn_ana_sayfa.setIcon(ust_ikonu("home"))
        self.btn_ana_sayfa.setIconSize(QSize(20, 20))

        self.ust_baslik.setStyleSheet(
            "color: white; font-size: 17px; "
            "font-weight: 800; padding-left: 12px;"
        )

        self.lbl_ust_kullanici = QLabel()
        self.lbl_ust_kullanici.setStyleSheet("""
QLabel {
    color: white;
    background: #244574;
    border: 1px solid #3A5A85;
    border-radius: 9px;
    padding: 0px 12px;
    font-size: 13px;
    font-weight: 700;
}
""")
        # UST_PANEL_ESIT_BOYUT_V1
        self.btn_bildirim.setFixedHeight(40)
        self.btn_ana_sayfa.setFixedHeight(40)
        self.lbl_ust_kullanici.setFixedHeight(40)

        self.btn_bildirim.setMinimumWidth(56)
        self.btn_ana_sayfa.setFixedWidth(52)
        self.lbl_ust_kullanici.setMinimumWidth(112)
        self.lbl_ust_kullanici.setAlignment(Qt.AlignCenter)

        self.ust_kullanici_kutusu = QFrame()
        self.ust_kullanici_kutusu.setObjectName("ustKullaniciKutusu")
        self.ust_kullanici_kutusu.setFixedHeight(40)
        self.ust_kullanici_kutusu.setMinimumWidth(124)

        self.ust_kullanici_kutusu.setStyleSheet("""
            QFrame#ustKullaniciKutusu {
                background: #244574;
                border: 1px solid #385A87;
                border-radius: 9px;
            }
        """)

        self.ust_kullanici_layout = QHBoxLayout(
            self.ust_kullanici_kutusu
        )
        self.ust_kullanici_layout.setContentsMargins(12, 0, 14, 0)
        self.ust_kullanici_layout.setSpacing(5)
        self.lbl_ust_kullanici.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        self.lbl_ust_kullanici_ikon = QLabel()
        self.lbl_ust_kullanici_ikon.setPixmap(
            ust_pixmap("user", 20)
        )
        self.lbl_ust_kullanici_ikon.setFixedSize(20, 20)
        self.lbl_ust_kullanici_ikon.setStyleSheet(
            "background: transparent; border: none;"
        )

        self.lbl_ust_kullanici.setStyleSheet("""
            color: white;
            background: transparent;
            border: none;
            padding: 0px;
            font-size: 13px;
            font-weight: 700;
        """)
        self.lbl_ust_kullanici.setMinimumWidth(0)

        self.ust_kullanici_layout.addWidget(
            self.lbl_ust_kullanici_ikon
        )
        self.ust_kullanici_layout.addWidget(
            self.lbl_ust_kullanici
        )

        self.gezinme_cubugu.addWidget(
            self.ust_kullanici_kutusu
        )

        for parca in (
            self.ust_kullanici_kutusu,
            self.lbl_ust_kullanici,
            self.lbl_ust_kullanici_ikon,
        ):
            parca.setCursor(Qt.PointingHandCursor)
            parca.installEventFilter(self)

        # INDEX 0: Normal Dashboard (Sol Menü + Sağ İçerik)
        ana_widget = QWidget()
        self.master_stack.addWidget(ana_widget)

        # INDEX 1: Tam Ekran Takvim (Üstünde Geri Ok Butonu ile)
        self.tam_ekran_takvim = QWidget()
        self.tam_ekran_takvim.setStyleSheet("background-color: white;")
        te_layout = QVBoxLayout(self.tam_ekran_takvim)
        te_layout.setContentsMargins(0, 0, 0, 0)
        te_layout.setSpacing(0)


        # 1. Önce takvim sayfasını (widget) oluştur
        self.takvim_widget = HaftalikTakvimEkrani(api_url=self.api_url, token=self.token)
        # 2. Sonra takvimin içindeki yeni geri ok butonuna tıklama görevi ver
        self.takvim_widget.btn_ana_ekrana_don.clicked.connect(self.ana_ekrana_don)
        # 3. Son olarak oluşturulan takvimi tam ekran alanına (layout) yerleştir
        te_layout.addWidget(self.takvim_widget)

        self.master_stack.addWidget(self.tam_ekran_takvim) # INDEX 1 olarak eklendi

        # Ana layout (Sol menü ve sağ panel) Index 0'ın içine kurulmaya devam ediyor
        ana = QHBoxLayout(ana_widget)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(0)

        # ---------------- SOL MENÜ ----------------
        sidebar = QWidget()
        self.sidebar = sidebar
        self._sol_menu_dar = False
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(18, 24, 18, 18)
        sb.setSpacing(6)

        logo = QFrame()
        self.logo_karti = logo
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
        self.rol_karti = rol_kart
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
        self.btn_cikis = btn_cikis
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

        self._bildirim_timer = QTimer(self)
        self._bildirim_timer.setInterval(60000)
        self._bildirim_timer.timeout.connect(self._bildirimleri_yenile)
        self._bildirim_timer.start()

        QTimer.singleShot(0, self._bildirimleri_yenile)
        if self.rol_onizleme:
            self.combo_rol.currentIndexChanged.connect(
                lambda _: QTimer.singleShot(
                    0, self._bildirimleri_yenile
                )
            )


    # ------------------------------------------------------------------

    def _bildirimleri_yenile(self):
        """Yalnizca erisilebilir bildirimleri yukler."""
        if getattr(self, "_oturum_kapatiliyor", False):
            return

        self._bildirimler = []
        self._bildirim_sayisi = 0
        self._bildirim_hata = False

        def getir(yol):
            try:
                yanit = oturum_kontrollu_istek(
                    "GET",
                    f"{self.api_url}{yol}",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=5
                )

                if oturum_hatasi_mi(yanit):
                    self._bildirim_hata = True
                    return None

                if yanit.status_code == 403:
                    return None

                yanit.raise_for_status()
                return yanit.json()

            except (requests.RequestException, ValueError):
                self._bildirim_hata = True
                return None

        # Parola sıfırlama talepleri: yalnızca sıfırlama izni ve Kullanıcı & Personel sayfası olan yöneticiye.
        if self._parola_talepleri_gorebilir_mi():
            talepler = getir("/api/parola-sifirlama-talepleri")

            if isinstance(talepler, list):
                for talep in talepler:
                    self._bildirimler.append((
                        "Parola Talepleri",
                        f"🔐 {talep.get('kullanici_adi', 'Kullanıcı')} parola sıfırlama istedi "
                        f"({self._bekleme_metni(talep.get('bekleme_dakika'))})",
                        "Kullanıcı & Personel"
                    ))
                    self._bildirim_sayisi += 1

        if "Cihaz Envanteri" in self.nav_btnler:
            ozet = getir("/api/dashboard/ozet")

            if isinstance(ozet, dict):
                ariza = int(ozet.get("acik_ariza_sayisi", 0) or 0)

                # Yetkisi olmayan sayfanın bildirimi hiç gösterilmez (başka sayfaya yönlendirilmez).
                if ariza > 0 and self._sayfa_izinli_mi("Arıza Kayıtları"):
                    self._bildirimler.append((
                        "Cihaz Uyarıları",
                        f"⚠️ {ariza} açık arıza kaydı çözüm bekliyor.",
                        "Arıza Kayıtları"
                    ))
                    self._bildirim_sayisi += 1

            islemler = getir("/api/dashboard/yaklasan-islemler")

            if isinstance(islemler, list):
                for islem in islemler:
                    gun = islem.get("kalan_gun")

                    # Sunucu listeyi her kaydın kendi uyarı süresine göre süzer; tarihi geçenler
                    # (kalan gün < 0) da gecikmiş olarak gelir. Burada ek bir gün sınırı uygulanmaz.
                    if not isinstance(gun, (int, float)):
                        continue

                    if gun < 0:
                        zaman, ikon = f"{int(-gun)} gün gecikti", "🔴"
                    elif gun == 0:
                        zaman, ikon = "bugün", "🔧"
                    else:
                        zaman, ikon = f"{int(gun)} gün kaldı", "🔧"

                    metin = (
                        f"{ikon} {islem.get('cihaz_adi', 'Cihaz')} — "
                        f"{islem.get('islem_turu', 'İşlem')} "
                        f"({zaman})"
                    )

                    # Bildirim kendi sayfasını açar (Bakım Kayıtları / Kalibrasyon). Kullanıcının o sayfaya
                    # yetkisi yoksa bildirim hiç gösterilmez (başka sayfaya yönlendirilmez).
                    tur = islem.get("islem_turu")
                    hedef = "Bakım Kayıtları" if tur == "Bakım" else (
                        "Kalibrasyon" if tur == "Kalibrasyon" else None)
                    if hedef is None or not self._sayfa_izinli_mi(hedef):
                        continue

                    self._bildirimler.append((
                        "Cihaz Uyarıları", metin, hedef
                    ))
                    self._bildirim_sayisi += 1

        if "Danışma Masası Yönetimi" in self.nav_btnler:
            veri = getir("/api/danisma/yonetim/onay-bildirimleri")

            if isinstance(veri, dict):
                toplam = int(veri.get("toplam", 0) or 0)

                self._bildirim_sayisi += toplam

                # Tüm danışma masası onaylarını tek bildirimde göster.
                if toplam > 0:
                    self._bildirimler.append((
                        "Danışma Masası",
                        f"📋 {toplam} görev onay bekliyor",
                        "Danışma Masası Yönetimi"
                    ))

        sayi = self._bildirim_sayisi

        if self._bildirim_hata:
            self.btn_bildirim.setText(
                f"{sayi} !" if sayi else "!"
            )
        else:
            self.btn_bildirim.setText(
                str(sayi) if sayi else ""
            )

        # TKYS_BILDIRIM_VURGU_V2
        if self._bildirim_hata:
            arka_plan = "#80511E"
            cerceve = "#E6A64A"
            hover = "#956028"

        elif self._bildirim_sayisi > 0:
            arka_plan = "#244574"
            cerceve = "#648DBB"
            hover = "#315D96"

        else:
            arka_plan = "#244574"
            cerceve = "#3A5A85"
            hover = "#30568A"

        self.btn_bildirim.setStyleSheet(f"""
            QPushButton {{
                background: {arka_plan};
                color: white;
                border: 1px solid {cerceve};
                border-radius: 9px;
                padding: 0px 12px;
                font-size: 13px;
                font-weight: 700;
            }}

            QPushButton:hover {{
                background: {hover};
            }}
        """)

        # TKYS_DINAMIK_ZIL_V1
        from tkys_ust_ikonlar import ust_ikonu

        ikon_adi = (
            "bell" if self._bildirim_sayisi > 0
            else "bell_outline"
        )

        self.btn_bildirim.setIcon(ust_ikonu(ikon_adi))

    def _parola_talepleri_gorebilir_mi(self):
        """Parola sıfırlama taleplerini görmek için hem sıfırlama izni hem Kullanıcı & Personel sayfası gerekir."""
        return (izin_var(self.aktif_rol, "Kullanıcı parola sıfırlama")
                and self._sayfa_izinli_mi("Kullanıcı & Personel"))

    @staticmethod
    def _bekleme_metni(dakika):
        """'az önce', '5 dk önce', '2 saat önce', '3 gün önce'."""
        dakika = max(int(dakika or 0), 0)
        if dakika < 1:
            return "az önce"
        if dakika < 60:
            return f"{dakika} dk önce"
        if dakika < 1440:
            return f"{dakika // 60} saat önce"
        return f"{dakika // 1440} gün önce"

    def _sayfa_izinli_mi(self, sayfa_adi):
        """Kullanıcının menüdeki bir sayfaya yetkisi var mı? Yetkisiz olunan sayfanın bildirimi gösterilmez.

        Menü çizilmeden önce de doğru çalışsın diye menü öğesinin iznine (izin_var) bakar; nav_btnler'e değil."""
        for _, ogeler in MENU:
            for oge in ogeler:
                if oge["ad"] == sayfa_adi:
                    return oge["izin"] is None or izin_var(self.aktif_rol, oge["izin"])
        return False

    def _bildirimden_sayfaya_git(self, sayfa_adi):
        """Bildirimin ilgili oldugu mevcut modulu acar."""
        btn = self.nav_btnler.get(sayfa_adi)

        if btn is None:
            return

        for idx, (ad, _) in enumerate(self.sayfa_bilgi):
            if ad == sayfa_adi:
                self.sayfa_ac(idx)
                btn.setChecked(True)
                return

    def _karttan_sayfaya_git(self, sayfa_adi, cihaz_durumu=None):
        """Ana paneldeki özet kartından ilgili sayfayı açar; cihaz durum kartlarında envanteri o duruma göre süzer."""
        self._bildirimden_sayfaya_git(sayfa_adi)
        ekran = getattr(self, "aktif_cihaz_ekrani", None)
        if sayfa_adi == "Cihaz Envanteri" and ekran is not None:
            ekran.durum_filtrele(cihaz_durumu)

    def _bildirim_menusunu_ac(self):
        """Modern merkezi bildirim panelini acar."""
        from bildirim_paneli import BildirimPaneli

        onceki = getattr(self, "_bildirim_popup", None)

        if onceki is not None and onceki.isVisible():
            onceki.close()
            return

        self._bildirimleri_yenile()

        if getattr(self, "_oturum_kapatiliyor", False):
            return

        panel = BildirimPaneli(
            bildirimler=self._bildirimler,
            toplam=self._bildirim_sayisi,
            hata=self._bildirim_hata,
            sayfa_ac=self._bildirimden_sayfaya_git,
            parent=self
        )

        self._bildirim_popup = panel

        ekran = self.screen().availableGeometry()

        sag = self.mapToGlobal(self.rect().topRight()).x() - 14
        x = max(
            ekran.left() + 8,
            min(sag - panel.width(), ekran.right() - panel.width() - 8)
        )

        alt = self.gezinme_cubugu.mapToGlobal(
            self.gezinme_cubugu.rect().bottomLeft()
        ).y()

        y = max(
            ekran.top() + 8,
            min(alt + 4, ekran.bottom() - panel.height() - 8)
        )

        panel.move(x, y)
        panel.show()



    def _sol_menu_degistir(self):
        """Sol menuyu daraltir veya genisletir."""
        self._sol_menu_dar = not self._sol_menu_dar
        self._sol_menu_gorunumunu_uygula()

    def _sol_menu_gorunumunu_uygula(self):
        sidebar = getattr(self, "_sidebar_elegant", None)
        if sidebar is not None:
            sidebar.refresh()

    def eventFilter(self, nesne, olay):
        kullanici_alanlari = (
            getattr(self, "ust_kullanici_kutusu", None),
            getattr(self, "lbl_ust_kullanici", None),
            getattr(self, "lbl_ust_kullanici_ikon", None),
        )

        if (
            nesne in kullanici_alanlari
            and olay.type() == QEvent.MouseButtonRelease
            and olay.button() == Qt.LeftButton
        ):
            self._kullanici_hesap_menusu()
            return True

        return super().eventFilter(nesne, olay)

    def _kullanici_hesap_menusu(self):
        if self._oturum_kapatiliyor:
            return

        from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QPushButton

        mevcut = getattr(self, "_hesap_popup", None)
        if mevcut is not None and mevcut.isVisible():
            mevcut.close()
            return

        popup = QWidget(
            self,
            Qt.Popup | Qt.FramelessWindowHint
        )
        popup.setAttribute(Qt.WA_TranslucentBackground)
        popup.setObjectName("hesapPopup")

        dis = QVBoxLayout(popup)
        dis.setContentsMargins(4, 5, 4, 5)

        kart = QFrame()
        kart.setObjectName("hesapKart")
        kart.setStyleSheet("""
            QFrame#hesapKart {
                background: #FFFFFF;
                border: 1px solid #D3E1F2;
                border-radius: 12px;
            }
            QPushButton#hesapSifre {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #243653;
                font-size: 13px;
                font-weight: 700;
                text-align: left;
                padding: 10px 12px;
            }
            QPushButton#hesapSifre:hover {
                background: #EAF2FF;
                color: #075BD8;
            }
        """)

        ic = QVBoxLayout(kart)
        ic.setContentsMargins(6, 6, 6, 6)
        ic.setSpacing(0)

        sifre_btn = QPushButton("🔑  Şifremi Değiştir")
        sifre_btn.setObjectName("hesapSifre")
        sifre_btn.setCursor(Qt.PointingHandCursor)
        sifre_btn.setFixedHeight(38)
        ic.addWidget(sifre_btn)

        ayirici = QFrame()
        ayirici.setFrameShape(QFrame.HLine)
        ayirici.setStyleSheet(
            "background: #E3EAF5; border: none; max-height: 1px;"
        )
        ic.addWidget(ayirici)

        cikis_btn = QPushButton("⏻  Çıkış Yap")
        cikis_btn.setObjectName("hesapSifre")
        cikis_btn.setCursor(Qt.PointingHandCursor)
        cikis_btn.setFixedHeight(38)
        cikis_btn.setStyleSheet("""
            QPushButton#hesapSifre {
                background: transparent;
                border: none;
                border-radius: 8px;
                color: #B42332;
                font-size: 13px;
                font-weight: 700;
                text-align: left;
                padding: 10px 12px;
            }
            QPushButton#hesapSifre:hover {
                background: #FFF0F0;
                color: #991B1B;
            }
        """)
        ic.addWidget(cikis_btn)

        dis.addWidget(kart)

        popup.setFixedWidth(230)
        popup.adjustSize()

        def sifre_ac():
            popup.close()
            self._kisisel_sifre_penceresini_ac()

        sifre_btn.clicked.connect(sifre_ac)

        def cikis_yap():
            popup.close()
            self.oturum_kapat()

        cikis_btn.clicked.connect(cikis_yap)

        konum = self.ust_kullanici_kutusu.mapToGlobal(
            self.ust_kullanici_kutusu.rect().bottomRight()
        )

        popup.move(
            konum.x() - popup.width(),
            konum.y() + 3
        )

        self._hesap_popup = popup
        popup.show()

    def _kisisel_sifre_penceresini_ac(self):
        if self._oturum_kapatiliyor or not self.token:
            return

        from sifre_degistir_ekrani import SifreDegistirEkrani

        mevcut = getattr(self, "sifre_penceresi", None)
        if mevcut is not None and mevcut.isVisible():
            mevcut.raise_()
            mevcut.activateWindow()
            return

        self.sifre_penceresi = SifreDegistirEkrani(
            self.token, ilk_giris=False
        )
        self.sifre_penceresi.sifre_degistirildi.connect(
            self._kisisel_sifre_degisti
        )
        self.sifre_penceresi.show()

    def _kisisel_sifre_degisti(self):
        self.sifre_penceresi.close()

        QMessageBox.information(
            self,
            "Şifre Değiştirildi",
            "Şifreniz başarıyla değiştirildi. Lütfen yeniden giriş yapın."
        )
        self.oturum_kapat()

    def rol_uygula(self, rol):
        from tkys_logo_widget import sol_panel_logosu_kur
        sol_panel_logosu_kur(self)
        old_sidebar = getattr(self, "_sidebar_elegant", None)
        if old_sidebar is not None:
            if old_sidebar.popup is not None:
                old_sidebar.popup.close()
            old_sidebar.deleteLater()
            self._sidebar_elegant = None
        self.aktif_rol = rol
        kullanici = self.kullanici_adi or ROL_BILGI[rol]["ad"]
        self.lbl_ust_kullanici.setText(str(kullanici))
        info = ROL_BILGI[rol]
        self.setWindowTitle(f"TKYS — Travma Kaynak Yönetim Sistemi  [{info['ad'].upper()} OTURUMU]")
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
                btn.setProperty("tkys_ikon", oge["ikon"])
                btn.setToolTip(oge["ad"])
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
        from tkys_sidebar_refined import ElegantSidebar
        self._sidebar_elegant = ElegantSidebar(self)  # TKYS_ELEGANT_MENU_2026
        self._sol_menu_gorunumunu_uygula()

        if ilk_btn:
            ilk_btn.setChecked(True)
            self.sayfa_ac(0)

        aktif = sum(1 for a in IZIN if izin_var(rol, a))
        self.statusBar().hide()

    def _api_token_reddedildi(self, token, neden):
        """Yalnizca aktif oturumun token hatasini isler."""

        if token != self.token or self._oturum_kapatiliyor:
            return

        self._oturum_nedeni = neden
        self._oturum_kapatiliyor = True
        self._oturum_zamanlayici.stop()

        QTimer.singleShot(0, self._api_oturum_uyarisi)

    def _oturum_pencerelerini_temizle(self):
        """Yalnizca mevcut oturuma ait pencereleri temizler."""
        from PySide6.QtWidgets import QDialog

        if getattr(self, "_pencereler_temizlendi", False):
            return

        self._pencereler_temizlendi = True

        # Oturuma ait zamanlayicilari durdur
        for zamanlayici in self.findChildren(QTimer):
            zamanlayici.stop()

        # Ana pencereye bagli modal formlar
        pencereler = list(self.findChildren(QDialog))

        # Ana pencereden bagimsiz acilan formlar
        bagimsiz_formlar = (
            "oda_ekle_penceresi",
            "oda_duzenle_penceresi",
            "sifre_penceresi",
            "randevu_formu",
            "liste_formu",
        )

        for ad in bagimsiz_formlar:
            pencere = getattr(self, ad, None)

            if isinstance(pencere, QWidget):
                pencereler.append(pencere)

        gorulen = set()

        for pencere in pencereler:
            if id(pencere) in gorulen:
                continue

            gorulen.add(id(pencere))

            try:
                if not pencere.isVisible():
                    continue

                if isinstance(pencere, QDialog):
                    pencere.reject()
                else:
                    pencere.close()

            except RuntimeError:
                # Qt tarafindan daha once silinmis pencere
                continue

    def _api_oturum_uyarisi(self):
        self._oturum_pencerelerini_temizle()

        mesaj = (
            "Oturum süreniz sona ermiştir.\n\n"
            if getattr(self, "_oturum_nedeni", "sure_doldu") == "sure_doldu"
            else "Oturumunuz geçersiz hâle gelmiştir.\n\n"
        )

        QMessageBox.information(
            self,
            "Oturum Sona Erdi",
            mesaj + "Uygulamayı kullanmaya devam etmek için "
            "lütfen yeniden giriş yapın.",
                    )

        self.oturum_kapat()

    def _yetkileri_sunucudan_al(self):
        """Giriş yapan kullanıcının izinlerini sunucudan alır (menü bu izinlere göre çizilir).

        Alınamazsa (rol önizlemesi, token yok, eski sunucu, bağlantı sorunu) elle yazılmış
        yetki tablosuna dönülür; uygulama açılmaya devam eder.
        """
        rol = self.aktif_rol
        yetkileri_temizle(rol)
        if not self.token or self.rol_onizleme:
            return
        try:
            cevap = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/yetkilerim",
                headers={"Authorization": f"Bearer {self.token}"}, timeout=5,
            )
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                veri = cevap.json()
                izinler = veri.get("izinler")
                if isinstance(izinler, list):
                    yetkileri_ayarla(rol, izinler)
                    self._sunucu_rol_adi = veri.get("rol_adi")      # rol sonradan değişirse fark edilsin
                    return
        except Exception as e:
            print("Yetkiler sunucudan alınamadı, yerel tablo kullanılacak:", e)

    # ------------------------------------------------------------------ açık oturumda yetki yenileme
    # Yönetici bir rolün izinlerini değiştirdiğinde ya da kullanıcının rolünü değiştirdiğinde, o kullanıcı
    # uygulamayı kapatıp açmak zorunda kalmasın: menü kısa aralıklarla sunucudaki yetkilerle karşılaştırılır.
    YETKI_YENILEME_ARALIGI_MS = 20_000
    YETKI_HATA_SONRASI_ATLANAN_TUR = 3        # sunucuya ulaşılamazsa art arda denemeyip bir süre beklenir

    def _yetki_zamanlayicisini_kur(self):
        self._yetki_istegi_suruyor = False
        self._yetki_atlanan_tur = 0
        self._yetki_zamanlayici = QTimer(self)
        self._yetki_zamanlayici.setInterval(self.YETKI_YENILEME_ARALIGI_MS)
        self._yetki_zamanlayici.timeout.connect(self._yetkileri_denetle)
        if self.token and not self.rol_onizleme:
            self._yetki_zamanlayici.start()

    def _yetkileri_denetle(self):
        """Sunucudaki güncel yetkileri alır; değiştiyse menüyü yeniler, rol değiştiyse yeniden girişi ister."""
        if self._oturum_kapatiliyor or self.rol_onizleme or not self.token or self._yetki_istegi_suruyor:
            return
        if self._yetki_atlanan_tur > 0:
            self._yetki_atlanan_tur -= 1
            return
        if QApplication.activeModalWidget() is not None:
            return                                   # kullanıcı bir pencerede çalışıyor; bir sonraki turda bakılır

        self._yetki_istegi_suruyor = True
        try:
            cevap = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/yetkilerim",
                headers={"Authorization": f"Bearer {self.token}"}, timeout=2,
            )
            if oturum_hatasi_mi(cevap) or cevap.status_code != 200:
                return
            veri = cevap.json()
        except Exception:
            self._yetki_atlanan_tur = self.YETKI_HATA_SONRASI_ATLANAN_TUR      # ağ sorunu: sessizce bekle
            return
        finally:
            self._yetki_istegi_suruyor = False

        self._yeni_yetkileri_uygula(veri)

    def _yeni_yetkileri_uygula(self, veri):
        izinler = veri.get("izinler") if isinstance(veri, dict) else None
        if not isinstance(izinler, list):
            return

        rol_adi = veri.get("rol_adi")
        onceki_rol = getattr(self, "_sunucu_rol_adi", None)
        if onceki_rol is not None and rol_adi != onceki_rol:
            self._rol_degisti_uyarisi()
            return

        if _SUNUCU_YETKILERI.get(self.aktif_rol) == frozenset(izinler):
            return                                   # değişiklik yok

        yetkileri_ayarla(self.aktif_rol, izinler)
        self._sunucu_rol_adi = rol_adi
        self._menuyu_yeniden_kur()

    def _menuyu_yeniden_kur(self):
        """Menüyü ve sayfaları yeni yetkilere göre yeniden çizer; kullanıcı açık olan sayfada kalır (yetkisi sürüyorsa)."""
        acik_sayfa = None
        if 0 <= self.stack.currentIndex() < len(self.sayfa_bilgi):
            acik_sayfa = self.sayfa_bilgi[self.stack.currentIndex()][0]

        self.rol_uygula(self.aktif_rol)

        if acik_sayfa in self.nav_btnler:
            self._bildirimden_sayfaya_git(acik_sayfa)

        QMessageBox.information(
            self,
            "Yetkileriniz Güncellendi",
            "Yöneticiniz yetkilerinizde değişiklik yaptı. Menü yeni yetkilerinize göre yenilendi.",
        )

    def _rol_degisti_uyarisi(self):
        """Rol değişince yetkilerin tamamı değişir; yeni rol için yeniden giriş yapılır."""
        self._yetki_zamanlayici.stop()
        QMessageBox.information(
            self,
            "Rolünüz Değişti",
            "Yöneticiniz rolünüzü değiştirdi.\n\n"
            "Yeni yetkilerinizin geçerli olması için lütfen yeniden giriş yapın.",
        )
        self.oturum_kapat()

    def _token_bitisini_oku(self):
        """JWT bitiş zamanını zamanlayıcı için okur."""
        if not self.token:
            return 0

        try:
            parca = self.token.split(".")[1]
            parca += "=" * (-len(parca) % 4)

            veri = json.loads(
                base64.urlsafe_b64decode(parca)
            )

            return int(veri["exp"])

        except (ValueError, TypeError, KeyError, IndexError):
            return 0

    def _oturum_suresini_kontrol_et(self):
        """Token süresi dolunca oturumu sonlandırır."""
        if self._oturum_kapatiliyor:
            return

        if time.time() < self._token_bitis_zamani:
            return

        self._oturum_kapatiliyor = True
        self._oturum_zamanlayici.stop()
        self._oturum_pencerelerini_temizle()

        QMessageBox.information(
            self,
            "Oturum Sona Erdi",
            "Oturum süreniz sona ermiştir.\n\n"
            "Uygulamayı kullanmaya devam etmek için "
            "lütfen yeniden giriş yapın.",
                    )

        self.oturum_kapat()

    def oturum_kapat(self):
        self._oturum_kapatiliyor = True
        self._oturum_zamanlayici.stop()
        self._yetki_zamanlayici.stop()
        self._oturum_pencerelerini_temizle()

        try:
            oturum_olaylari.token_reddedildi.disconnect(
                self._api_token_reddedildi
            )
        except (TypeError, RuntimeError):
            pass

        self.oturum_kapatildi.emit()
        self.close()

    def yeni_oda_formunu_ac(self):
        self.oda_ekle_penceresi = OdaFormu(api_url=self.api_url, token=self.token)

        orijinal_close = self.oda_ekle_penceresi.closeEvent
        def kapanma_yakala(event):
            if not self._oturum_kapatiliyor:
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
            if not self._oturum_kapatiliyor:
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
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if cevap == QMessageBox.Yes:
            headers = {"Authorization": f"Bearer {self.token}"}
            try:
                res = oturum_kontrollu_istek("PATCH",
                    f"{self.api_url}/api/odalar/{oda_id}",
                    json={"aktif_mi": False},
                    headers=headers,
                    timeout=5
                )
                if oturum_hatasi_mi(res):
                    return

                if res.status_code == 200:
                    QMessageBox.information(self, "Başarılı", "Oda başarıyla pasife alındı.")
                    self.odalari_getir()
                else:
                    if res.status_code == 409:
                        try:
                            mesaj = res.json().get("detail") or "Oda pasife alınamadı."
                        except Exception:
                            mesaj = "Oda pasife alınamadı."
                        QMessageBox.warning(self, "Oda Pasife Alınamadı", mesaj)
                    else:
                        QMessageBox.warning(self, "Hata", f"İşlem başarısız (Kod: {res.status_code})")
            except Exception as e:
                QMessageBox.critical(self, "Hata", f"Bağlantı hatası:\n{str(e)}")

    # Sayfa adı -> (ekran özniteliği, yenileme metodu). Sayfalar açılışta bir kez oluşturulduğundan,
    # kullanıcı sayfaya (menüden ya da bildirimden) geçtiğinde liste güncel veriyle yeniden yüklenir.
    SAYFA_YENILEME = {
        "Öğrenciler": ("ogrenciler_ekrani", "yenile"),
        "Puan Raporu": ("puan_raporu_ekrani", "yenile"),
        "Cihaz Uygunluğu": ("aktif_uygunluk_ekrani", "verileri_yukle"),
        "Cihaz Envanteri": ("aktif_cihaz_ekrani", "verileri_yukle"),
        "Kalibrasyon": ("aktif_kalibrasyon_ekrani", "yukle"),
        "Cihaz Rezervasyonu": ("aktif_rezervasyon_ekrani", "verileri_yukle"),
        "Bakım Planları": ("aktif_plan_ekrani", "verileri_yukle"),
        "Kullanıcı & Personel": ("aktif_personel_ekrani", "verileri_cek"),
        "Arıza Kayıtları": ("aktif_ariza_ekrani", "verileri_yukle"),
        "Bakım Kayıtları": ("aktif_bakim_ekrani", "verileri_yukle"),
        # Oda tablosu ana pencerenin kendi içinde olduğundan ekran yerine None (= ana pencerenin kendisi) yazılır.
        "Oda Yönetimi": (None, "odalari_getir"),
        "Danışanlar": ("danisanlar_ekrani", "verileri_cek"),
        "Randevu Yönetimi": ("randevu_ana_ekrani", "verileri_cek"),
    }
    SAYFA_YENILEME_ARALIGI = 2.0     # saniye; art arda tıklamada gereksiz istek atılmaz

    def _sayfayi_yenile(self, ad):
        hedef = self.SAYFA_YENILEME.get(ad)
        if not hedef:
            return
        ekran = self if hedef[0] is None else getattr(self, hedef[0], None)
        yontem = getattr(ekran, hedef[1], None) if ekran is not None else None
        if yontem is None:
            return
        simdi = time.monotonic()
        son = self.__dict__.setdefault("_sayfa_son_yenileme", {})
        if simdi - son.get(ad, -1e9) < self.SAYFA_YENILEME_ARALIGI:
            return
        son[ad] = simdi
        try:
            yontem()
        except Exception as e:
            print(f"Sayfa yenileme hatası ({ad}):", e)

    def sayfa_ac(self, idx):
        ad, alt = self.sayfa_bilgi[idx]
        self.ust_sayfa.setText(f"›   {ad}")

        # Ana panelden gelen durum filtresi yalnızca o geçişe aittir; menüden/bildirimden açılışta temiz başlar.
        envanter = getattr(self, "aktif_cihaz_ekrani", None)
        if ad == "Cihaz Envanteri" and envanter is not None:
            envanter.durum_filtresini_temizle()

        if ad == "Oda Kullanımı":
            self.master_stack.setCurrentIndex(1)
            self.stack.setCurrentIndex(idx)
        else:
            self.master_stack.setCurrentIndex(0)
            self.stack.setCurrentIndex(idx)
        self._sayfayi_yenile(ad)

    def ogrenciler_sayfasina_git(self, yeni_ekle=False):
        if "Öğrenciler" not in self.nav_btnler:
            QMessageBox.warning(
                self,
                "Yetki",
                "Öğrenciler sayfasına erişim yetkiniz yok."
            )
            return

        self._bildirimden_sayfaya_git("Öğrenciler")

        if yeni_ekle:
            QTimer.singleShot(
                0,
                self.ogrenciler_ekrani.yeni_ogrenci_ekle
            )

    def ana_ekrana_don(self):
        self.master_stack.setCurrentIndex(0)
        if "Ana Kontrol Paneli" in self.nav_btnler:
            self.nav_btnler["Ana Kontrol Paneli"].setChecked(True)
            for i, (ad, _) in enumerate(self.sayfa_bilgi):
                if ad == "Ana Kontrol Paneli":
                    self.sayfa_ac(i)
                    break

    def oda_psikolog_atamalarini_getir(self):
        """Oda -> atanmış psikologlar (bilgi amaçlı). Alınamazsa boş sözlük döner, sütun "-" gösterir."""
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/oda-psikolog-atamalari", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap) or cevap.status_code != 200:
                return {}
            return {a["oda_id"]: ", ".join(a["psikologlar"]) for a in cevap.json()}
        except Exception:
            return {}

    def odalari_getir(self):
        if not hasattr(self, 'oda_tablosu'):
            return

        import requests
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/odalar", headers=headers, timeout=5)
            if oturum_hatasi_mi(cevap):
                return
            if cevap.status_code == 200:
                odalar = cevap.json()
                self.oda_tablosu.setRowCount(len(odalar))
                atamalar = self.oda_psikolog_atamalarini_getir()

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
                    item_psikolog = QTableWidgetItem(atamalar.get(oda["oda_id"], "-"))
                    item_psikolog.setTextAlignment(Qt.AlignCenter)
                    self.oda_tablosu.setItem(satir, 4, item_psikolog)
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

        # Randevu listesi her rolde, cihaz özeti yalnızca cihaz envanteri iznine sahip rollerde gösterilir.
        # Bu özetin sunucu uçları da aynı izni ister; izin rol adına değil veritabanındaki yetkiye bağlıdır.
        self.istatistik_paneli = DashboardEkrani(
            self.api_url,
            self.token,
            cihaz_ozeti=cihaz_ozeti_gorebilir_mi(rol),
            sayfa_ac=self._bildirimden_sayfaya_git,
            sayfa_izinli_mi=self._sayfa_izinli_mi,
            kart_ac=self._karttan_sayfaya_git,
            parola_talepleri_goster=self._parola_talepleri_gorebilir_mi(),
        )
        lay.addWidget(self.istatistik_paneli)

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


        # Bu satırlar if bloğunun DIŞINDA olmalı.
        lay.addStretch()
        return _tkys_dashboard_kompakt(self.kaydirmali(govde))

    # ---------------- EKRANLAR: BUTONLARIN DİNAMİK EKLENDİĞİ YER ----------------
    def sayfa_modul(self, oge):
        rol = self.aktif_rol
        govde = QWidget()
        lay = QVBoxLayout(govde)
        lay.setContentsMargins(4, 0, 4, 16)
        lay.setSpacing(10)

        # Sayfa başlığı ve açıklaması üst çubukta (TKYS › Sayfa adı) gösterilir; sayfada ayrıca büyük başlık kartı yoktur.
        yetkili = [a for a in oge["aksiyon"] if izin_var(rol, a[1])]

        if oge["ad"] == "Danışma Masası Yönetimi":
            danisma_islemleri = [
                ("Görev Onaylama", "Danışma masası yönetimi"),
                ("Görev Düzenleme", "Danışma masası yönetimi"),
            ]
            yetkili.extend(
                a for a in danisma_islemleri
                if izin_var(rol, a[1])
            )


        # 2. Yetki Butonlarının Eklenmesi ve Routing Bağlantıları
        if yetkili and oge["ad"] not in ("Danışma Masası", "Danışma Masası Yönetimi"):
            ab = QHBoxLayout()
            ab.setSpacing(8)
            ab.addStretch()
            for etiket, izin_kodu in yetkili:
                btn = QPushButton(etiket)
                btn.setObjectName("aksiyon")
                btn.setCursor(Qt.PointingHandCursor)

                # İzin koduna veya etikete bakarak ilgili fonksiyonları bağla
                # İzin koduna veya etikete bakarak ilgili fonksiyonları bağla
                if "Yeni Randevu" in etiket:
                    btn.clicked.connect(self.yeni_randevu_ekrani_ac)
                elif "Yeni Danışan" in etiket:
                    btn.clicked.connect(self.hizli_danisan_kod_olustur)
                elif izin_kodu == "Arıza kayıtlarını yönetme":
                    btn.clicked.connect(self.yeni_ariza_bildirimi_ac)
                elif etiket == "✓  Tamamlandı":
                    btn.clicked.connect(lambda: self.randevu_ana_ekrani.durum_isaretle("TAMAMLANDI") if hasattr(self, 'randevu_ana_ekrani') else None)
                elif etiket == "✗  Gelmedi":
                    btn.clicked.connect(lambda: self.randevu_ana_ekrani.durum_isaretle("GELMEDI") if hasattr(self, 'randevu_ana_ekrani') else None)
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
                elif etiket == "＋  Yeni Oda Ekle":
                    btn.clicked.connect(self.yeni_oda_formunu_ac)
                elif etiket == "✎  Odayı Düzenle":
                    btn.clicked.connect(self.odayi_duzenle)
                elif etiket == "✕  Odayı Pasife Al":
                    btn.clicked.connect(self.odayi_pasife_al)
                elif etiket == "＋  Kalibrasyon Kaydı":
                    btn.clicked.connect(lambda: self.aktif_kalibrasyon_ekrani.yeni_ekle() if hasattr(self, 'aktif_kalibrasyon_ekrani') else None)
                elif izin_kodu == "Danışma masası oturumunu yönetme":
                    btn.clicked.connect(lambda: self.danisma_ekrani.yenile())

                # --- YENİ EKLENEN BAKIM BUTONU ---
                elif etiket == "＋  Bakım Kaydı":
                    btn.clicked.connect(self.yeni_bakim_ekrani_ac)
                elif etiket == "＋  Yeni Plan":
                    btn.clicked.connect(self.yeni_bakim_plani_ac)
                elif etiket == "＋  Kullanıcı Oluştur":
                    btn.clicked.connect(self.yeni_kullanici_formunu_ac)
                elif "Aktiflik Düzenle" in etiket:
                    btn.clicked.connect(lambda: self.aktif_personel_ekrani.secili_kullanici_durum_degistir() if hasattr(self, 'aktif_personel_ekrani') else None)
                elif etiket == "🔑  Parola Sıfırla":
                    btn.clicked.connect(
                        lambda: (
                            self.aktif_personel_ekrani.secili_kullanici_parola_sifirla()
                            if hasattr(self, "aktif_personel_ekrani")
                            else None
                        )
                    )
                elif "Oda Yetkileri" in etiket:
                    btn.clicked.connect(lambda: self.aktif_personel_ekrani.secili_kullanici_oda_yetkileri() if hasattr(self, 'aktif_personel_ekrani') else None)
                elif "Rol Ata / Değiştir" in etiket:
                    btn.clicked.connect(lambda: self.aktif_personel_ekrani.secili_kullanici_rol_degistir() if hasattr(self, 'aktif_personel_ekrani') else None)
                elif etiket == "＋  Yeni Faaliyet Ekle":
                    btn.clicked.connect(self.yeni_faaliyet_ekrani_ac)
                elif "Faaliyet Düzenle" in etiket:
                    btn.clicked.connect(self.faaliyet_duzenle_tetikle)
                elif "Faaliyet Sil" in etiket:
                    btn.clicked.connect(self.faaliyet_sil_tetikle)
                    btn.setStyleSheet("background-color: #E74C3C; color: white; font-weight: bold; border-radius: 4px;") # Kan kırmızı tehlike butonu
                elif "Rol Oluştur" in etiket:
                    btn.clicked.connect(self.rol_olustur_ac)
                elif "Rol Düzenle" in etiket:
                    btn.clicked.connect(self.rol_duzenle_diyalog_ac)
                elif "Faaliyet Birimleri" in etiket:
                    btn.clicked.connect(self.faaliyet_birimleri_ekrani_ac)
                elif "Faaliyet Türleri" in etiket:
                    btn.clicked.connect(self.faaliyet_turleri_ekrani_ac)
                elif "İzin Düzenle" in etiket:
                    btn.clicked.connect(self.izin_duzenle_tetikle)

                ab.addWidget(btn)
            lay.addLayout(ab)

        # 3. SAYFA İÇERİĞİNİN (TABLOLARIN vs.) YÜKLENDİĞİ YER
        if oge["ad"] == "Danışma Masası":
            from danisma_masasi_ekrani import DanismaMasasiEkrani
            self.danisma_ekrani = DanismaMasasiEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.danisma_ekrani, 1)

        elif oge["ad"] == "Audit Kayıtları":
            from audit_kayitlari_ekrani import AuditKayitlariEkrani

            self.audit_ekrani = AuditKayitlariEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.audit_ekrani, 1)

        elif oge["ad"] == "Danışma Masası Yönetimi":
            from danisma_masasi_yonetimi import DanismaMasasiYonetimi

            self.danisma_yonetim_ekrani = DanismaMasasiYonetimi(
                api_url=self.api_url,
                token=self.token
            )

            lay.addWidget(self.danisma_yonetim_ekrani, 1)

        elif oge["ad"] == "Danışma Masası Raporları":
            from danisma_masasi_raporlari import DanismaMasasiRaporlari

            self.danisma_rapor_ekrani = DanismaMasasiRaporlari(
                api_url=self.api_url,
                token=self.token
            )

            lay.addWidget(self.danisma_rapor_ekrani, 1)

        elif oge["ad"] == "Cihaz Uygunluğu":
            # Takvim yalnızca görüntüleme izniyle açılır; işlem düğmeleri kullanıcının ilgili izni varsa görünür.
            self.aktif_uygunluk_ekrani = CihazUygunlukEkrani(
                api_url=self.api_url,
                token=self.token,
                yetkiler={
                    "rezervasyon": izin_var(rol, "Cihaz rezervasyonu yapma"),
                    "ariza": izin_var(rol, "Arıza kayıtlarını yönetme"),
                    "bakim": izin_var(rol, "Bakım kayıtlarını yönetme"),
                    "kalibrasyon": izin_var(rol, "Kalibrasyon kayıtlarını yönetme"),
                },
                sayfaya_git=self._bildirimden_sayfaya_git,
                rezervasyon_ac=self._uygunluktan_rezervasyon_ac,
            )
            lay.addWidget(self.aktif_uygunluk_ekrani, 1)

        elif oge["ad"] == "Cihaz Envanteri":
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

        elif oge["ad"] == "Cihaz Raporları":
            from cihaz_raporlari_ekrani import CihazRaporlariEkrani

            self.aktif_cihaz_rapor_ekrani = CihazRaporlariEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.aktif_cihaz_rapor_ekrani, 1)


        # =========================================================
        # CİHAZ BAKIM KAYITLARI (MNT-002) YÖNLENDİRMESİ
        # =========================================================
        elif oge["ad"] == "Bakım Kayıtları":
            self.aktif_bakim_ekrani = BakimYonetimEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.aktif_bakim_ekrani, 1)
        elif oge["ad"] == "Bakım Planları":
            from bakim_plani_ekranlari import BakimPlanlariEkrani

            self.aktif_plan_ekrani = BakimPlanlariEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.aktif_plan_ekrani, 1)
        elif oge["ad"] == "Kullanıcı & Personel":
            self.aktif_personel_ekrani = KullaniciPersonelEkrani(
                api_url=self.api_url,
                token=self.token
            )
            lay.addWidget(self.aktif_personel_ekrani, 1)
            
        elif oge["ad"] == "Oda Yönetimi":
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)

            self.oda_tablosu = QTableWidget()
            self.oda_tablosu.setColumnCount(5)
            self.oda_tablosu.setHorizontalHeaderLabels(["Oda ID", "Oda Adı", "Kapasite", "Durum", "Psikologlar"])
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

        elif oge["ad"] == "Randevu Yönetimi":
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)

            from randevu_ekranlari import RandevuAnaEkrani
            self.randevu_ana_ekrani = RandevuAnaEkrani(
                api_url=self.api_url, 
                token=self.token, 
                mevcut_psikolog_id=self.kullanici_id,
                rol=self.kullanici_adi
            )
            il.addWidget(self.randevu_ana_ekrani)

            lay.addWidget(ik, 1)

        elif oge["ad"] == "Danışanlar":
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)

            from danisanlar_ekrani import DanisanlarEkrani
            self.danisanlar_ekrani = DanisanlarEkrani(
                api_url=self.api_url, token=self.token, mevcut_psikolog_id=self.kullanici_id
            )
            il.addWidget(self.danisanlar_ekrani)

            lay.addWidget(ik, 1)

        elif oge["ad"] == "Öğrenciler":
            from ogrenci_yonetim_ekrani import OgrenciYonetimEkrani

            self.ogrenciler_ekrani = OgrenciYonetimEkrani(
                api_url=self.api_url,
                token=self.token,
                parent=self
            )
            lay.addWidget(self.ogrenciler_ekrani, 1)

        elif oge["ad"] == "Puan Raporu":
            from puan_raporu_ekrani import PuanRaporuEkrani

            self.puan_raporu_ekrani = PuanRaporuEkrani(
                api_url=self.api_url,
                token=self.token,
            )
            lay.addWidget(self.puan_raporu_ekrani, 1)

        elif oge["ad"] == "Faaliyet Kayıtları":
            ik = kart_olustur()
            ik.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            il = QVBoxLayout(ik)

            self.tablo_faaliyetler = QTableWidget()
            self.tablo_faaliyetler.setColumnCount(7)
            self.tablo_faaliyetler.setHorizontalHeaderLabels([
                "ID", "Öğrenci Adı", "Öğrenci No", "Faaliyet", "Miktar", "Toplam Puan", "Tarih"
            ])
            self.tablo_faaliyetler.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.tablo_faaliyetler.setEditTriggers(QAbstractItemView.NoEditTriggers)
            self.tablo_faaliyetler.setSelectionBehavior(QAbstractItemView.SelectRows)

            self.tablo_faaliyetler.setStyleSheet("""
                QTableWidget {
                    background-color: white;
                    color: #2C3E50; /* YAZI RENGİNİ ZORLA KOYU LACİVERT/SİYAH YAPTIK */
                    border: 1px solid #D0D7E5;
                    border-radius: 8px;
                    gridline-color: #E2E8F0;
                }
                QTableWidget::item {
                    color: #2C3E50; /* Hücre içindeki yazılar kesinlikle görünür olacak */
                }
                QTableWidget::item:selected {
                    background-color: #3498DB; /* Satıra tıklanınca arka plan mavi */
                    color: white; /* Satıra tıklanınca yazı beyaz */
                }
                QHeaderView::section {
                    background-color: #0A1F5C;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border: none;
                }
            """)
            il.addWidget(self.tablo_faaliyetler)

            # Tablo çizildiği an veriyi çekecek fonksiyonu çağırıyoruz
            self.faaliyet_tablosunu_guncelle()

            lay.addWidget(ik, 1)

        elif oge["ad"] == "Rol & İzin Yönetimi":
            self.rol_izin_sayfasi = RolIzinSayfasi(token=self.token, api_url=self.api_url)
            lay.addWidget(self.rol_izin_sayfasi, 1)

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
        
        # Form başarıyla kaydedildiğinde tabloyu doğrudan tetikle
        if hasattr(self, 'randevu_ana_ekrani'):
            self.randevu_formu.veriler_degisti.connect(self.randevu_ana_ekrani.verileri_cek)

        orijinal_close = self.randevu_formu.closeEvent
        def kapanma_yakala(event):
            if (
                not self._oturum_kapatiliyor
                and hasattr(self, 'randevu_ana_ekrani')
            ):
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

    def hizli_danisan_kod_olustur(self):
        from danisan_diyalog import DanisanOlusturDialog

        # Danışanlar sayfasında seçili psikolog varsa yeni danışan için önerilir
        onceden = None
        sayfa = getattr(self, 'danisanlar_ekrani', None)
        if sayfa is not None:
            onceden = sayfa.cmb_psikolog.currentData()
        dialog = DanisanOlusturDialog(
            api_url=self.api_url, token=self.token, ebeveyn=self,
            mevcut_psikolog_id=self.kullanici_id, onceden_psikolog_id=onceden,
        )
        if dialog.exec():
            # Kullanıcı bizzat pencereyi açıp "Danışanı Oluştur" butonuna basarsa yeni kod üretilir.
            if hasattr(self, 'randevu_ana_ekrani'):
                self.randevu_ana_ekrani.verileri_cek()
            if hasattr(self, 'danisanlar_ekrani'):
                self.danisanlar_ekrani.verileri_cek()

    def cihaz_ekle_tetikle(self):
        if hasattr(self, 'aktif_cihaz_ekrani'):
            self.aktif_cihaz_ekrani.yeni_cihaz_ekle()

    def cihaz_envanter_duzenle_tetikle(self):
        if hasattr(self, 'aktif_cihaz_ekrani'):
            self.aktif_cihaz_ekrani.envanter_duzenle_liste_ac()

    def _uygunluktan_rezervasyon_ac(self, cihaz_id, gun, baslangic, bitis):
        """Cihaz Uygunluğu takviminden: Rezervasyon sayfasına geçip formu cihaz, gün ve saatle açar."""
        if "Cihaz Rezervasyonu" not in self.nav_btnler or not hasattr(self, "aktif_rezervasyon_ekrani"):
            return
        self._bildirimden_sayfaya_git("Cihaz Rezervasyonu")
        self.aktif_rezervasyon_ekrani.yeni_rezervasyon_olustur(
            cihaz_id=cihaz_id, tarih=gun, baslangic_saati=baslangic, bitis_saati=bitis)

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
    def yeni_bakim_plani_ac(self):
        """Ana yetki kartındaki 'Yeni Plan' butonuna basılınca plan formunu açar."""
        if hasattr(self, 'aktif_plan_ekrani'):
            self.aktif_plan_ekrani.yeni_plan_ekle()

    def yeni_kullanici_formunu_ac(self):
        from k_personel_ekranlari import KullaniciOlusturFormu
        
        self.kullanici_formu = KullaniciOlusturFormu(api_url=self.api_url, token=self.token, ebeveyn=self)
        # Kayıt başarılıysa pencerenin kapanma biçiminden bağımsız olarak listeyi yenile.
        self.kullanici_formu.exec()
        if self.kullanici_formu.olusturulan_kullanici is not None:
            ekran = getattr(self, "aktif_personel_ekrani", None)
            if ekran is not None:
                ekran.verileri_cek()
    
    def faaliyet_tablosunu_guncelle(self):
        if not hasattr(self, 'tablo_faaliyetler'):
            return

        self.tablo_faaliyetler.setRowCount(0)

        try:
            import requests
            from PySide6.QtWidgets import QTableWidgetItem, QMessageBox

            headers = {"Authorization": f"Bearer {self.token}"}
            res = oturum_kontrollu_istek("GET", f"{self.api_url}/api/faaliyet-kayitlari", headers=headers)
            if oturum_hatasi_mi(res):
                return

            if res.status_code == 200:
                kayitlar = res.json()
                self.tablo_faaliyetler.setRowCount(len(kayitlar))

                for satir_no, kayit in enumerate(kayitlar):
                    self.tablo_faaliyetler.setItem(satir_no, 0, QTableWidgetItem(str(kayit.get("id", ""))))
                    self.tablo_faaliyetler.setItem(satir_no, 1, QTableWidgetItem(str(kayit.get("ad_soyad", ""))))
                    self.tablo_faaliyetler.setItem(satir_no, 2, QTableWidgetItem(str(kayit.get("ogrenci_no", ""))))
                    self.tablo_faaliyetler.setItem(satir_no, 3, QTableWidgetItem(str(kayit.get("faaliyet_adi", ""))))
                    self.tablo_faaliyetler.setItem(satir_no, 4, QTableWidgetItem(str(kayit.get("miktar", ""))))
                    self.tablo_faaliyetler.setItem(satir_no, 5, QTableWidgetItem(f"{kayit.get('toplam_puan', '0')} Puan"))
                    self.tablo_faaliyetler.setItem(satir_no, 6, QTableWidgetItem(str(kayit.get("tarih", ""))))

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Arayüz Hatası", f"Tablo çizilirken hata oluştu:\n{str(e)}")

    def yeni_faaliyet_ekrani_ac(self):
        from faaliyet_dialog import FaaliyetEkleDialog
        dialog = FaaliyetEkleDialog(
            self.api_url, self.token, self,
            birim_yonetebilir=izin_var(self.aktif_rol, "Faaliyet birimlerini yönetme"),
        )
        if dialog.exec():
            # Kullanıcı formu doldurup kaydete basınca tablo şak diye yenilenecek
            self.faaliyet_tablosunu_guncelle()

    def faaliyet_duzenle_tetikle(self):
        # 1. Buton bağlandıysa terminale bunu yazdıracak:
        print("--- DÜZENLE BUTONUNA BASILDI! ---")

        # 2. Tabloyu bulamazsa sessizce kapanmayacak, bize bağıracak:
        if not hasattr(self, 'tablo_faaliyetler'):
            print("HATA: 'tablo_faaliyetler' adında bir tablo yok! Acaba tablonun adı başka bir şey mi?")
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Hata", "Tablo bulunamadı! Terminale bak.")
            return

        secili_satirlar = self.tablo_faaliyetler.selectionModel().selectedRows()
        if not secili_satirlar:
            from PySide6.QtWidgets import QMessageBox
            uyari = QMessageBox(self)
            uyari.setWindowTitle("Uyarı")
            uyari.setText("Lütfen düzenlemek istediğiniz faaliyeti tablodan seçin!")
            uyari.setIcon(QMessageBox.Warning)
            uyari.setStyleSheet("""
                QMessageBox { background-color: #F8F9FA; }
                QLabel { color: #2C3E50; font-size: 13px; font-weight: bold; }
                QPushButton { background-color: #2980B9; color: white; padding: 6px 15px; border-radius: 4px; }
                QPushButton:hover { background-color: #3498DB; }
            """)
            uyari.setStandardButtons(QMessageBox.Ok)
            uyari.exec()
            return

        satir = secili_satirlar[0].row()
        takip_id = self.tablo_faaliyetler.item(satir, 0).text()
        print(f"Seçilen satırın ID'si: {takip_id}") # ID'yi yakaladık mı görelim

        # Miktar sütununda hem rakam hem birim var, onları parçalıyoruz
        miktar_hücresi = self.tablo_faaliyetler.item(satir, 4).text().split(" ")
        miktar_rakam = miktar_hücresi[0]
        birim_adi = miktar_hücresi[1] if len(miktar_hücresi) > 1 else ""

        mevcut_veri = {
            "takip_id": takip_id,
            "ogrenci_adi": self.tablo_faaliyetler.item(satir, 1).text(),
            "faaliyet_adi": self.tablo_faaliyetler.item(satir, 3).text(),
            "miktar": miktar_rakam,
            "birim_adi": birim_adi
        }

        from faaliyet_dialog import FaaliyetEkleDialog
        dialog = FaaliyetEkleDialog(self.api_url, self.token, self, mevcut_veri=mevcut_veri)
        if dialog.exec():
            self.faaliyet_tablosunu_guncelle()

    def faaliyet_sil_tetikle(self):
        if not hasattr(self, 'tablo_faaliyetler'):
            return

        secili_satirlar = self.tablo_faaliyetler.selectionModel().selectedRows()

        # 1. SATIR SEÇİLMEMİŞSE ÇIKACAK ŞIK UYARI
        if not secili_satirlar:
            from PySide6.QtWidgets import QMessageBox
            uyari = QMessageBox(self)
            uyari.setWindowTitle("Uyarı")
            uyari.setText("Lütfen silmek istediğiniz faaliyeti tablodan seçin!")
            uyari.setIcon(QMessageBox.Warning)
            uyari.setStyleSheet("""
                QMessageBox { background-color: #F8F9FA; }
                QLabel { color: #2C3E50; font-size: 13px; font-weight: bold; }
                QPushButton { background-color: #2980B9; color: white; padding: 6px 15px; border-radius: 4px; }
                QPushButton:hover { background-color: #3498DB; }
            """)
            uyari.setStandardButtons(QMessageBox.Ok)
            uyari.exec()
            return

        satir = secili_satirlar[0].row()
        takip_id = str(self.tablo_faaliyetler.item(satir, 0).text()).strip()
        ogrenci_adi = self.tablo_faaliyetler.item(satir, 1).text()
        faaliyet_adi = self.tablo_faaliyetler.item(satir, 3).text()

        # 2. EMİN MİSİN SORUSUNUN ŞIK VERSİYONU
        from PySide6.QtWidgets import QMessageBox
        soru = QMessageBox(self)
        soru.setWindowTitle("Kayıt Silme Onayı")
        soru.setText(f"DİKKAT: {ogrenci_adi} adlı öğrencinin '{faaliyet_adi}' kaydını kalıcı olarak silmek istediğinize emin misiniz?")
        soru.setIcon(QMessageBox.Question)
        soru.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        soru.setDefaultButton(QMessageBox.No)
        # Soru kutusuna özel, Yes (Evet) butonunu tehlike rengi yapalım
        soru.setStyleSheet("""
            QMessageBox { background-color: #F8F9FA; }
            QLabel { color: #2C3E50; font-size: 13px; font-weight: bold; }
            QPushButton { background-color: #BDC3C7; color: black; padding: 6px 15px; border-radius: 4px; }
            QPushButton:hover { background-color: #95A5A6; }
            QPushButton[text="Evet"] { background-color: #E74C3C; color: white; }
            QPushButton[text="Evet"]:hover { background-color: #C0392B; }
        """)

        cevap = soru.exec()

        if cevap == QMessageBox.Yes:
            import requests
            headers = {"Authorization": f"Bearer {self.token}"}
            hedef_url = f"{self.api_url.rstrip('/')}/api/faaliyet-kayitlari/{takip_id}"

            try:
                res = oturum_kontrollu_istek("DELETE", hedef_url, headers=headers)
                if oturum_hatasi_mi(res):
                    return

                if res.status_code == 200:
                    bilgi = QMessageBox(self)
                    bilgi.setWindowTitle("Başarılı")
                    bilgi.setText("Kayıt veritabanından kalıcı olarak silindi!")
                    bilgi.setIcon(QMessageBox.Information)
                    bilgi.setStyleSheet("""
                        QMessageBox { background-color: #F8F9FA; }
                        QLabel { color: #2C3E50; font-size: 13px; font-weight: bold; }
                        QPushButton { background-color: #27AE60; color: white; padding: 6px 15px; border-radius: 4px; }
                        QPushButton:hover { background-color: #2ECC71; }
                    """)
                    bilgi.setStandardButtons(QMessageBox.Ok)
                    bilgi.exec()

                    self.faaliyet_tablosunu_guncelle() # Tabloyu yenile ki kayıt ekrandan kaybolsun
                else:
                    try:
                        hata_detayi = res.json().get("detail", res.text)
                    except:
                        hata_detayi = res.text
                    QMessageBox.critical(self, "Hata", f"Silme işlemi başarısız oldu.\nSunucu Cevabı: {hata_detayi}")
            except Exception as e:
                QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")

    def faaliyet_turleri_ekrani_ac(self):
        from faaliyet_turleri_dialog import FaaliyetTurleriDialog

        dialog = FaaliyetTurleriDialog(
            self.api_url,
            self.token,
            self
        )
        dialog.exec()

        # Faaliyet türü veya puanı değişmiş olabilir.
        # Pencere kapatılınca ana faaliyet tablosunu yenile.
        if hasattr(self, "tablo_faaliyetler"):
            self.faaliyet_tablosunu_guncelle()

    def faaliyet_birimleri_ekrani_ac(self):
        # Az önce yazdığımız arayüz dosyasını çağırıyoruz
        from birim_dialog import BirimYonetimDialog
        dialog = BirimYonetimDialog(self.api_url, self.token, self)
        dialog.exec()

    def rol_olustur_ac(self):
        dialog = RolOlusturDialog(self.api_url, self.token, self)
        if dialog.exec():
            # Yeni rol eklendi, matris sayfasını yenile
            if hasattr(self, 'rol_izin_sayfasi'):
                self.rol_izin_sayfasi.verileri_yukle()
    
    def rol_duzenle_diyalog_ac(self):
        # Sayfanın ve verilerin yüklü olup olmadığını kontrol et
        if not hasattr(self, 'rol_izin_sayfasi') or not hasattr(self.rol_izin_sayfasi, 'roller'):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Uyarı", "Lütfen önce 'Rol & İzin Yönetimi' sekmesini açın.")
            return
            
        from rol_izin_diyaloglari import RolDuzenleDialog
        dialog = RolDuzenleDialog(
            self.api_url, 
            self.token, 
            self.rol_izin_sayfasi.roller, 
            self.rol_izin_sayfasi.rol_izin_map, 
            self
        )
        
        if dialog.exec():
            self.rol_izin_sayfasi.verileri_yukle()

    def izin_duzenle_tetikle(self):
        izin_id = self.rol_izin_sayfasi.secili_izin_id()
        if not izin_id:
            QMessageBox.warning(self, "Uyarı", "Lütfen düzenlemek istediğiniz izni listeden seçin.")
            return
            
        dialog = IzinDuzenleDialog(
            api_url=self.api_url, 
            token=self.token, 
            izin_id=izin_id, 
            roller=self.rol_izin_sayfasi.roller, 
            matris_verisi=self.rol_izin_sayfasi.matris_verisi, 
            ebeveyn=self
        )
        if dialog.exec():
            self.rol_izin_sayfasi.verileri_yukle()

    def rolleri_getir(self):
        if not hasattr(self, 'rol_tablosu'):
            return

        import requests
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtCore import Qt

        self.rol_tablosu.setRowCount(0) # Önce tabloyu temizle
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            # Backend API endpoint'inin /api/roller olduğunu varsayıyoruz
            cevap = requests.get(f"{self.api_url}/api/roller", headers=headers, timeout=5)
            if cevap.status_code == 200:
                roller = cevap.json()
                self.rol_tablosu.setRowCount(len(roller))

                for satir, rol_verisi in enumerate(roller):
                    item_id = QTableWidgetItem(str(rol_verisi.get("rol_id", "")))
                    item_ad = QTableWidgetItem(str(rol_verisi.get("rol_adi", "")))

                    item_id.setTextAlignment(Qt.AlignCenter)
                    item_ad.setTextAlignment(Qt.AlignCenter)

                    self.rol_tablosu.setItem(satir, 0, item_id)
                    self.rol_tablosu.setItem(satir, 1, item_ad)
        except Exception as e:
            print("Rol verileri çekilirken hata oluştu:", e)


if __name__ == "__main__":
    from qt_dil import turkce_ceviriyi_yukle
    app = QApplication(sys.argv)
    if not turkce_ceviriyi_yukle(app):
        print("Uyarı: Qt Türkçe çevirisi yüklenemedi.")
    rol = sys.argv[1] if len(sys.argv) > 1 else "admin"
    pencere = AnaPencere(aktif_rol=rol, rol_onizleme=True)
    pencere.showMaximized()
    sys.exit(app.exec())