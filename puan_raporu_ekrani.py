"""TKYS - Puan Raporu: öğrencilerin faaliyet puanlarına göre sıralaması ve Excel çıktısı.

Yıl sonunda ya da istenen her an, seçilen dönemde en yüksek puanlı öğrenciler en üstte olacak şekilde
sıralama gösterir. Pasif öğrenciler de listelenir ("Durum" sütununda belirtilir).
"""

from datetime import datetime

import requests
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)
from puan_rapor_excel import excel_dosyasi_olustur

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

DONEMLER = ["Bu Yıl", "Geçen Yıl", "Son 6 Ay", "Bu Ay", "Tümü", "Tarih Aralığı"]
TURLER = [("Tümü", None), ("Gönüllü Öğrenci", "GONULLU"), ("Danışma Masası Öğrencisi", "DANISMA_MASASI")]
DURUMLAR = [("Tümü", None), ("Aktif", "aktif"), ("Pasif", "pasif")]

MADALYALAR = {1: "🥇", 2: "🥈", 3: "🥉"}
SATIR_RENKLERI = {1: "#FFF8DC", 2: "#F1F4F9", 3: "#FCEFE2"}
PASIF_RENK = "#C0392B"

SUTUNLAR = ["Sıra", "Öğrenci", "Öğrenci No", "Tür", "Durum", "Faaliyet", "Toplam Puan", "Puan Dağılımı"]
SUTUN_SIRA, SUTUN_OGRENCI, SUTUN_NO, SUTUN_TUR, SUTUN_DURUM, SUTUN_FAALIYET, SUTUN_PUAN, SUTUN_CUBUK = range(8)


