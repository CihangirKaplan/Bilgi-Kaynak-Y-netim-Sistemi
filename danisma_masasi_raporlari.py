"""TKYS - Danışma Masası Raporları (Salt Okunur)."""

from datetime import datetime

import requests

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class DanismaMasasiRaporlari(QWidget):
    NAVY = "#16294B"
    BLUE = "#285CE6"

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self._ogrenciler_yuklendi = False

        self._arayuz_kur()
        self.yenile()

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}"
        }

    @staticmethod
    def _sure(saniye):
        dakika = max(0, int(saniye or 0)) // 60
        return f"{dakika // 60} sa {dakika % 60:02d} dk"

    @staticmethod
    def _tarih(deger):
        if not deger:
            return "—"
        return datetime.fromisoformat(deger).strftime(
            "%d.%m.%Y %H:%M"
        )

    def _tablo_olustur(self, basliklar):
        tablo = QTableWidget()
        tablo.setColumnCount(len(basliklar))
        tablo.setHorizontalHeaderLabels(basliklar)
        tablo.setAlternatingRowColors(False)
        tablo.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        tablo.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        tablo.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        tablo.verticalHeader().setVisible(False)
        tablo.verticalHeader().setDefaultSectionSize(36)
        tablo.setStyleSheet("""
            QTableWidget {
                background: white;
                gridline-color: #E3EAF5;
                color: #243653;
                border: 1px solid #E3EAF5;
            }
            QHeaderView::section {
                background: #E8F0FF;
                color: #16294B;
                font-weight: bold;
                padding: 9px 5px;
                border: none;
                border-right: 1px solid #D6E2F3;
                border-bottom: 1px solid #D6E2F3;
            }
        """)
        return tablo

    def _arayuz_kur(self):
        self.setStyleSheet("""
            QWidget#danismaRaporlari {
                background: #EAF0FA;
            }
            QPushButton {
                background: #285CE6;
                color: white;
                border-radius: 8px;
                padding: 10px 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1E4BC5;
            }
        """)
        self.setObjectName("danismaRaporlari")

        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 16, 20, 20)
        ana.setSpacing(13)

        # Filtreler
        filtre_satiri = QHBoxLayout()

        filtre_satiri.addWidget(QLabel("Dönem:"))
        self.donem = QComboBox()
        self.donem.addItems([
            "Tümü",
            "Bugün",
            "Bu Hafta",
            "Geçen Hafta",
            "Tarih Aralığı"
        ])
        self.donem.currentIndexChanged.connect(
            self._tarih_alanlari
        )
        filtre_satiri.addWidget(self.donem)

        filtre_satiri.addWidget(QLabel("Başlangıç:"))
        self.baslangic = QDateEdit()
        self.baslangic.setCalendarPopup(True)
        self.baslangic.setDisplayFormat("dd.MM.yyyy")
        self.baslangic.setDate(
            QDate.currentDate().addDays(-7)
        )
        filtre_satiri.addWidget(self.baslangic)

        filtre_satiri.addWidget(QLabel("Bitiş:"))
        self.bitis = QDateEdit()
        self.bitis.setCalendarPopup(True)
        self.bitis.setDisplayFormat("dd.MM.yyyy")
        self.bitis.setDate(QDate.currentDate())
        filtre_satiri.addWidget(self.bitis)

        filtre_satiri.addWidget(QLabel("Öğrenci:"))
        self.ogrenci_sec = QComboBox()
        self.ogrenci_sec.addItem("Tüm Öğrenciler", None)
        filtre_satiri.addWidget(self.ogrenci_sec, 1)

        yenile_btn = QPushButton("↻ Raporu Getir")
        yenile_btn.clicked.connect(self.yenile)
        filtre_satiri.addWidget(yenile_btn)

        ana.addLayout(filtre_satiri)
        self._tarih_alanlari()

        # Özet kartları
        kart_satiri = QHBoxLayout()
        kart_satiri.setSpacing(12)

        self.kartlar = {}

        for anahtar, baslik, renk in [
            ("toplam_gorev", "Toplam Görev", "#16294B"),
            ("devam_eden", "Devam Eden", "#285CE6"),
            ("onay_bekleyen", "Onay Bekleyen", "#B86B08"),
            ("onaylanan", "Onaylanan", "#16803C"),
            ("toplam_calisma_saniye",
             "Toplam Çalışma Süresi", "#16294B"),
            ("onaylanan_calisma_saniye",
             "Onaylı Çalışma Süresi", "#16803C"),
        ]:
            kart = QFrame()
            kart.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #E3EAF5;
                    border-radius: 10px;
                }
                QLabel {
                    border: none;
                }
            """)

            icerik = QVBoxLayout(kart)
            icerik.setContentsMargins(15, 12, 15, 12)

            etiket = QLabel(baslik)
            etiket.setStyleSheet(
                "color: #697993; font-size: 12px;"
            )

            deger = QLabel("0")
            deger.setStyleSheet(
                f"color: {renk}; font-size: 24px;"
                "font-weight: bold;"
            )

            icerik.addWidget(etiket)
            icerik.addWidget(deger)

            self.kartlar[anahtar] = deger
            kart_satiri.addWidget(kart, 1)

        ana.addLayout(kart_satiri)

        # İki sekmeli raporlama alanı
        self.rapor_sekmeleri = QTabWidget()
        self.rapor_sekmeleri.setStyleSheet("""
            QTabWidget::pane {
                background: white;
                border: 1px solid #DCE5F3;
                border-radius: 8px;
            }
            QTabBar::tab {
                background: #E3ECFA;
                color: #617493;
                padding: 12px 24px;
                margin-right: 5px;
                font-weight: bold;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: white;
                color: #16294B;
                border-bottom: 3px solid #285CE6;
            }
            QTabBar::tab:hover {
                color: #285CE6;
            }
        """)

        # 1. sekme: Görev Kayıtları
        gorev_sayfasi = QWidget()
        gorev_layout = QVBoxLayout(gorev_sayfasi)
        gorev_layout.setContentsMargins(12, 12, 12, 12)

        self.gorev_tablo = self._tablo_olustur([
            "Öğrenci",
            "Başlangıç",
            "Bitiş",
            "Çalışma Süresi",
            "Görev Durumu",
            "Onay Durumu"
        ])

        gorev_layout.addWidget(self.gorev_tablo)

        self.rapor_sekmeleri.addTab(
            gorev_sayfasi, "Görev Kayıtları"
        )

        # 2. sekme: Öğrenci Bazlı Raporlar
        ogrenci_sayfasi = QWidget()
        ogrenci_layout = QVBoxLayout(ogrenci_sayfasi)
        ogrenci_layout.setContentsMargins(12, 12, 12, 12)

        self.ogrenci_tablo = self._tablo_olustur([
            "Öğrenci",
            "Öğrenci No",
            "Görev",
            "Onay Bekleyen",
            "Onaylanan",
            "Toplam Süre",
            "Onaylı Süre"
        ])

        ogrenci_layout.addWidget(self.ogrenci_tablo)

        self.rapor_sekmeleri.addTab(
            ogrenci_sayfasi, "Öğrenci Bazlı Raporlar"
        )

        # Görev kayıtları varsayılan olarak açık olsun.
        self.rapor_sekmeleri.setCurrentIndex(0)
        ana.addWidget(self.rapor_sekmeleri, 1)

    def _tarih_alanlari(self, *args):
        ozel = self.donem.currentText() == "Tarih Aralığı"
        self.baslangic.setEnabled(ozel)
        self.bitis.setEnabled(ozel)

    def _parametreler(self):
        bugun = QDate.currentDate()
        secim = self.donem.currentText()
        params = {}

        if secim == "Bugün":
            bas, bit = bugun, bugun

        elif secim == "Bu Hafta":
            bas = bugun.addDays(1 - bugun.dayOfWeek())
            bit = bugun

        elif secim == "Geçen Hafta":
            bu_hafta = bugun.addDays(
                1 - bugun.dayOfWeek()
            )
            bas = bu_hafta.addDays(-7)
            bit = bu_hafta.addDays(-1)

        elif secim == "Tarih Aralığı":
            bas = self.baslangic.date()
            bit = self.bitis.date()

            if bit < bas:
                raise ValueError(
                    "Bitiş tarihi başlangıçtan önce olamaz."
                )

        else:
            bas = bit = None

        if bas is not None:
            params["baslangic_tarihi"] = bas.toString(
                "yyyy-MM-dd"
            )
            params["bitis_tarihi"] = bit.toString(
                "yyyy-MM-dd"
            )

        ogrenci_id = self.ogrenci_sec.currentData()
        if ogrenci_id is not None:
            params["ogrenci_id"] = ogrenci_id

        return params

    def _hucre(self, tablo, satir, sutun, deger, renk=None):
        hucre = QTableWidgetItem(str(deger))
        hucre.setFlags(
            hucre.flags() & ~Qt.ItemIsEditable
        )

        if renk:
            hucre.setForeground(QColor(renk))

        if sutun == 0:
            font = hucre.font()
            font.setBold(True)
            hucre.setFont(font)

        tablo.setItem(satir, sutun, hucre)

    def yenile(self):
        try:
            params = self._parametreler()
        except ValueError as hata:
            QMessageBox.warning(
                self, "Geçersiz Tarih", str(hata)
            )
            return

        try:
            yanit = requests.get(
                f"{self.api_url}/api/danisma/raporlar",
                headers=self._headers(),
                params=params,
                timeout=15
            )
            yanit.raise_for_status()
            veri = yanit.json()

        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(
                self,
                "Rapor Hatası",
                f"Rapor bilgileri alınamadı:\n{hata}"
            )
            return

        ozet = veri.get("ozet", {})

        for anahtar, etiket in self.kartlar.items():
            deger = ozet.get(anahtar, 0)

            if anahtar in (
                "toplam_calisma_saniye",
                "onaylanan_calisma_saniye"
            ):
                deger = self._sure(deger)

            etiket.setText(str(deger))

        ogrenciler = veri.get("ogrenci_ozetleri", [])

        # İlk yüklemede öğrenci filtresini oluştur.
        if not self._ogrenciler_yuklendi:
            for ogrenci in ogrenciler:
                self.ogrenci_sec.addItem(
                    f"{ogrenci['ad_soyad']} - "
                    f"{ogrenci['ogrenci_numarasi']}",
                    ogrenci["ogrenci_id"]
                )
            self._ogrenciler_yuklendi = True

        self.ogrenci_tablo.setRowCount(len(ogrenciler))

        for satir, ogrenci in enumerate(ogrenciler):
            degerler = [
                ogrenci["ad_soyad"],
                ogrenci["ogrenci_numarasi"],
                ogrenci["toplam_gorev"],
                ogrenci["onay_bekleyen"],
                ogrenci["onaylanan"],
                self._sure(ogrenci["toplam_saniye"]),
                self._sure(ogrenci["onaylanan_saniye"])
            ]

            for sutun, deger in enumerate(degerler):
                self._hucre(
                    self.ogrenci_tablo,
                    satir, sutun, deger
                )

        oturumlar = veri.get("oturumlar", [])
        self.gorev_tablo.setRowCount(len(oturumlar))

        for satir, oturum in enumerate(oturumlar):
            tamamlandi = (
                oturum.get("bitis_zamani") is not None
            )
            onaylandi = oturum.get("onaylandi_mi", False)

            degerler = [
                oturum.get("ad_soyad", ""),
                self._tarih(oturum["baslangic_zamani"]),
                self._tarih(oturum.get("bitis_zamani")),
                (
                    self._sure(oturum["toplam_saniye"])
                    if tamamlandi else "Devam Ediyor"
                ),
                "Tamamlandı" if tamamlandi else "Devam Ediyor",
                (
                    "Onaylandı" if onaylandi
                    else "Onay Bekliyor" if tamamlandi
                    else "—"
                )
            ]

            for sutun, deger in enumerate(degerler):
                renk = None

                if sutun == 4:
                    renk = (
                        "#16803C" if tamamlandi else "#285CE6"
                    )
                elif sutun == 5:
                    renk = (
                        "#16803C" if onaylandi else "#B86B08"
                    )

                self._hucre(
                    self.gorev_tablo,
                    satir, sutun, deger, renk
                )
