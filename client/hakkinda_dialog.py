"""TKYS - Hakkında / Yardım penceresi.

Destek ararken hangi sürümde olunduğu bilinmiyordu. Bu pencere istemci ve sunucu sürümünü, veritabanı şema sürümünü ve
giriş yapan kullanıcıyı gösterir; "Destek bilgisini kopyala" ile hepsi tek metin olarak panoya alınır. Ayrıca klavye
kısayolları ve kısa kullanım ipuçları burada listelenir. Parola, oturum anahtarı ya da kişisel veri içermez.
"""
import platform
import sys
from datetime import datetime

import PySide6
import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QAbstractItemView,
)

from client.api_yoneticisi import oturum_kontrollu_istek
from client.surum import SURUM, UYGULAMA_ADI

KISAYOLLAR = [
    ("Ctrl + N", "Açık sayfadaki ilk \"＋ Yeni ...\" işlemini başlatır (örn. Yeni Randevu, Öğrenci Ekle, Cihaz Ekle)"),
    ("Ctrl + F", "Açık sayfadaki arama kutusuna gider"),
    ("F5", "Açık sayfayı yeniler (güncel veriyi sunucudan alır)"),
    ("F1", "Bu Hakkında / Yardım penceresini açar"),
    ("Esc", "Açık pencere ya da formu kapatır"),
    ("Başlığa tıklama", "Tablolarda sütuna göre sıralar; ikinci tıklama ters çevirir"),
    ("Çift tıklama", "Listede kaydı düzenlemek için açar (yetkiniz varsa)"),
]

IPUCLARI = [
    "Listelerde \"Excel'e Aktar\" düğmesi, ekranda o an görünen kayıtları dosyaya yazar. Önce arama ya da süzgeç uygulayabilirsiniz.",
    "Randevu listesinde \"Tüm tarihler\" en yeni 2000 randevuyu getirir. Daha eskileri görmek için dönem seçin.",
    "Danışan listelerinde ad/soyad tutulmaz; yalnızca danışan kodu görünür.",
    "Bir şey beklediğiniz gibi görünmüyorsa önce F5 ile yenileyin.",
    "Sorun bildirirken \"Hakkında\" sekmesindeki \"Destek bilgisini kopyala\" düğmesiyle sürüm bilgisini ekleyin.",
]


def destek_metni(istemci_surumu, sunucu_bilgisi, kullanici, rol, api_url, simdi=None):
    """Destek ekibine gönderilecek düz metin. Oturum anahtarı ve parola içermez."""
    sunucu_bilgisi = sunucu_bilgisi or {}
    satirlar = [
        f"{UYGULAMA_ADI} destek bilgisi — {(simdi or datetime.now()):%d.%m.%Y %H:%M}",
        f"İstemci sürümü: {istemci_surumu}",
        f"Sunucu sürümü: {sunucu_bilgisi.get('surum') or 'alınamadı'}",
        f"Veritabanı şema sürümü: {sunucu_bilgisi.get('sema_surumu') or 'alınamadı'}",
        f"Kullanıcı / rol: {kullanici or '—'} / {rol or '—'}",
        f"Sunucu adresi: {api_url or '—'}",
        f"Python {platform.python_version()} · PySide6 {PySide6.__version__} · {platform.system()} {platform.release()}",
    ]
    return "\n".join(satirlar)