def puan_metni(deger):
    """1250 -> '1.250'; küsuratlıysa 2 basamak."""
    deger = float(deger or 0)
    if deger == int(deger):
        return f"{int(deger):,}".replace(",", ".")
    return f"{deger:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class PuanRaporuEkrani(QWidget):
    NAVY = "#16294B"
    BLUE = "#285CE6"

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)

        self.api_url = api_url.rstrip("/")
        self.token = token
        self._son_veri = None
        self._son_params = None
        self._son_filtre = []
        self._yukleniyor = False

        self._arayuz_kur()
        self.yenile()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    # ------------------------------------------------------------------ arayüz
    def _kart(self, baslik, renk):
        kart = QFrame()
        kart.setStyleSheet("""
            QFrame { background: white; border: 1px solid #E3EAF5; border-radius: 10px; }
            QLabel { border: none; }
        """)
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

    def _arayuz_kur(self):
        self.setObjectName("puanRaporu")
        self.setStyleSheet("""
            QWidget#puanRaporu { background: #EAF0FA; }
            QPushButton {
                background: #285CE6; color: white; border-radius: 8px;
                padding: 10px 18px; font-weight: bold;
            }
            QPushButton:hover { background: #1E4BC5; }
            QLabel { color: #243653; }
            QCheckBox { color: #243653; }
            QLineEdit, QComboBox, QDateEdit {
                background: white; color: #243653; border: 1px solid #C9D6EA;
                border-radius: 6px; padding: 6px 8px;
            }
            QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 1px solid #285CE6; }
        """)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 16, 20, 20)
        ana.setSpacing(12)

        # ---- 1. satır: dönem ve öğrenci filtreleri
        satir1 = QHBoxLayout()
        satir1.addWidget(QLabel("Dönem:"))
        self.donem = QComboBox()
        self.donem.addItems(DONEMLER)
        self.donem.setToolTip("Raporlanacak dönemi seçin. 'Bu Yıl' yıl sonu raporu için uygundur.")
        satir1.addWidget(self.donem)

        satir1.addWidget(QLabel("Başlangıç:"))
        self.baslangic = QDateEdit()
        self.baslangic.setCalendarPopup(True)
        self.baslangic.setDisplayFormat("dd.MM.yyyy")
        satir1.addWidget(self.baslangic)

        satir1.addWidget(QLabel("Bitiş:"))
        self.bitis = QDateEdit()
        self.bitis.setCalendarPopup(True)
        self.bitis.setDisplayFormat("dd.MM.yyyy")
        satir1.addWidget(self.bitis)

        satir1.addSpacing(10)
        satir1.addWidget(QLabel("Öğrenci Türü:"))
        self.tur_sec = QComboBox()
        for etiket, deger in TURLER:
            self.tur_sec.addItem(etiket, deger)
        satir1.addWidget(self.tur_sec)

        satir1.addWidget(QLabel("Durum:"))
        self.durum_sec = QComboBox()
        for etiket, deger in DURUMLAR:
            self.durum_sec.addItem(etiket, deger)
        satir1.addWidget(self.durum_sec)

        self.puansiz_kutusu = QCheckBox("Puanı olmayanları da göster")
        self.puansiz_kutusu.setChecked(True)
        self.puansiz_kutusu.setToolTip("Seçilen dönemde hiç faaliyeti olmayan öğrenciler listenin en altında görünür.")
        satir1.addWidget(self.puansiz_kutusu)
        satir1.addStretch(1)
        ana.addLayout(satir1)

        # ---- 2. satır: arama ve düğmeler
        satir2 = QHBoxLayout()
        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔎  Öğrenci adı ya da numarası ara…")
        self.arama.setClearButtonEnabled(True)
        self.arama.setToolTip("Yalnızca ekrandaki listeyi süzer; sıralama değişmez. Excel her zaman raporun tamamını içerir.")
        satir2.addWidget(self.arama, 1)

        self.yenile_btn = QPushButton("↻ Raporu Getir")
        satir2.addWidget(self.yenile_btn)

        self.excel_btn = QPushButton("⬇ Excel'e Aktar")
        self.excel_btn.setEnabled(False)
        self.excel_btn.setToolTip("Raporu dört sayfalı bir Excel dosyası olarak kaydeder.")
        self.excel_btn.setStyleSheet(
            "QPushButton { background: #16803C; } "
            "QPushButton:hover { background: #126A31; } "
            "QPushButton:disabled { background: #AEB9CC; }"
        )
        satir2.addWidget(self.excel_btn)
        ana.addLayout(satir2)

        # ---- özet kartları
        kart_satiri = QHBoxLayout()
        kart_satiri.setSpacing(12)
        self.kartlar = {}
        for anahtar, baslik, renk in [
            ("ogrenci", "Öğrenci", self.NAVY),
            ("toplam_puan", "Toplam Puan", self.BLUE),
            ("ortalama_puan", "Ortalama Puan", "#B86B08"),
            ("en_yuksek", "En Yüksek Puan", "#16803C"),
        ]:
            kart, deger, alt = self._kart(baslik, renk)
            self.kartlar[anahtar] = (deger, alt)
            kart_satiri.addWidget(kart, 1)
        ana.addLayout(kart_satiri)

        # ---- ilk üç
        self.podyum_kutusu = QWidget()
        podyum = QHBoxLayout(self.podyum_kutusu)
        podyum.setContentsMargins(0, 0, 0, 0)
        podyum.setSpacing(12)
        self.podyum = []
        for madalya_no in (1, 2, 3):
            kart = QFrame()
            kart.setStyleSheet(
                f"QFrame {{ background: {SATIR_RENKLERI[madalya_no]}; border: 1px solid #E3EAF5; border-radius: 10px; }} "
                "QLabel { border: none; background: transparent; }"
            )
            icerik = QHBoxLayout(kart)
            icerik.setContentsMargins(14, 10, 14, 10)
            simge = QLabel(MADALYALAR[madalya_no])
            simge.setStyleSheet("font-size: 28px;")
            metin = QLabel("")
            metin.setStyleSheet("font-size: 13px; font-weight: bold; color: #16294B;")
            metin.setWordWrap(True)
            icerik.addWidget(simge)
            icerik.addWidget(metin, 1)
            self.podyum.append((kart, metin))
            podyum.addWidget(kart, 1)
        ana.addWidget(self.podyum_kutusu)

        # ---- tablo
        self.tablo = QTableWidget()
        self.tablo.setColumnCount(len(SUTUNLAR))
        self.tablo.setHorizontalHeaderLabels(SUTUNLAR)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.verticalHeader().setDefaultSectionSize(38)
        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
        baslik.setSectionResizeMode(SUTUN_OGRENCI, QHeaderView.Stretch)
        baslik.setSectionResizeMode(SUTUN_CUBUK, QHeaderView.Stretch)
        self.tablo.setStyleSheet("""
            QTableWidget {
                background: white; gridline-color: #E3EAF5; color: #243653;
                border: 1px solid #E3EAF5; border-radius: 8px;
            }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected { background: #DCE8FF; color: #16294B; }
            QHeaderView::section {
                background: #E8F0FF; color: #16294B; font-weight: bold; padding: 9px 5px;
                border: none; border-right: 1px solid #D6E2F3; border-bottom: 1px solid #D6E2F3;
            }
        """)
        ana.addWidget(self.tablo, 1)

        self.bos_mesaj = QLabel("")
        self.bos_mesaj.setAlignment(Qt.AlignCenter)
        self.bos_mesaj.setStyleSheet("color: #697993; font-size: 13px; padding: 14px;")
        self.bos_mesaj.hide()
        ana.addWidget(self.bos_mesaj)

        self.durum_etiketi = QLabel("")
        self.durum_etiketi.setStyleSheet("color: #697993; font-size: 12px;")
        ana.addWidget(self.durum_etiketi)

        # ---- olaylar (bound method; lambda kullanılmaz)
        self.donem.currentIndexChanged.connect(self._donem_degisti)
        self.baslangic.dateChanged.connect(self._tarih_elle_degisti)
        self.bitis.dateChanged.connect(self._tarih_elle_degisti)
        self.tur_sec.currentIndexChanged.connect(self._filtre_degisti)
        self.durum_sec.currentIndexChanged.connect(self._filtre_degisti)
        self.puansiz_kutusu.toggled.connect(self._filtre_degisti)
        self.arama.textChanged.connect(self._aramayi_uygula)
        self.yenile_btn.clicked.connect(self.yenile)
        self.excel_btn.clicked.connect(self.excel_aktar)

        self._donem_tarihlerini_yaz()

    # ------------------------------------------------------------------ filtreler
    def _donem_araligi(self):
        """Seçili dönemin (başlangıç, bitiş) QDate çifti; 'Tümü' için (None, None)."""
        bugun = QDate.currentDate()
        secim = self.donem.currentText()
        if secim == "Bu Yıl":
            return QDate(bugun.year(), 1, 1), QDate(bugun.year(), 12, 31)
        if secim == "Geçen Yıl":
            return QDate(bugun.year() - 1, 1, 1), QDate(bugun.year() - 1, 12, 31)
        if secim == "Son 6 Ay":
            return bugun.addMonths(-6), bugun
        if secim == "Bu Ay":
            ilk = QDate(bugun.year(), bugun.month(), 1)
            return ilk, ilk.addMonths(1).addDays(-1)
        if secim == "Tarih Aralığı":
            return self.baslangic.date(), self.bitis.date()
        return None, None

    def _donem_tarihlerini_yaz(self):
        """Hazır dönem seçilince tarih kutularını doldurur; yalnızca 'Tarih Aralığı'nda düzenlenebilir."""
        secim = self.donem.currentText()
        if secim != "Tarih Aralığı":
            bas, bit = self._donem_araligi()
            self.baslangic.blockSignals(True)
            self.bitis.blockSignals(True)
            self.baslangic.setDate(bas or QDate.currentDate().addYears(-1))
            self.bitis.setDate(bit or QDate.currentDate())
            self.baslangic.blockSignals(False)
            self.bitis.blockSignals(False)
        ozel = secim == "Tarih Aralığı"
        self.baslangic.setEnabled(ozel)
        self.bitis.setEnabled(ozel)

    def _donem_degisti(self, *args):
        self._donem_tarihlerini_yaz()
        self.yenile()

    def _tarih_elle_degisti(self, *args):
        if self.donem.currentText() == "Tarih Aralığı":
            self.yenile()

    def _filtre_degisti(self, *args):
        self.yenile()

    def _parametreler(self):
        bas, bit = self._donem_araligi()
        if bas is not None and bit < bas:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")

        params = {"puansizlari_goster": "true" if self.puansiz_kutusu.isChecked() else "false"}
        if bas is not None:
            params["baslangic"] = bas.toString("yyyy-MM-dd")
            params["bitis"] = bit.toString("yyyy-MM-dd")
        if self.tur_sec.currentData() is not None:
            params["tur"] = self.tur_sec.currentData()
        if self.durum_sec.currentData() is not None:
            params["durum"] = self.durum_sec.currentData()
        return params

    def _filtre_ozeti(self, params):
        if "baslangic" in params:
            gun = lambda metin: QDate.fromString(metin, "yyyy-MM-dd").toString("dd.MM.yyyy")
            donem = f"{gun(params['baslangic'])} - {gun(params['bitis'])}"
        else:
            donem = "Tümü"
        return [
            ("Dönem", donem),
            ("Öğrenci Türü", self.tur_sec.currentText()),
            ("Öğrenci Durumu", self.durum_sec.currentText()),
            ("Puanı Olmayanlar", "Gösterilir" if params["puansizlari_goster"] == "true" else "Gizlenir"),
        ]

    # ------------------------------------------------------------------ veri
    def yenile(self):
        if self._yukleniyor:
            return
        try:
            params = self._parametreler()
        except ValueError as hata:
            QMessageBox.warning(self, "Geçersiz Tarih", str(hata))
            return

        self._yukleniyor = True
        try:
            try:
                yanit = oturum_kontrollu_istek(
                    "GET", f"{self.api_url}/api/puan-raporu",
                    headers=self._headers(), params=params, timeout=15,
                )
                if oturum_hatasi_mi(yanit):
                    return
                yanit.raise_for_status()
                veri = yanit.json()
            except (requests.RequestException, ValueError) as hata:
                QMessageBox.warning(self, "Rapor Hatası", f"Puan raporu alınamadı:\n{hata}")
                return
        finally:
            self._yukleniyor = False

        # Excel, ekranda gösterilen raporun filtreleriyle üretilir.
        self._son_veri = veri
        self._son_params = params
        self._son_filtre = self._filtre_ozeti(params)
        self.excel_btn.setEnabled(True)
        self._goster(veri)

    def _goster(self, veri):
        ozet = veri.get("ozet", {})
        ogrenciler = veri.get("ogrenciler", [])

        deger, alt = self.kartlar["ogrenci"]
        deger.setText(str(ozet.get("ogrenci_sayisi", len(ogrenciler))))
        alt.setText(f"{ozet.get('puanli_ogrenci_sayisi', 0)} öğrencinin puanı var")

        deger, alt = self.kartlar["toplam_puan"]
        deger.setText(puan_metni(ozet.get("toplam_puan", 0)))
        alt.setText(f"{ozet.get('faaliyet_kaydi_sayisi', 0)} faaliyet kaydı")

        deger, alt = self.kartlar["ortalama_puan"]
        deger.setText(puan_metni(ozet.get("ortalama_puan", 0)))
        alt.setText("puanı olan öğrenciler için")

        deger, alt = self.kartlar["en_yuksek"]
        deger.setText(puan_metni(ozet.get("en_yuksek_puan", 0)))
        alt.setText(", ".join(ozet.get("en_yuksek_ogrenciler", [])) or "—")

        self._podyumu_doldur(ogrenciler)
        self._tabloyu_doldur(ogrenciler)
        self._aramayi_uygula()

    def _podyumu_doldur(self, ogrenciler):
        ilk_uc = [o for o in ogrenciler if o.get("sira") is not None and o["sira"] <= 3][:3]
        self.podyum_kutusu.setVisible(bool(ilk_uc))
        for sira_no, (kart, metin) in enumerate(self.podyum):
            if sira_no < len(ilk_uc):
                o = ilk_uc[sira_no]
                kart.show()
                metin.setText(f"{o['ad_soyad']}\n{puan_metni(o['toplam_puan'])} puan")
            else:
                kart.hide()

    def _hucre(self, satir, sutun, deger, renk=None, kalin=False, ortala=False):
        hucre = QTableWidgetItem(str(deger))
        hucre.setFlags(hucre.flags() & ~Qt.ItemIsEditable)
        if renk:
            hucre.setForeground(QColor(renk))
        if kalin:
            font = hucre.font()
            font.setBold(True)
            hucre.setFont(font)
        if ortala:
            hucre.setTextAlignment(Qt.AlignCenter)
        self.tablo.setItem(satir, sutun, hucre)
        return hucre

    @staticmethod
    def _sira_metni(sira):
        if sira is None:
            return "—"
        return f"{MADALYALAR[sira]} {sira}" if sira in MADALYALAR else str(sira)

    def _tabloyu_doldur(self, ogrenciler):
        self.tablo.setRowCount(len(ogrenciler))
        en_yuksek = max((o["toplam_puan"] for o in ogrenciler), default=0)

        for satir, o in enumerate(ogrenciler):
            pasif = not o.get("aktif_mi", True)
            self._hucre(satir, SUTUN_SIRA, self._sira_metni(o.get("sira")), kalin=True, ortala=True)
            self._hucre(satir, SUTUN_OGRENCI, o["ad_soyad"], kalin=True)
            self._hucre(satir, SUTUN_NO, o["ogrenci_numarasi"])
            self._hucre(satir, SUTUN_TUR, o.get("tur_etiketi") or o.get("tur", ""))
            self._hucre(satir, SUTUN_DURUM, "Pasif" if pasif else "Aktif",
                        renk=PASIF_RENK if pasif else "#16803C", kalin=True, ortala=True)
            self._hucre(satir, SUTUN_FAALIYET, o.get("faaliyet_sayisi", 0), ortala=True)
            self._hucre(satir, SUTUN_PUAN, puan_metni(o["toplam_puan"]), kalin=True, ortala=True)

            # Puanın en yüksek puana oranını gösteren çubuk; metin yerine görsel karşılaştırma sağlar.
            cubuk = QProgressBar()
            cubuk.setRange(0, 100)
            cubuk.setValue(int(round(o["toplam_puan"] / en_yuksek * 100)) if en_yuksek else 0)
            cubuk.setTextVisible(False)
            cubuk.setFixedHeight(12)
            cubuk.setStyleSheet(
                "QProgressBar { background: #E8EEF8; border: none; border-radius: 6px; } "
                f"QProgressBar::chunk {{ background: {'#C9D3E6' if pasif else self.BLUE}; border-radius: 6px; }}"
            )
            kap = QWidget()
            kap_duzeni = QHBoxLayout(kap)
            kap_duzeni.setContentsMargins(10, 0, 10, 0)
            kap_duzeni.addWidget(cubuk, 1, Qt.AlignVCenter)       # çubuk satırın ortasında dursun
            self.tablo.setCellWidget(satir, SUTUN_CUBUK, kap)

            zemin = SATIR_RENKLERI.get(o.get("sira"))
            if zemin:
                for sutun in range(SUTUN_CUBUK):
                    self.tablo.item(satir, sutun).setBackground(QColor(zemin))

    # ------------------------------------------------------------------ arama
    def _aramayi_uygula(self, *args):
        """Yalnızca ekrandaki satırları gizler/gösterir; sıra numaraları ve Excel etkilenmez."""
        aranan = self.arama.text().strip().casefold()
        gorunen = 0
        toplam = self.tablo.rowCount()
        for satir in range(toplam):
            ad = self.tablo.item(satir, SUTUN_OGRENCI).text().casefold()
            numara = self.tablo.item(satir, SUTUN_NO).text().casefold()
            eslesti = not aranan or aranan in ad or aranan in numara
            self.tablo.setRowHidden(satir, not eslesti)
            gorunen += 1 if eslesti else 0

        if toplam == 0:
            self.bos_mesaj.setText("Bu filtrelerle öğrenci bulunamadı. Dönemi ya da filtreleri değiştirmeyi deneyin.")
        elif gorunen == 0:
            self.bos_mesaj.setText("Aramanıza uyan öğrenci yok.")
        self.bos_mesaj.setVisible(gorunen == 0)

        donem = self._son_filtre[0][1] if self._son_filtre else "—"
        if aranan:
            self.durum_etiketi.setText(f"{gorunen} / {toplam} öğrenci gösteriliyor  ·  Dönem: {donem}")
        else:
            self.durum_etiketi.setText(f"{toplam} öğrenci listeleniyor  ·  Dönem: {donem}")

    # ------------------------------------------------------------------ excel
    def excel_aktar(self):
        if self._son_params is None:
            QMessageBox.information(self, "Excel'e Aktar", "Önce raporu getirin.")
            return

        varsayilan = f"puan_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        dosya_yolu, _ = QFileDialog.getSaveFileName(
            self, "Raporu Kaydet", varsayilan, "Excel Dosyası (*.xlsx)"
        )
        if not dosya_yolu:
            return
        if not dosya_yolu.lower().endswith(".xlsx"):
            dosya_yolu += ".xlsx"

        # Ayrıntı sayfaları için kayıt kayıt veri, ekrandaki raporla aynı filtrelerle istenir.
        try:
            yanit = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/puan-raporu",
                headers=self._headers(), params={**self._son_params, "detay": "true"}, timeout=30,
            )
            if oturum_hatasi_mi(yanit):
                return
            yanit.raise_for_status()
            veri = yanit.json()
        except (requests.RequestException, ValueError) as hata:
            QMessageBox.warning(self, "Rapor Hatası", f"Excel için rapor verisi alınamadı:\n{hata}")
            return

        try:
            excel_dosyasi_olustur(veri, self._son_filtre, dosya_yolu)
        except OSError as hata:
            QMessageBox.warning(
                self,
                "Kaydedilemedi",
                "Dosya kaydedilemedi. Aynı adlı dosya Excel'de açık olabilir "
                f"ya da klasöre yazma izniniz olmayabilir.\n{hata}",
            )
            return

        QMessageBox.information(self, "Excel'e Aktar", f"Rapor kaydedildi:\n{dosya_yolu}")
