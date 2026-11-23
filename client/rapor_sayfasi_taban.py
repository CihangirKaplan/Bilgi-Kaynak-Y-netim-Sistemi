"""TKYS - Ayrıntılı rapor sayfaları için ortak taban.

Cihaz Raporları, Danışma Masası Raporları ve Randevu Raporları ile aynı düzeni kullanır: üstte süzgeç çubuğu (dönem + sayfaya özel
süzgeçler + Excel düğmesi), altında özet kartları ve tablolar. Süzgeç değişince rapor kendiliğinden yenilenir.

Alt sınıf şunları tanımlar: RAPOR_YOLU, KARTLAR, TABLO_DIZILIMI ve gerekirse ek süzgeçler, goster() ve excel_yaz().
"""
from datetime import datetime

import requests
from client.tablo_tasarimi import cihaz_hucresi_uygula
from client.api_yoneticisi import istek_hatasi_metni, oturum_hatasi_mi, oturum_kontrollu_istek

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from client.tablo_siralama import siralanabilir_yap

DONEMLER = ["Bu Ay", "Geçen Ay", "Son 3 Ay", "Bu Yıl", "Geçen Yıl", "Tarih Aralığı"]
EN_FAZLA_GUN = 366


def yuzde_metni(oran):
    """0.4 -> '%40'; 0.3333 -> '%33,3'; hesaplanamıyorsa '—'."""
    if oran is None:
        return "—"
    deger = round(oran * 100, 1)
    metin = f"{int(deger)}" if deger == int(deger) else f"{deger:.1f}".replace(".", ",")
    return f"%{metin}"


def sayi_metni(deger):
    """12.0 -> '12'; 12.5 -> '12,5' (Türkçe ondalık)."""
    if deger is None:
        return "—"
    deger = float(deger)
    return f"{int(deger)}" if deger == int(deger) else f"{deger:.1f}".replace(".", ",")


