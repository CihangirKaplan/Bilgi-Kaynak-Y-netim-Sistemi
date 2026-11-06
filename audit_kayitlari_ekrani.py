from datetime import datetime
import requests
from api_yoneticisi import oturum_kontrollu_istek, oturum_hatasi_mi

from PySide6.QtCore import Qt, QDate, QRectF
from PySide6.QtGui import QColor, QPainter, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QComboBox,
    QCheckBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFrame, QDialog,
    QMenu, QWidgetAction,
    QStyledItemDelegate, QGraphicsDropShadowEffect, QStyle
)



OLAY_ADLARI = {
    "PASSWORD_RESET": "Parola Sıfırlama",
    "LOGIN": "Giriş Başarılı",
    "LOGIN_FAILED": "Başarısız Giriş",
    "CREATE": "Oluşturma",
    "UPDATE": "Güncelleme",
    "CANCEL": "İptal",
    "ROLE_CHANGE": "Rol Değişikliği",
    "DEVICE_STATUS_CHANGE": "Cihaz Durum Değişikliği",
}

HEDEF_TABLO_ADLARI = {
    "kullanicilar": "Kullanıcı",
    "personel": "Personel",
    "ogrenciler": "Öğrenci",
    "roller": "Rol",
    "izinler": "İzin",
    "randevular": "Randevu",
    "odalar": "Oda",
    "cihazlar": "Cihaz",
    "cihaz_rezervasyonlari": "Cihaz Rezervasyonu",
    "cihaz_bakim": "Cihaz Bakımı",
    "cihaz_ariza": "Cihaz Arızası",
    "cihaz_kalibrasyon": "Cihaz Kalibrasyonu",
    "danisan_kodlari": "Danışan Kodu",
    "danisma_masasi_oturumlari": "Danışma Oturumu",
    "ogrenci_faaliyet_takip": "Öğrenci Faaliyeti",
    "projeler": "Proje",
    "deneyler": "Deney",
}

OLAY_RENKLERI = {
    "LOGIN": ("#17634F", "#E8F6EF"),
    "LOGIN_FAILED": ("#9B3048", "#FCEBF0"),
    "CREATE": ("#2457A2", "#E9F1FF"),
    "UPDATE": ("#96601B", "#FFF2DF"),
    "CANCEL": ("#9B3048", "#FCEBF0"),
    "ROLE_CHANGE": ("#62499E", "#F0EBFC"),
    "DEVICE_STATUS_CHANGE": ("#285F88", "#E8F2FB"),
}


def kart_golgesi(widget):
    efekt = QGraphicsDropShadowEffect(widget)
    efekt.setBlurRadius(20)
    efekt.setOffset(0, 3)
    efekt.setColor(QColor(13, 37, 87, 18))
    widget.setGraphicsEffect(efekt)


class IslemEtiketiDelegate(QStyledItemDelegate):
    """İşlem türünü, satır seçilse bile rengini koruyan rozet olarak çizer."""

    def paint(self, painter, option, index):
        olay_kodu = index.data(Qt.UserRole)
        etiket = str(index.data(Qt.DisplayRole) or "")
        yazi_rengi, zemin_rengi = OLAY_RENKLERI.get(
            olay_kodu, ("#334155", "#EEF2F7")
        )

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        secili = bool(option.state & QStyle.State_Selected)
        if secili:
            satir_zemini = "#E6EEFC"
        else:
            satir_zemini = (
                "#FFFFFF" if index.row() % 2 == 0 else "#F7F9FD"
            )

        painter.fillRect(option.rect, QColor(satir_zemini))

        yazi_tipi = option.font
        yazi_tipi.setBold(True)
        painter.setFont(yazi_tipi)

        olculer = QFontMetrics(yazi_tipi)
        etiket_genisligi = min(
            olculer.horizontalAdvance(etiket) + 28,
            max(10, option.rect.width() - 20)
        )

        rozet = QRectF(
            option.rect.x() + 10,
            option.rect.y() + (option.rect.height() - 29) / 2,
            etiket_genisligi,
            29
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(zemin_rengi))
        painter.drawRoundedRect(rozet, 9, 9)

        painter.setPen(QColor(yazi_rengi))
        painter.drawText(rozet, Qt.AlignCenter, etiket)
        painter.restore()

    def sizeHint(self, option, index):
        boyut = super().sizeHint(option, index)
        boyut.setHeight(max(boyut.height(), 42))
        return boyut



