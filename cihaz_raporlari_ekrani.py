"""TKYS - Cihaz Raporları (Salt Okunur): bakım, kalibrasyon ve arıza kayıtları."""

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


class CihazRaporlariEkrani(QWidget):
    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self._cihazlar_yuklendi = False

        self._arayuz_kur()
        self.yenile()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    @staticmethod
    def _tarih(deger):
        if not deger:
            return "—"
        try:
            parca = datetime.fromisoformat(deger)
        except ValueError:
            return str(deger)
        if len(str(deger)) <= 10:
            return parca.strftime("%d.%m.%Y")
        return parca.strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _para(deger):
        return f"{float(deger or 0):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", ".")

    def _tablo_olustur(self, basliklar):
        tablo = QTableWidget()
        tablo.setColumnCount(len(basliklar))
        tablo.setHorizontalHeaderLabels(basliklar)
        tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
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
        self.setObjectName("cihazRaporlari")
        self.setStyleSheet("""
            QWidget#cihazRaporlari {
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

        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 16, 20, 20)
        ana.setSpacing(13)

        # Filtreler
        filtre_satiri = QHBoxLayout()

        filtre_satiri.addWidget(QLabel("Dönem:"))
        self.donem = QComboBox()
        self.donem.addItems(["Tümü", "Bugün", "Bu Hafta", "Bu Ay", "Tarih Aralığı"])
        self.donem.currentIndexChanged.connect(self._tarih_alanlari)
        filtre_satiri.addWidget(self.donem)

        filtre_satiri.addWidget(QLabel("Başlangıç:"))
        self.baslangic = QDateEdit()
        self.baslangic.setCalendarPopup(True)
        self.baslangic.setDisplayFormat("dd.MM.yyyy")
        self.baslangic.setDate(QDate.currentDate().addDays(-30))
        filtre_satiri.addWidget(self.baslangic)

        filtre_satiri.addWidget(QLabel("Bitiş:"))
        self.bitis = QDateEdit()
        self.bitis.setCalendarPopup(True)
        self.bitis.setDisplayFormat("dd.MM.yyyy")
        self.bitis.setDate(QDate.currentDate())
        filtre_satiri.addWidget(self.bitis)

        filtre_satiri.addWidget(QLabel("Cihaz:"))
        self.cihaz_sec = QComboBox()
        self.cihaz_sec.addItem("Tüm Cihazlar", None)
        filtre_satiri.addWidget(self.cihaz_sec, 1)

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
            ("bakim_sayisi", "Bakım Kaydı", "#16294B"),
            ("toplam_bakim_maliyeti", "Toplam Bakım Maliyeti", "#16294B"),
            ("kalibrasyon_sayisi", "Kalibrasyon Kaydı", "#285CE6"),
            ("ariza_sayisi", "Arıza Kaydı", "#B86B08"),
            ("acik_ariza_sayisi", "Açık Arıza", "#C0392B"),
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
            etiket.setStyleSheet("color: #697993; font-size: 12px;")
            deger = QLabel("0")
            deger.setStyleSheet(f"color: {renk}; font-size: 24px; font-weight: bold;")

            icerik.addWidget(etiket)
            icerik.addWidget(deger)
            self.kartlar[anahtar] = deger
            kart_satiri.addWidget(kart, 1)

        ana.addLayout(kart_satiri)

        # Sekmeler
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

        self.bakim_tablo = self._sekme_ekle("Bakım Geçmişi", [
            "Cihaz", "Bakım Tarihi", "Yapan Kişi", "Yapılan İşlem", "Maliyet", "Sonraki Bakım"
        ])
        self.kalibrasyon_tablo = self._sekme_ekle("Kalibrasyon", [
            "Cihaz", "İşlem Tarihi", "Kurum", "Sertifika No", "Geçerlilik Tarihi"
        ])
        self.ariza_tablo = self._sekme_ekle("Arızalar", [
            "Cihaz", "Bildirim Tarihi", "Bildiren", "Açıklama", "Durum", "Çözüm Tarihi"
        ])

        ana.addWidget(self.rapor_sekmeleri, 1)

    def _sekme_ekle(self, baslik, kolonlar):
        sayfa = QWidget()
        duzen = QVBoxLayout(sayfa)
        duzen.setContentsMargins(12, 12, 12, 12)
        tablo = self._tablo_olustur(kolonlar)
        duzen.addWidget(tablo)
        self.rapor_sekmeleri.addTab(sayfa, baslik)
        return tablo

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
            bas, bit = bugun.addDays(1 - bugun.dayOfWeek()), bugun
        elif secim == "Bu Ay":
            bas, bit = QDate(bugun.year(), bugun.month(), 1), bugun
        elif secim == "Tarih Aralığı":
            bas, bit = self.baslangic.date(), self.bitis.date()
            if bit < bas:
                raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
        else:
            bas = bit = None

        if bas is not None:
            params["baslangic_tarihi"] = bas.toString("yyyy-MM-dd")
            params["bitis_tarihi"] = bit.toString("yyyy-MM-dd")

        cihaz_id = self.cihaz_sec.currentData()
        if cihaz_id is not None:
            params["cihaz_id"] = cihaz_id

        return params

    def _cihazlari_yukle(self):
        """Cihaz filtresini yalnızca ilk yüklemede doldurur; hata olursa rapor yine çalışır."""
        try:
            yanit = requests.get(
                f"{self.api_url}/api/cihazlar", headers=self._headers(), timeout=15
            )
            yanit.raise_for_status()
            for cihaz in yanit.json():
                self.cihaz_sec.addItem(
                    f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}", cihaz["cihaz_id"]
                )
            self._cihazlar_yuklendi = True
        except (requests.RequestException, ValueError, KeyError):
            pass

    def _hucre(self, tablo, satir, sutun, deger, renk=None):
        hucre = QTableWidgetItem(str(deger))
        hucre.setFlags(hucre.flags() & ~Qt.ItemIsEditable)
        if renk:
            hucre.setForeground(QColor(renk))
        if sutun == 0:
            font = hucre.font()
            font.setBold(True)
            hucre.setFont(font)
        tablo.setItem(satir, sutun, hucre)

    def _tabloyu_doldur(self, tablo, satirlar, renkler=None):
        tablo.setRowCount(len(satirlar))
        for satir, degerler in enumerate(satirlar):
            for sutun, deger in enumerate(degerler):
                renk = renkler.get((sutun, deger)) if renkler else None
                self._hucre(tablo, satir, sutun, deger, renk)

    def yenile(self):
        try:
            params = self._parametreler()
        except ValueError as hata:
            QMessageBox.warning(self, "Geçersiz Tarih", str(hata))
            return

        if not self._cihazlar_yuklendi:
            self._cihazlari_yukle()

        try:
            yanit = requests.get(
                f"{self.api_url}/api/cihaz-raporlari",
                headers=self._headers(),
                params=params,
                timeout=15,
            )
            yanit.raise_for_status()
            veri = yanit.json()
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(
                self, "Rapor Hatası", f"Rapor bilgileri alınamadı:\n{hata}"
            )
            return

        ozet = veri.get("ozet", {})
        for anahtar, etiket in self.kartlar.items():
            deger = ozet.get(anahtar, 0)
            if anahtar == "toplam_bakim_maliyeti":
                deger = self._para(deger)
            etiket.setText(str(deger))

        self._tabloyu_doldur(self.bakim_tablo, [
            [
                b["cihaz"],
                self._tarih(b["bakim_tarihi"]),
                b.get("bakim_yapan_kisi") or "—",
                b.get("yapilan_islem") or "—",
                self._para(b["maliyet"]),
                self._tarih(b["sonraki_bakim_tarihi"]),
            ]
            for b in veri.get("bakimlar", [])
        ])

        self._tabloyu_doldur(self.kalibrasyon_tablo, [
            [
                k["cihaz"],
                self._tarih(k["islem_tarihi"]),
                k.get("kalibrasyon_yapan_kurum") or "—",
                k.get("sertifika_no") or "—",
                self._tarih(k["gecerlilik_tarihi"]),
            ]
            for k in veri.get("kalibrasyonlar", [])
        ])

        self._tabloyu_doldur(
            self.ariza_tablo,
            [
                [
                    a["cihaz"],
                    self._tarih(a["bildirim_tarihi"]),
                    a.get("bildiren_personel") or "—",
                    a.get("ariza_aciklamasi") or "—",
                    a["durum"],
                    self._tarih(a["cozum_tarihi"]),
                ]
                for a in veri.get("arizalar", [])
            ],
            renkler={(4, "Açık"): "#C0392B", (4, "Çözüldü"): "#16803C"},
        )