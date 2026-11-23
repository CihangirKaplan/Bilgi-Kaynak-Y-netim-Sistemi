"""TKYS - Hakkında / Yardım penceresi.

Destek ararken hangi sürümde olunduğu bilinmiyordu. Bu pencere istemci ve sunucu sürümünü, veritabanı şema sürümünü ve
giriş yapan kullanıcıyı gösterir; "Destek bilgisini kopyala" ile hepsi tek metin olarak panoya alınır. Ayrıca klavye
kısayolları ve kısa kullanım ipuçları burada listelenir. Parola, oturum anahtarı ya da kişisel veri içermez.
"""
import platform
from datetime import datetime
from pathlib import Path

import PySide6
import requests
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTabWidget, QTableWidget,
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

YARDIM_BOLUMLERI = [
    ("Başlarken", [
        "Soldaki menüden bir sayfa seçin. Menüde yalnızca rolünüzün yetkili olduğu sayfalar görünür.",
        "Üstteki zil simgesi bekleyen bildirimleri (geciken bakım, açık arıza vb.) gösterir; bildirime tıklayınca ilgili sayfaya gidersiniz.",
        "Bir şey beklediğiniz gibi görünmüyorsa önce F5 ile sayfayı yenileyin.",
    ]),
    ("Listeler ve arama", [
        "Tablolarda bir sütun başlığına tıklayarak sıralayabilirsiniz; ikinci tıklama sırayı tersine çevirir.",
        "Arama kutusu ve süzgeçler, listede o an görünen kayıtları daraltır. Ctrl + F ile arama kutusuna geçebilirsiniz.",
        "Randevu listesinde \"Tüm tarihler\" en yeni 2000 randevuyu getirir; daha eskilerini görmek için bir dönem seçin.",
    ]),
    ("Excel'e aktarma", [
        "\"Excel'e Aktar\" düğmesi, ekranda o an görünen kayıtları dosyaya yazar. Önce arama ya da süzgeç uygulayabilirsiniz.",
        "Aktarılan dosyaların paylaşımında dikkatli olun; her aktarım denetim kaydına işlenir.",
    ]),
    ("Kişisel veriler", [
        "Danışanlar adla değil danışan koduyla kaydedilir. Ad, telefon ya da tanı bilgisini sisteme yazmayın.",
    ]),
    ("Sorun bildirme", [
        "Sorun bildirirken \"Hakkında\" sekmesindeki \"Destek bilgisini kopyala\" düğmesine basıp metni mesajınıza yapıştırın.",
        "Bu metin yalnızca sürüm bilgisini içerir; parola ve oturum anahtarı içermez.",
    ]),
]
# Eski ad (geriye dönük uyumluluk): düz ipucu listesi
IPUCLARI = [madde for _, maddeler in YARDIM_BOLUMLERI for madde in maddeler]