class RaporSayfasiTaban(QWidget):
    NAVY = "#16294B"
    BLUE = "#285CE6"

    NESNE_ADI = "ayrintiliRapor"
    BASLIK = "Rapor"
    RAPOR_YOLU = ""
    DOSYA_ONEKI = "rapor"
    DONEM_VAR = True
    HATA_BASLIGI = "Rapor Hatası"
    # [(anahtar, başlık, renk)]
    KARTLAR = []
    # Satır satır tablo dizilimi: [[(anahtar, başlık, [sütunlar], genişlik payı), ...], ...]
    TABLO_DIZILIMI = []

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self._son_params = None
        self._son_filtre = []
        self._yukleniyor = False
        self.kartlar = {}
        self.tablolar = {}
        self._arayuz_kur()
        self.ek_listeleri_yukle()
        self.yenile()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # ------------------------------------------------------------------ alt sınıfın doldurduğu noktalar
    def ek_suzgecleri_olustur(self, satir):
        """Süzgeç çubuğuna sayfaya özel kutular ekler (QHBoxLayout alır)."""

    def ek_listeleri_yukle(self):
        """Açılır listeleri (cihaz, oda, rol...) doldurur."""

    def ek_parametreler(self):
        return {}

    def ek_filtre_ozeti(self):
        return []

    def goster(self, veri):
        raise NotImplementedError

    def excel_yaz(self, veri, filtre, dosya_yolu):
        raise NotImplementedError

    # ------------------------------------------------------------------ arayüz
    def _kart(self, baslik, renk):
        kart = QFrame()
        kart.setStyleSheet("QFrame { background: white; border: 1px solid #E3EAF5; border-radius: 10px; } QLabel { border: none; }")
        icerik = QVBoxLayout(kart)
        icerik.setContentsMargins(15, 12, 15, 12)
        etiket = QLabel(baslik)
        etiket.setStyleSheet("color: #697993; font-size: 12px;")
        deger = QLabel("—")
        deger.setStyleSheet(f"color: {renk}; font-size: 24px; font-weight: bold;")
        alt = QLabel("")
        alt.setStyleSheet("color: #8A98B0; font-size: 11px;")
        alt.setWordWrap(True)
        icerik.addWidget(etiket)
        icerik.addWidget(deger)
        icerik.addWidget(alt)
        return kart, deger, alt

    def _tablo(self, sutunlar):
        tablo = QTableWidget()
        siralanabilir_yap(tablo)
        tablo.setColumnCount(len(sutunlar))
        tablo.setHorizontalHeaderLabels(sutunlar)
        tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tablo.setSelectionMode(QAbstractItemView.NoSelection)
        tablo.verticalHeader().setVisible(False)
        tablo.verticalHeader().setDefaultSectionSize(34)
        baslik = tablo.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(0, QHeaderView.Stretch)
        tablo.setStyleSheet("""
            QTableWidget { background: white; gridline-color: #E3EAF5; color: #243653; border: 1px solid #E3EAF5; border-radius: 8px; }
            QTableWidget::item { padding: 3px 8px; }
            QHeaderView::section { background: #E8F0FF; color: #16294B; font-weight: bold; padding: 8px 5px; border: none;
                border-right: 1px solid #D6E2F3; border-bottom: 1px solid #D6E2F3; }
        """)
        for sira, ad in enumerate(sutunlar):
            if ad == "Cihaz":                                                  # "KOD - Ad" -> ad üstte (kalın), envanter kodu altta (gri)
                cihaz_hucresi_uygula(tablo, sira)
        return tablo

    def _bolum(self, baslik, tablo):
        kutu = QWidget()
        yerlesim = QVBoxLayout(kutu)
        yerlesim.setContentsMargins(0, 0, 0, 0)
        yerlesim.setSpacing(6)
        etiket = QLabel(baslik)
        etiket.setStyleSheet("color: #16294B; font-size: 13px; font-weight: bold;")
        yerlesim.addWidget(etiket)
        yerlesim.addWidget(tablo, 1)
        return kutu

    def _arayuz_kur(self):
        self.setObjectName(self.NESNE_ADI)
        self.setStyleSheet(f"""
            QWidget#{self.NESNE_ADI} {{ background: #EAF0FA; }}
            QPushButton {{ background: #285CE6; color: white; border-radius: 8px; padding: 10px 18px; font-weight: bold; }}
            QPushButton:hover {{ background: #1E4BC5; }}
            QLabel {{ color: #243653; }}
            QComboBox, QDateEdit {{ background: white; color: #243653; border: 1px solid #C9D6EA; border-radius: 6px; padding: 6px 8px; }}
            /* Ana pencerenin genel stili her açılır kutuya min-width: 170px verir; süzgeç çubuğunda geçersiz kılınır. */
            QComboBox {{ min-width: 110px; }}
            QDateEdit {{ min-width: 105px; }}
            QComboBox:focus, QDateEdit:focus {{ border: 1px solid #285CE6; }}
        """)
        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 16, 20, 20)
        ana.setSpacing(12)

        satir = QHBoxLayout()
        satir.setSpacing(8)
        if self.DONEM_VAR:
            satir.addWidget(QLabel("Dönem:"))
            self.donem = QComboBox()
            self.donem.addItems(DONEMLER)
            satir.addWidget(self.donem)
            self.etiket_baslangic = QLabel("Başlangıç:")
            self.baslangic = QDateEdit()
            self.baslangic.setCalendarPopup(True)
            self.baslangic.setDisplayFormat("dd.MM.yyyy")
            self.etiket_bitis = QLabel("Bitiş:")
            self.bitis = QDateEdit()
            self.bitis.setCalendarPopup(True)
            self.bitis.setDisplayFormat("dd.MM.yyyy")
            for parca in (self.etiket_baslangic, self.baslangic, self.etiket_bitis, self.bitis):
                satir.addWidget(parca)
            satir.addSpacing(10)
        self.ek_suzgecleri_olustur(satir)
        satir.addStretch(1)
        self.excel_btn = QPushButton("⬇ Excel'e Aktar")
        self.excel_btn.setMinimumWidth(150)
        self.excel_btn.setEnabled(False)
        self.excel_btn.setStyleSheet(
            "QPushButton { background: #16803C; } QPushButton:hover { background: #126A31; } QPushButton:disabled { background: #AEB9CC; }"
        )
        satir.addWidget(self.excel_btn)
        ana.addLayout(satir)

        if self.KARTLAR:
            kartlar = QHBoxLayout()
            kartlar.setSpacing(12)
            for anahtar, baslik, renk in self.KARTLAR:
                kart, deger, alt = self._kart(baslik, renk)
                self.kartlar[anahtar] = (deger, alt)
                kartlar.addWidget(kart, 1)
            ana.addLayout(kartlar)

        for tablo_satiri in self.TABLO_DIZILIMI:
            yatay = QHBoxLayout()
            yatay.setSpacing(14)
            for anahtar, baslik, sutunlar, pay in tablo_satiri:
                tablo = self._tablo(sutunlar)
                self.tablolar[anahtar] = tablo
                yatay.addWidget(self._bolum(baslik, tablo), pay)
            ana.addLayout(yatay, 1)

        self.durum_etiketi = QLabel("")
        self.durum_etiketi.setStyleSheet("color: #697993; font-size: 12px;")
        self.durum_etiketi.setWordWrap(True)
        ana.addWidget(self.durum_etiketi)

        if self.DONEM_VAR:
            self.donem.currentIndexChanged.connect(self._donem_degisti)
            self.baslangic.dateChanged.connect(self._tarih_elle_degisti)
            self.bitis.dateChanged.connect(self._tarih_elle_degisti)
            self._donem_tarihlerini_yaz()
        self.excel_btn.clicked.connect(self.excel_aktar)

    # ------------------------------------------------------------------ dönem
    def _donem_araligi(self):
        bugun = QDate.currentDate()
        secim = self.donem.currentText()
        if secim == "Bu Ay":
            ilk = QDate(bugun.year(), bugun.month(), 1)
            return ilk, ilk.addMonths(1).addDays(-1)
        if secim == "Geçen Ay":
            ilk = QDate(bugun.year(), bugun.month(), 1).addMonths(-1)
            return ilk, ilk.addMonths(1).addDays(-1)
        if secim == "Son 3 Ay":
            return bugun.addMonths(-3), bugun
        if secim == "Bu Yıl":
            return QDate(bugun.year(), 1, 1), QDate(bugun.year(), 12, 31)
        if secim == "Geçen Yıl":
            return QDate(bugun.year() - 1, 1, 1), QDate(bugun.year() - 1, 12, 31)
        return self.baslangic.date(), self.bitis.date()

    def _donem_tarihlerini_yaz(self):
        ozel = self.donem.currentText() == "Tarih Aralığı"
        if not ozel:
            bas, bit = self._donem_araligi()
            for kutu, deger in ((self.baslangic, bas), (self.bitis, bit)):
                kutu.blockSignals(True)
                kutu.setDate(deger)
                kutu.blockSignals(False)
        for parca in (self.etiket_baslangic, self.baslangic, self.etiket_bitis, self.bitis):
            parca.setVisible(ozel)

    def _donem_degisti(self, *_):
        self._donem_tarihlerini_yaz()
        self.yenile()

    def _tarih_elle_degisti(self, *_):
        if self.donem.currentText() == "Tarih Aralığı":
            self.yenile()

    def suzgec_degisti(self, *_):
        self.yenile()

    def _parametreler(self):
        params = {}
        if self.DONEM_VAR:
            bas, bit = self._donem_araligi()
            if bit < bas:
                raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
            if bas.daysTo(bit) + 1 > EN_FAZLA_GUN:
                raise ValueError(f"Tarih aralığı en fazla {EN_FAZLA_GUN} gün olabilir.")
            params["baslangic"] = bas.toString("yyyy-MM-dd")
            params["bitis"] = bit.toString("yyyy-MM-dd")
        params.update(self.ek_parametreler())
        return params

    def _filtre_ozeti(self, params):
        sonuc = []
        if self.DONEM_VAR:
            gun = lambda metin: QDate.fromString(metin, "yyyy-MM-dd").toString("dd.MM.yyyy")
            sonuc.append(("Dönem", f"{gun(params['baslangic'])} - {gun(params['bitis'])}"))
        return sonuc + self.ek_filtre_ozeti()

    # ------------------------------------------------------------------ veri
    def veriyi_getir(self, params, zaman_asimi=15):
        yanit = oturum_kontrollu_istek("GET", f"{self.api_url}{self.RAPOR_YOLU}", headers=self._headers(), params=params, timeout=zaman_asimi)
        if oturum_hatasi_mi(yanit):
            return None
        yanit.raise_for_status()
        return yanit.json()

    def yenile(self):
        if self._yukleniyor:
            return
        try:
            params = self._parametreler()
        except ValueError as hata:
            QMessageBox.warning(self, "Geçersiz Süzgeç", str(hata))
            return
        self._yukleniyor = True
        try:
            try:
                veri = self.veriyi_getir(params)
            except (requests.RequestException, ValueError) as hata:
                QMessageBox.warning(self, self.HATA_BASLIGI, f"{self.BASLIK} alınamadı:\n{istek_hatasi_metni(hata)}")
                return
        finally:
            self._yukleniyor = False
        if veri is None:
            return
        self._son_params = params
        self._son_filtre = self._filtre_ozeti(params)
        self.excel_btn.setEnabled(True)
        self.goster(veri)

    @staticmethod
    def _hucre(metin, ortala=False, kalin=False):
        oge = QTableWidgetItem(str(metin))
        if ortala:
            oge.setTextAlignment(Qt.AlignCenter)
        if kalin:
            font = oge.font()
            font.setBold(True)
            oge.setFont(font)
        return oge

    def doldur(self, anahtar, satirlar):
        tablo = self.tablolar[anahtar]
        tablo.setRowCount(len(satirlar))
        for i, satir in enumerate(satirlar):
            for j, deger in enumerate(satir):
                tablo.setItem(i, j, self._hucre(deger, ortala=j > 0, kalin=j == 0))

    def kart_yaz(self, anahtar, deger, alt=""):
        etiket, alt_etiket = self.kartlar[anahtar]
        etiket.setText(str(deger))
        alt_etiket.setText(alt)

    # ------------------------------------------------------------------ excel
    def excel_aktar(self):
        if self._son_params is None:
            QMessageBox.information(self, "Excel'e Aktar", "Önce raporu getirin.")
            return
        varsayilan = f"{self.DOSYA_ONEKI}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        dosya_yolu, _ = QFileDialog.getSaveFileName(self, "Raporu Kaydet", varsayilan, "Excel Dosyası (*.xlsx)")
        if not dosya_yolu:
            return
        if not dosya_yolu.lower().endswith(".xlsx"):
            dosya_yolu += ".xlsx"
        try:
            veri = self.veriyi_getir({**self._son_params, "detay": "true"}, zaman_asimi=30)
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(self, self.HATA_BASLIGI, f"Excel için rapor verisi alınamadı:\n{istek_hatasi_metni(hata)}")
            return
        if veri is None:
            return
        try:
            self.excel_yaz(veri, self._son_filtre, dosya_yolu)
        except OSError as hata:
            QMessageBox.warning(
                self, "Kaydedilemedi",
                f"Dosya kaydedilemedi. Aynı adlı dosya Excel'de açık olabilir ya da klasöre yazma izniniz olmayabilir.\n{hata}",
            )
            return
        QMessageBox.information(self, "Excel'e Aktar", f"Rapor kaydedildi:\n{dosya_yolu}")