class HakkindaDialog(QDialog):
    def __init__(self, api_url, token, kullanici="", rol="", parent=None, baslangic_sekmesi=0):
        super().__init__(parent)
        self.api_url = (api_url or "").rstrip("/")
        self.token = token
        self.kullanici = kullanici
        self.rol = rol
        self.sunucu_bilgisi = self._sunucu_bilgisini_al()
        self.setWindowTitle(f"{UYGULAMA_ADI} — Hakkında / Yardım")
        self.setMinimumSize(620, 460)

        kok = QVBoxLayout(self)
        self.sekmeler = QTabWidget()
        self.sekmeler.addTab(self._hakkinda_sekmesi(), "Hakkında")
        self.sekmeler.addTab(self._kisayollar_sekmesi(), "Kısayollar")
        self.sekmeler.addTab(self._yardim_sekmesi(), "Yardım")
        self.sekmeler.setCurrentIndex(baslangic_sekmesi)
        kok.addWidget(self.sekmeler, 1)

        alt = QHBoxLayout()
        alt.addStretch()
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        alt.addWidget(kapat)
        kok.addLayout(alt)

    def _sunucu_bilgisini_al(self):
        if not self.api_url:
            return None
        try:
            cevap = oturum_kontrollu_istek("GET", f"{self.api_url}/api/surum", headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            if cevap.status_code == 200:
                return cevap.json()
        except (requests.RequestException, ValueError):
            pass
        return None

    def _hakkinda_sekmesi(self):
        sayfa = QWidget()
        duzen = QVBoxLayout(sayfa)
        baslik = QLabel(f"{UYGULAMA_ADI} — Terapi Kaynak Yönetim Sistemi")
        baslik.setStyleSheet("font-size: 18px; font-weight: 800; color: #0A1F5C;")
        duzen.addWidget(baslik)

        izgara = QGridLayout()
        izgara.setHorizontalSpacing(18)
        izgara.setVerticalSpacing(8)
        sunucu = self.sunucu_bilgisi or {}
        satirlar = [
            ("İstemci sürümü", SURUM),
            ("Sunucu sürümü", sunucu.get("surum") or "alınamadı"),
            ("Veritabanı şema sürümü", sunucu.get("sema_surumu") or "alınamadı"),
            ("Kullanıcı / rol", f"{self.kullanici or '—'} / {self.rol or '—'}"),
            ("Sunucu adresi", self.api_url or "—"),
        ]
        for sira, (ad, deger) in enumerate(satirlar):
            etiket = QLabel(ad + ":")
            etiket.setStyleSheet("font-weight: 700; color: #31517D;")
            degeri = QLabel(str(deger))
            degeri.setTextInteractionFlags(Qt.TextSelectableByMouse)
            izgara.addWidget(etiket, sira, 0)
            izgara.addWidget(degeri, sira, 1)
        izgara.setColumnStretch(1, 1)
        duzen.addLayout(izgara)

        self.surum_uyarisi = QLabel("")
        self.surum_uyarisi.setWordWrap(True)
        self.surum_uyarisi.setStyleSheet("color: #854D0E; background: #FEF3C7; border-radius: 8px; padding: 8px;")
        if sunucu.get("surum") and sunucu["surum"] != SURUM:
            self.surum_uyarisi.setText("İstemci ve sunucu sürümleri farklı. İstemciyi güncelleyin.")
        else:
            self.surum_uyarisi.hide()
        duzen.addWidget(self.surum_uyarisi)

        self.kopyala_btn = QPushButton("Destek bilgisini kopyala")
        self.kopyala_btn.setCursor(Qt.PointingHandCursor)
        self.kopyala_btn.clicked.connect(self.destek_bilgisini_kopyala)
        duzen.addWidget(self.kopyala_btn, alignment=Qt.AlignLeft)
        duzen.addStretch()
        return sayfa

    def destek_bilgisini_kopyala(self):
        QApplication.clipboard().setText(destek_metni(SURUM, self.sunucu_bilgisi, self.kullanici, self.rol, self.api_url))
        self.kopyala_btn.setText("Kopyalandı ✓")

    def _kisayollar_sekmesi(self):
        tablo = QTableWidget(len(KISAYOLLAR), 2)
        tablo.setHorizontalHeaderLabels(["TUŞ", "NE YAPAR"])
        tablo.verticalHeader().setVisible(False)
        tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tablo.setSelectionMode(QAbstractItemView.NoSelection)
        tablo.setWordWrap(True)
        tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for satir, (tus, aciklama) in enumerate(KISAYOLLAR):
            tablo.setItem(satir, 0, QTableWidgetItem(tus))
            tablo.setItem(satir, 1, QTableWidgetItem(aciklama))
        tablo.resizeRowsToContents()
        self.kisayol_tablosu = tablo
        return tablo

    def _yardim_sekmesi(self):
        sayfa = QWidget()
        duzen = QVBoxLayout(sayfa)
        for ipucu in IPUCLARI:
            etiket = QLabel("•  " + ipucu)
            etiket.setWordWrap(True)
            duzen.addWidget(etiket)
        duzen.addStretch()
        return sayfa