# Pencere açık/koyu işletim sistemi temasından bağımsız, her zaman okunur görünsün diye tüm renkler burada belirtilir.
STIL = """
QDialog { background: #F3F6FC; }
QLabel { color: #243653; background: transparent; }
QTabWidget::pane { border: 1px solid #D6E2F3; border-radius: 10px; background: white; top: -1px; }
QTabBar::tab { background: #E3ECFA; color: #4A5E80; padding: 10px 22px; margin-right: 4px; font-weight: 700;
               border-top-left-radius: 8px; border-top-right-radius: 8px; }
QTabBar::tab:selected { background: white; color: #0A1F5C; border-bottom: 3px solid #285CE6; }
QTabBar::tab:hover { color: #285CE6; }
QTableWidget { background: white; color: #243653; gridline-color: #E8EEF8; border: none; }
QTableWidget::item { padding: 8px 12px; }
QHeaderView::section { background: #E8F0FF; color: #16294B; font-weight: 700; padding: 8px 12px; border: none;
                       border-bottom: 1px solid #D6E2F3; }
QPushButton { background: #285CE6; color: white; border: none; border-radius: 8px; padding: 9px 20px; font-weight: 700; }
QPushButton:hover { background: #1E4BC5; }
QPushButton#ikincil { background: #E3ECFA; color: #16294B; }
QPushButton#ikincil:hover { background: #D3E1F7; }
QScrollArea { border: none; background: white; }
"""


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
        self.setMinimumSize(680, 560)
        self.setStyleSheet(STIL)

        kok = QVBoxLayout(self)
        kok.setContentsMargins(18, 18, 18, 16)
        kok.setSpacing(14)
        kok.addWidget(self._ust_baslik())

        self.sekmeler = QTabWidget()
        self.sekmeler.addTab(self._hakkinda_sekmesi(), "Hakkında")
        self.sekmeler.addTab(self._kisayollar_sekmesi(), "Kısayollar")
        self.sekmeler.addTab(self._yardim_sekmesi(), "Yardım")
        self.sekmeler.setCurrentIndex(baslangic_sekmesi)
        kok.addWidget(self.sekmeler, 1)

        alt = QHBoxLayout()
        alt.addStretch()
        kapat = QPushButton("Kapat")
        kapat.setObjectName("ikincil")
        kapat.setCursor(Qt.PointingHandCursor)
        kapat.clicked.connect(self.accept)
        alt.addWidget(kapat)
        kok.addLayout(alt)

    def _ust_baslik(self):
        """Uygulama adı, kurum ve sürüm: lacivert şerit."""
        kart = QFrame()
        kart.setObjectName("ustBaslik")
        kart.setStyleSheet(
            "QFrame#ustBaslik { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #082B66, stop:1 #285CE6); border-radius: 12px; }"
            "QFrame#ustBaslik QLabel { background: transparent; }"
        )
        yatay = QHBoxLayout(kart)
        yatay.setContentsMargins(20, 16, 20, 16)
        yatay.setSpacing(16)

        logo_yolu = Path(__file__).resolve().parent / "assets" / "tkys_travma_logo.png"
        if logo_yolu.is_file():
            harita = QPixmap(str(logo_yolu))
            if not harita.isNull():
                logo = QLabel()
                logo.setPixmap(harita.scaledToHeight(64, Qt.SmoothTransformation))
                yatay.addWidget(logo)

        metin = QVBoxLayout()
        metin.setSpacing(2)
        self.baslik_etiketi = QLabel("Travma Kaynak Yönetim Sistemi")
        self.baslik_etiketi.setStyleSheet("color: white; font-size: 21px; font-weight: 800;")
        alt_baslik = QLabel(f"{UYGULAMA_ADI}  ·  Travma Uygulama ve Araştırma Merkezi")
        alt_baslik.setStyleSheet("color: #DCE9FF; font-size: 12px; font-weight: 600;")
        metin.addWidget(self.baslik_etiketi)
        metin.addWidget(alt_baslik)
        yatay.addLayout(metin, 1)

        rozet = QLabel(f"Sürüm {SURUM}")
        rozet.setStyleSheet("color: white; background: rgba(255,255,255,0.18); border-radius: 12px; padding: 5px 14px; font-weight: 700;")
        yatay.addWidget(rozet, alignment=Qt.AlignTop)
        return kart

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
        duzen.setContentsMargins(22, 20, 22, 20)
        duzen.setSpacing(12)

        sunucu = self.sunucu_bilgisi or {}
        satirlar = [
            ("İstemci sürümü", SURUM),
            ("Sunucu sürümü", sunucu.get("surum") or "alınamadı"),
            ("Veritabanı şema sürümü", sunucu.get("sema_surumu") or "alınamadı"),
            ("Kullanıcı / rol", f"{self.kullanici or '—'} / {self.rol or '—'}"),
            ("Sunucu adresi", self.api_url or "—"),
        ]
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(24)
        izgara.setVerticalSpacing(0)
        for sira, (ad, deger) in enumerate(satirlar):
            etiket = QLabel(ad)
            etiket.setStyleSheet("color: #5B6B88; font-size: 13px; font-weight: 600; padding: 10px 0;")
            degeri = QLabel(str(deger))
            degeri.setStyleSheet("color: #0A1F5C; font-size: 14px; font-weight: 700; padding: 10px 0;")
            degeri.setTextInteractionFlags(Qt.TextSelectableByMouse)
            izgara.addWidget(etiket, sira, 0)
            izgara.addWidget(degeri, sira, 1)
            cizgi = QFrame()
            cizgi.setFixedHeight(1)
            cizgi.setStyleSheet("background: #E8EEF8;")
            izgara.addWidget(cizgi, sira, 0, 1, 2, alignment=Qt.AlignBottom)
        izgara.setColumnStretch(1, 1)
        duzen.addLayout(izgara)

        self.surum_uyarisi = QLabel("")
        self.surum_uyarisi.setWordWrap(True)
        self.surum_uyarisi.setStyleSheet("color: #854D0E; background: #FEF3C7; border-radius: 8px; padding: 10px 12px; font-weight: 600;")
        self.surum_durumu = QLabel("")
        self.surum_durumu.setStyleSheet("color: #166534; background: #DCFCE7; border-radius: 8px; padding: 10px 12px; font-weight: 600;")
        if sunucu.get("surum") and sunucu["surum"] != SURUM:
            self.surum_uyarisi.setText("İstemci ve sunucu sürümleri farklı. İstemciyi güncelleyin.")
            self.surum_durumu.hide()
        elif sunucu.get("surum"):
            self.surum_uyarisi.hide()
            self.surum_durumu.setText("✓  İstemci ve sunucu sürümleri uyumlu.")
        else:
            self.surum_uyarisi.hide()
            self.surum_durumu.hide()
        duzen.addWidget(self.surum_uyarisi)
        duzen.addWidget(self.surum_durumu)

        duzen.addStretch()
        destek = QLabel("Bir sorunla karşılaşırsanız aşağıdaki düğmeyle sürüm bilgisini kopyalayıp mesajınıza ekleyin. "
                        "Kopyalanan metin parola ya da oturum anahtarı içermez.")
        destek.setWordWrap(True)
        destek.setStyleSheet("color: #5B6B88; font-size: 12px;")
        duzen.addWidget(destek)
        self.kopyala_btn = QPushButton("Destek bilgisini kopyala")
        self.kopyala_btn.setCursor(Qt.PointingHandCursor)
        self.kopyala_btn.clicked.connect(self.destek_bilgisini_kopyala)
        duzen.addWidget(self.kopyala_btn, alignment=Qt.AlignLeft)
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
        tablo.setShowGrid(False)
        tablo.setFocusPolicy(Qt.NoFocus)
        tablo.setWordWrap(True)
        tablo.setAlternatingRowColors(True)
        tablo.setStyleSheet("QTableWidget { alternate-background-color: #F6F9FE; }")
        tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        tablo.horizontalHeader().setStretchLastSection(True)
        for satir, (tus, aciklama) in enumerate(KISAYOLLAR):
            tus_hucresi = QTableWidgetItem(tus)
            yazi = tus_hucresi.font()
            yazi.setBold(True)
            tus_hucresi.setFont(yazi)
            tus_hucresi.setForeground(QColor("#0A1F5C"))
            tablo.setItem(satir, 0, tus_hucresi)
            tablo.setItem(satir, 1, QTableWidgetItem(aciklama))
        tablo.resizeRowsToContents()
        self.kisayol_tablosu = tablo
        return tablo

    def _yardim_sekmesi(self):
        kaydirma = QScrollArea()
        kaydirma.setWidgetResizable(True)
        kaydirma.setFrameShape(QFrame.NoFrame)
        sayfa = QWidget()
        sayfa.setStyleSheet("background: white;")
        duzen = QVBoxLayout(sayfa)
        duzen.setContentsMargins(22, 18, 22, 18)
        duzen.setSpacing(6)
        for baslik, maddeler in YARDIM_BOLUMLERI:
            b = QLabel(baslik)
            b.setStyleSheet("color: #0A1F5C; font-size: 14px; font-weight: 800; padding-top: 10px;")
            duzen.addWidget(b)
            for madde in maddeler:
                etiket = QLabel("•  " + madde)
                etiket.setWordWrap(True)
                etiket.setStyleSheet("color: #314361; font-size: 13px; padding-left: 4px;")
                duzen.addWidget(etiket)
        duzen.addStretch()
        kaydirma.setWidget(sayfa)
        return kaydirma