class CokluIslemSecici(QPushButton):
    def __init__(self, parent=None):
        super().__init__("Tüm İşlemler", parent)

        self.kutular = {}

        self.setMinimumHeight(40)
        self.setStyleSheet("""
            QPushButton {
                background: white;
                color: #0A1F5C;
                border: 1px solid #D1DDED;
                border-radius: 8px;
                text-align: left;
                padding: 7px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #F5F8FF;
                border: 1px solid #95B5E3;
            }
        """)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: white;
                border: 1px solid #DDE6F3;
                border-radius: 8px;
                padding: 6px;
            }
        """)

        for kod, ad in OLAY_ADLARI.items():
            kutu = QCheckBox(ad)
            kutu.setMinimumHeight(32)

            kapsayici = QWidget(menu)
            duzen = QHBoxLayout(kapsayici)
            duzen.setContentsMargins(12, 2, 14, 2)
            duzen.addWidget(kutu)

            eylem = QWidgetAction(menu)
            eylem.setDefaultWidget(kapsayici)
            menu.addAction(eylem)

            self.kutular[kod] = kutu
            kutu.toggled.connect(self.yaziyi_guncelle)

        self.setMenu(menu)

    def secilenler(self):
        return [
            kod for kod, kutu in self.kutular.items()
            if kutu.isChecked()
        ]

    def yaziyi_guncelle(self, *_):
        secilen = self.secilenler()

        if not secilen:
            self.setText("Tüm İşlemler")
        elif len(secilen) == 1:
            self.setText(
                OLAY_ADLARI[secilen[0]]
            )
        else:
            self.setText(
                f"{len(secilen)} işlem seçildi"
            )

    def temizle(self):
        for kutu in self.kutular.values():
            kutu.setChecked(False)
        self.yaziyi_guncelle()


class AuditKayitlariEkrani(QWidget):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self.limit = 50
        self.offset = 0
        self.toplam = 0

        self.arayuzu_olustur()
        self.kayitlari_getir()

    def arayuzu_olustur(self):
        self.setStyleSheet("""
            AuditKayitlariEkrani {
                background: transparent;
                color: #173263;
            }

            QFrame#ozetKart, QFrame#tabloKart {
                background: #FFFFFF;
                border: 1px solid #E3EAF5;
                border-radius: 10px;
            }

            QLabel#ozetBaslik {
                color: #697993;
                font-size: 12px;
                font-weight: 500;
                border: none;
                background: transparent;
            }

            QLabel#ozetDeger {
                color: #16294B;
                font-size: 24px;
                font-weight: bold;
                border: none;
                background: transparent;
            }

            QLabel#tabloBaslik {
                color: #0A1F5C;
                font-size: 15px;
                font-weight: bold;
                background: transparent;
                border: none;
            }

            QLabel#tabloAciklama {
                color: #8090AA;
                font-size: 12px;
                background: transparent;
                border: none;
            }

            QLineEdit, QComboBox {
                background: #FFFFFF;
                color: #183461;
                border: 1px solid #D1DDED;
                border-radius: 8px;
                padding: 4px 9px;
                min-height: 25px;
                font-size: 13px;
            }

            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #3778D8;
                background: #FFFFFF;
            }

            QLineEdit::placeholder {
                color: #96A5B8;
            }

            QPushButton {
                background: #285CE6;
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 7px 12px;
                min-height: 28px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1E4BC5;
            }

            QPushButton#temizleBtn,
            QPushButton#ikincilBtn {
                background: #F5F8FF;
                color: #0A1F5C;
                border: 1px solid #D6E2F5;
            }

            QPushButton#temizleBtn:hover,
            QPushButton#ikincilBtn:hover {
                background: #E9F1FF;
            }

            QTableWidget {
                background: #FFFFFF;
                color: #243650;
                border: 1px solid #E3EAF5;
                border-radius: 7px;
                alternate-background-color: #FFFFFF;
                gridline-color: #E3EAF5;
                font-size: 13px;
                selection-background-color: #E6EEFC;
                selection-color: #173263;
            }

            QTableWidget::item {
                padding-left: 5px;
                padding-right: 5px;
                border-bottom: 1px solid #EDF1F7;
            }

            QTableWidget::item:selected {
                background: #E6EEFC;
                color: #173263;
            }

            QHeaderView::section {
                background: #E8F0FF;
                color: #16294B;
                padding: 9px 5px;
                font-size: 12px;
                font-weight: bold;
                border: none;
                border-right: 1px solid #D6E2F3;
                border-bottom: 1px solid #D6E2F3;
            }

            QCheckBox {
                color: #284166;
                spacing: 8px;
                background: transparent;
                font-size: 13px;
                font-weight: 500;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #B7C7DE;
                border-radius: 4px;
                background: #FFFFFF;
            }

            QCheckBox::indicator:hover {
                border: 1px solid #7E9DCC;
            }

            QCheckBox::indicator:checked {
                background: #0A1F5C;
                border: 1px solid #0A1F5C;
            }

            QScrollBar:vertical {
                background: #F3F6FB;
                width: 10px;
                margin: 0;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #C3D0E4;
                min-height: 35px;
                border-radius: 5px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        from PySide6.QtWidgets import QScrollArea, QSizePolicy
        dis = QVBoxLayout(self)
        dis.setContentsMargins(0, 0, 0, 0)
        dis.setSpacing(0)
        kaydirma = QScrollArea(self)
        kaydirma.setWidgetResizable(True)
        kaydirma.setFrameShape(QFrame.NoFrame)
        kaydirma.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        kaydirma.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        govde = QWidget()
        ana = QVBoxLayout(govde)
        kaydirma.setWidget(govde)
        dis.addWidget(kaydirma, 1)
        ana.setContentsMargins(22, 16, 22, 19)
        ana.setSpacing(11)

        # Özet kartları
        kartlar = QGridLayout()
        kartlar.setSpacing(12)

        self.ozet_degerleri = {}

        basliklar = [
            ("toplam_kayit", "Toplam Kayıt", "#16294B"),
            ("basarisiz_giris", "Başarısız Giriş", "#B03840"),
            ("kullanici_islemleri", "Değişiklik İşlemleri", "#285CE6"),
            ("bugunku_islemler", "Bugünkü Kayıtlar", "#16803C"),
        ]

        for sira, (anahtar, baslik, renk) in enumerate(basliklar):
            kart = QFrame()
            kart.setObjectName("ozetKart")

            icerik = QVBoxLayout(kart)
            icerik.setContentsMargins(15, 12, 15, 12)

            baslik_etiketi = QLabel(baslik)
            baslik_etiketi.setObjectName("ozetBaslik")

            deger = QLabel("—")
            deger.setObjectName("ozetDeger")
            deger.setStyleSheet(f"color: {renk};")

            self.ozet_degerleri[anahtar] = deger

            icerik.addWidget(baslik_etiketi)
            icerik.addWidget(deger)
            kartlar.addWidget(kart, 0, sira)

        ana.addLayout(kartlar)

        # Filtreler
        filtre_alani = QVBoxLayout()
        filtre_alani.setSpacing(6)

        arama_satiri = QHBoxLayout()
        arama_satiri.setSpacing(9)

        self.kullanici_arama = QLineEdit()
        self.kullanici_arama.setPlaceholderText("Kullanıcı adı ara...")
        self.kullanici_arama.returnPressed.connect(self.filtrele)
        arama_satiri.addWidget(self.kullanici_arama, 3)

        self.olay_secimi = CokluIslemSecici()
        self.olay_secimi.setCursor(Qt.CursorShape.PointingHandCursor)
        arama_satiri.addWidget(self.olay_secimi, 2)

        filtre_btn = QPushButton("Filtrele")
        filtre_btn.clicked.connect(self.filtrele)
        arama_satiri.addWidget(filtre_btn)

        temizle_btn = QPushButton("Filtreleri Temizle")
        temizle_btn.setObjectName("temizleBtn")
        temizle_btn.clicked.connect(self.filtreleri_temizle)
        arama_satiri.addWidget(temizle_btn)

        yenile_btn = QPushButton("Yenile")
        yenile_btn.setObjectName("ikincilBtn")
        yenile_btn.clicked.connect(self.kayitlari_getir)
        arama_satiri.addWidget(yenile_btn)

        for buton in (filtre_btn, temizle_btn, yenile_btn):
            buton.setCursor(Qt.CursorShape.PointingHandCursor)

        filtre_alani.addLayout(arama_satiri)

        tarih_satiri = QHBoxLayout()
        tarih_satiri.setSpacing(9)

        tarih_satiri.addWidget(QLabel("Dönem:"))

        self.donem_secimi = QComboBox()
        self.donem_secimi.setFixedWidth(185)
        self.donem_secimi.setFixedHeight(36)
        self.donem_secimi.addItems([
            "Tümü",
            "Bugün",
            "Son 7 Gün",
            "Son 30 Gün",
            "Tarih Aralığı"
        ])
        self.donem_secimi.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        tarih_satiri.addWidget(self.donem_secimi)

        tarih_satiri.addWidget(QLabel("Başlangıç:"))

        self.baslangic = QDateEdit()
        self.baslangic.setFixedWidth(150)
        self.baslangic.setCalendarPopup(True)
        self.baslangic.setDisplayFormat("dd.MM.yyyy")
        self.baslangic.setDate(QDate.currentDate().addDays(-7))
        self.baslangic.setEnabled(False)
        tarih_satiri.addWidget(self.baslangic)

        tarih_satiri.addWidget(QLabel("Bitiş:"))

        self.bitis = QDateEdit()
        self.bitis.setFixedWidth(150)
        self.bitis.setCalendarPopup(True)
        self.bitis.setDisplayFormat("dd.MM.yyyy")
        self.bitis.setDate(QDate.currentDate())
        self.bitis.setEnabled(False)
        tarih_satiri.addWidget(self.bitis)

        self.donem_secimi.currentIndexChanged.connect(
            self._donem_degisti
        )

        tarih_satiri.addStretch()
        filtre_alani.addLayout(tarih_satiri)
        filtre_alani.setContentsMargins(0, 0, 0, 0)
        filtre_alani.setSpacing(9)
        ana.insertLayout(0, filtre_alani)

        # Salt okunur kayıt tablosu
        self.tablo = QTableWidget()
        self.tablo.setMinimumHeight(300)
        self.tablo.setColumnCount(5)
        self.tablo.setHorizontalHeaderLabels([
            "Tarih / Saat", "İşlemi Yapan",
            "İşlem Türü", "İlgili Kayıt Türü",
            "Detay"
        ])

        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setAlternatingRowColors(False)
        self.tablo.verticalHeader().setVisible(False)

        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(0, QHeaderView.Fixed)
        baslik.setSectionResizeMode(1, QHeaderView.Stretch)
        baslik.setSectionResizeMode(2, QHeaderView.Stretch)
        baslik.setSectionResizeMode(3, QHeaderView.Stretch)
        baslik.setSectionResizeMode(4, QHeaderView.Fixed)

        self.tablo.setColumnWidth(0, 175)
        self.tablo.setColumnWidth(4, 115)

        self.tablo.setShowGrid(True)
        self.tablo.verticalHeader().setDefaultSectionSize(42)
        self.tablo.horizontalHeader().setFixedHeight(46)

        self.tablo.setItemDelegateForColumn(
            2, IslemEtiketiDelegate(self.tablo)
        )

        tablo_kart = QFrame()
        tablo_kart.setObjectName("tabloKart")

        tablo_duzen = QVBoxLayout(tablo_kart)
        tablo_duzen.setContentsMargins(14, 14, 14, 14)
        tablo_duzen.setSpacing(10)

        tablo_ust = QHBoxLayout()

        tablo_baslik = QLabel("Denetim Geçmişi")
        tablo_baslik.setObjectName("tabloBaslik")
        tablo_ust.addWidget(tablo_baslik)

        tablo_ust.addStretch()

        tablo_aciklama = QLabel("Salt okunur işlem geçmişi")
        tablo_aciklama.setObjectName("tabloAciklama")
        tablo_ust.addWidget(tablo_aciklama)

        tablo_duzen.addLayout(tablo_ust)

        tablo_duzen.addWidget(self.tablo, 1)

        ana.addWidget(tablo_kart, 1)

        # Sayfalama ve durum bilgisi
        alt = QHBoxLayout()

        self.durum = QLabel("Kayıtlar yükleniyor...")
        self.durum.setTextFormat(Qt.PlainText)
        alt.addWidget(self.durum)

        alt.addStretch()

        self.onceki_btn = QPushButton("← Önceki")
        self.onceki_btn.clicked.connect(self.onceki_sayfa)
        alt.addWidget(self.onceki_btn)

        self.sonraki_btn = QPushButton("Sonraki →")
        self.sonraki_btn.clicked.connect(self.sonraki_sayfa)
        alt.addWidget(self.sonraki_btn)

        # Sayfalama butonlari her durumda ayni lacivert renkte
        for buton in (self.onceki_btn, self.sonraki_btn):
            buton.setCursor(Qt.CursorShape.PointingHandCursor)
            buton.setStyleSheet("""
                QPushButton {
                    background: #285CE6;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 9px 15px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #1E4BC5;
                }
                QPushButton:disabled {
                    background: #DCE6F5;
                    color: #8192AD;
                }
            """)

        self.onceki_btn.setMinimumWidth(120)
        self.sonraki_btn.setMinimumWidth(120)

        # Sayfalama bolumu kaydirilan alanin disinda kalir.
        alt_kapsayici = QWidget(self)
        alt.setContentsMargins(22, 18, 22, 4)
        alt_kapsayici.setLayout(alt)
        alt_kapsayici.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        dis.addWidget(alt_kapsayici)

        self.sayfalama_guncelle()

    def _audit_detayini_goster(self, kayit, tarih):
        pencere = QDialog(self)
        pencere.setWindowTitle("Denetim Kaydı Detayları")
        pencere.setObjectName("auditDetayPenceresi")
        pencere.setStyleSheet(
            "QDialog#auditDetayPenceresi { background-color: #FFFFFF; }"
        )
        pencere.setMinimumWidth(450)

        duzen = QVBoxLayout(pencere)
        duzen.setContentsMargins(24, 22, 24, 20)
        duzen.setSpacing(16)

        baslik = QLabel("Denetim Kaydı Detayları")
        baslik.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #102D59;"
        )
        duzen.addWidget(baslik)

        bilgiler = [
            ("Kayıt ID", kayit.get("denetim_id")),
            ("Tarih / Saat", tarih),
            ("İşlemi Yapan", kayit.get("kullanici_adi")),
            ("Kullanıcı ID", kayit.get("kullanici_id")),
            ("İşlem Türü", OLAY_ADLARI.get(
                kayit.get("olay_turu"),
                kayit.get("olay_turu")
            )),
            ("Hedef Tablo", kayit.get("hedef_tablo")),
            ("Hedef Kayıt ID", kayit.get("hedef_kayit_id")),
        ]

        if (
            kayit.get("hedef_tablo") == "kullanicilar"
            and kayit.get("hedef_kayit_id") is not None
        ):
            bilgiler.insert(-1, (
                "İşlem Yapılan Kullanıcı",
                kayit.get("hedef_kullanici_adi")
                or "Bulunamadı (kayıt silinmiş olabilir)"
            ))

        izgara = QGridLayout()
        izgara.setHorizontalSpacing(20)
        izgara.setVerticalSpacing(12)

        for sira, (alan, deger) in enumerate(bilgiler):
            ad = QLabel(alan + ":")
            ad.setStyleSheet(
                "font-weight: bold; color: #31517D;"
            )

            deger_yazisi = QLabel(
                "—" if deger is None else str(deger)
            )
            deger_yazisi.setTextFormat(Qt.PlainText)
            deger_yazisi.setWordWrap(True)
            deger_yazisi.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            izgara.addWidget(ad, sira, 0)
            izgara.addWidget(deger_yazisi, sira, 1)

        izgara.setColumnStretch(1, 1)
        duzen.addLayout(izgara)

        kapat = QPushButton("Kapat")
        kapat.setCursor(Qt.PointingHandCursor)
        kapat.setMinimumWidth(100)
        kapat.clicked.connect(pencere.accept)

        duzen.addWidget(kapat, alignment=Qt.AlignRight)
        pencere.exec()

    def _donem_degisti(self, *_):
        secim = self.donem_secimi.currentText()
        bugun = QDate.currentDate()

        if secim == "Bugün":
            self.baslangic.setDate(bugun)
            self.bitis.setDate(bugun)

        elif secim == "Son 7 Gün":
            self.baslangic.setDate(bugun.addDays(-6))
            self.bitis.setDate(bugun)

        elif secim == "Son 30 Gün":
            self.baslangic.setDate(bugun.addDays(-29))
            self.bitis.setDate(bugun)

        manuel = secim == "Tarih Aralığı"
        self.baslangic.setEnabled(manuel)
        self.bitis.setEnabled(manuel)

    def filtrele(self):
        self.offset = 0
        self.kayitlari_getir()

    def filtreleri_temizle(self):
        self.kullanici_arama.clear()
        self.olay_secimi.temizle()
        self.donem_secimi.setCurrentIndex(0)
        self.baslangic.setDate(QDate.currentDate().addDays(-7))
        self.bitis.setDate(QDate.currentDate())
        self.offset = 0
        self.kayitlari_getir()

    def onceki_sayfa(self):
        if self.offset >= self.limit:
            self.offset -= self.limit
            self.kayitlari_getir()

    def sonraki_sayfa(self):
        if self.offset + self.limit < self.toplam:
            self.offset += self.limit
            self.kayitlari_getir()

    def sayfalama_guncelle(self):
        self.onceki_btn.setEnabled(self.offset > 0)
        self.sonraki_btn.setEnabled(
            self.offset + self.limit < self.toplam
        )

    def kayitlari_getir(self):
        self._donem_degisti()

        if (
            self.donem_secimi.currentText() == "Tarih Aralığı"
            and self.baslangic.date() > self.bitis.date()
        ):
            self.durum.setText(
                "Başlangıç tarihi bitiş tarihinden sonra olamaz."
            )
            return

        parametreler = {
            "limit": self.limit,
            "offset": self.offset
        }

        kullanici = self.kullanici_arama.text().strip()
        if kullanici:
            parametreler["kullanici"] = kullanici

        olay = self.olay_secimi.secilenler()
        if olay:
            parametreler["olay_turu"] = olay

        if (self.donem_secimi.currentIndex() != 0):
            if self.baslangic.date() > self.bitis.date():
                self.durum.setText(
                    "Başlangıç tarihi bitiş tarihinden sonra olamaz."
                )
                return

            parametreler["baslangic_tarihi"] = (
                self.baslangic.date().toString("yyyy-MM-dd")
            )
            parametreler["bitis_tarihi"] = (
                self.bitis.date().toString("yyyy-MM-dd")
            )

        try:
            yanit = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/audit-kayitlari",
                headers={
                    "Authorization": f"Bearer {self.token}"
                },
                params=parametreler,
                timeout=15
            )
            if oturum_hatasi_mi(yanit):
                return
            yanit.raise_for_status()
            veri = yanit.json()

        except requests.RequestException as hata:
            self.tablo.setRowCount(0)
            self.toplam = 0
            self.sayfalama_guncelle()
            self.durum.setText(
                f"Denetim kayıtları yüklenemedi: {hata}"
            )
            return

        ozet = veri.get("ozet", {})

        for anahtar, etiket in self.ozet_degerleri.items():
            etiket.setText(str(ozet.get(anahtar, 0)))

        kayitlar = veri.get("kayitlar", [])
        self.toplam = int(ozet.get("toplam_kayit", 0))

        self.tablo.setRowCount(len(kayitlar))

        for satir_no, kayit in enumerate(kayitlar):
            tarih = (kayit.get("olusturulma_tarihi") or "")
            if tarih:
                try:
                    tarih = datetime.fromisoformat(tarih).strftime(
                        "%d.%m.%Y %H:%M:%S"
                    )
                except ValueError:
                    tarih = tarih.replace("T", " ")[:19]

            hedef = kayit.get("hedef_tablo")

            alanlar = [
                tarih,
                kayit.get("kullanici_adi"),
                OLAY_ADLARI.get(
                    kayit.get("olay_turu"),
                    kayit.get("olay_turu")
                ),
                HEDEF_TABLO_ADLARI.get(hedef, hedef),
            ]

            for sutun_no, deger in enumerate(alanlar):
                metin = "—" if deger is None else str(deger)
                hucre = QTableWidgetItem(metin)

                if sutun_no == 2:
                    hucre.setData(
                        Qt.UserRole, kayit.get("olay_turu")
                    )

                self.tablo.setItem(satir_no, sutun_no, hucre)

            hucre_alani = QWidget()
            hucre_duzen = QHBoxLayout(hucre_alani)
            hucre_duzen.setContentsMargins(5, 3, 5, 3)

            detay_btn = QPushButton("Görüntüle")
            detay_btn.setFixedSize(92, 30)
            detay_btn.setCursor(Qt.PointingHandCursor)
            detay_btn.setStyleSheet("""
                QPushButton {
                    background: #E9F1FF;
                    color: #2457A2;
                    border: none;
                    border-radius: 7px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #D4E5FF;
                }
            """)

            detay_btn.clicked.connect(
                lambda _checked=False, k=dict(kayit), t=tarih:
                    self._audit_detayini_goster(k, t)
            )

            hucre_duzen.addStretch()
            hucre_duzen.addWidget(detay_btn)
            hucre_duzen.addStretch()

            self.tablo.setCellWidget(
                satir_no, 4, hucre_alani
            )

        ilk = self.offset + 1 if kayitlar else 0
        son = self.offset + len(kayitlar)

        self.durum.setText(
            f"{self.toplam} kayıttan {ilk}-{son} arası gösteriliyor."
        )

        self.sayfalama_guncelle()
