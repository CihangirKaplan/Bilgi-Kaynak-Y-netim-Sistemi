"""TKYS - Randevu Raporları: dönem, psikolog ve odaya göre randevu sayıları, iptal nedenleri, dağılımlar ve Excel çıktısı.

Danışanlar yalnızca kodla tutulduğundan rapor kişisel veri içermez (FR-008). Psikolog yalnızca kendi randevularını görür
(sunucu da bunu uygular).
"""

from datetime import datetime

import requests
from client.api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from client.randevu_rapor_excel import excel_dosyasi_olustur

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

DONEMLER = ["Bu Ay", "Geçen Ay", "Son 3 Ay", "Bu Yıl", "Geçen Yıl", "Tümü", "Tarih Aralığı"]
PSIKOLOG_SUTUNLARI = ["Psikolog", "Toplam", "Planlandı", "Tamamlandı", "Gelmedi", "İptal"]
NEDEN_SUTUNLARI = ["İptal Nedeni", "Sayı", "Pay"]
DAGILIM_SUTUNLARI = ["", "Sayı", "Pay"]


def yuzde_metni(oran):
    """0.4 -> '%40'; 0.3333 -> '%33,3'; hesaplanamıyorsa '—'."""
    if oran is None:
        return "—"
    deger = round(oran * 100, 1)
    metin = f"{int(deger)}" if deger == int(deger) else f"{deger:.1f}".replace(".", ",")
    return f"%{metin}"


class RandevuRaporlariEkrani(QWidget):
    NAVY = "#16294B"
    BLUE = "#285CE6"

    def __init__(self, api_url, token, psikolog_mu=False, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.psikolog_mu = psikolog_mu          # psikolog yalnızca kendi randevularını görür; psikolog süzgeci gizlenir
        self._son_params = None
        self._son_filtre = []
        self._yukleniyor = False

        self._arayuz_kur()
        self._listeleri_yukle()
        self.yenile()

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

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

    def _tablo(self, sutunlar, ilk_genis=True):
        tablo = QTableWidget()
        tablo.setColumnCount(len(sutunlar))
        tablo.setHorizontalHeaderLabels(sutunlar)
        tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tablo.setSelectionMode(QAbstractItemView.NoSelection)
        tablo.verticalHeader().setVisible(False)
        tablo.verticalHeader().setDefaultSectionSize(34)
        baslik = tablo.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeToContents)
        if ilk_genis:
            baslik.setSectionResizeMode(0, QHeaderView.Stretch)
        tablo.setStyleSheet("""
            QTableWidget { background: white; gridline-color: #E3EAF5; color: #243653; border: 1px solid #E3EAF5; border-radius: 8px; }
            QTableWidget::item { padding: 3px 8px; }
            QHeaderView::section { background: #E8F0FF; color: #16294B; font-weight: bold; padding: 8px 5px; border: none;
                border-right: 1px solid #D6E2F3; border-bottom: 1px solid #D6E2F3; }
        """)
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
        self.setObjectName("randevuRaporu")
        self.setStyleSheet("""
            QWidget#randevuRaporu { background: #EAF0FA; }
            QPushButton { background: #285CE6; color: white; border-radius: 8px; padding: 10px 18px; font-weight: bold; }
            QPushButton:hover { background: #1E4BC5; }
            QLabel { color: #243653; }
            QComboBox, QDateEdit { background: white; color: #243653; border: 1px solid #C9D6EA; border-radius: 6px; padding: 6px 8px; }
            /* Ana pencerenin genel stili her açılır kutuya min-width: 170px verir; süzgeç çubuğunda geçersiz kılınır. */
            QComboBox { min-width: 110px; }
            QDateEdit { min-width: 105px; }
            QComboBox:focus, QDateEdit:focus { border: 1px solid #285CE6; }
        """)
        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 16, 20, 20)
        ana.setSpacing(12)

        satir = QHBoxLayout()
        satir.setSpacing(8)
        satir.addWidget(QLabel("Dönem:"))
        self.donem = QComboBox()
        self.donem.addItems(DONEMLER)
        satir.addWidget(self.donem)
        # Tarih kutuları yalnızca "Tarih Aralığı" seçilince görünür (hazır dönemlerde gereksiz kalabalık yapmaz).
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
        self.etiket_psikolog = QLabel("Psikolog:")
        self.psikolog_sec = QComboBox()
        self.psikolog_sec.addItem("Tümü", None)
        satir.addWidget(self.etiket_psikolog)
        satir.addWidget(self.psikolog_sec)
        self.etiket_psikolog.setVisible(not self.psikolog_mu)
        self.psikolog_sec.setVisible(not self.psikolog_mu)
        satir.addWidget(QLabel("Oda:"))
        self.oda_sec = QComboBox()
        self.oda_sec.addItem("Tümü", None)
        satir.addWidget(self.oda_sec)
        satir.addStretch(1)
        # Rapor süzgeç değişince kendiliğinden yenilenir; ayrı bir "Raporu Getir" düğmesi yoktur.
        self.excel_btn = QPushButton("⬇ Excel'e Aktar")
        self.excel_btn.setMinimumWidth(150)
        self.excel_btn.setEnabled(False)
        self.excel_btn.setStyleSheet(
            "QPushButton { background: #16803C; } QPushButton:hover { background: #126A31; } QPushButton:disabled { background: #AEB9CC; }"
        )
        satir.addWidget(self.excel_btn)
        ana.addLayout(satir)

        kartlar = QHBoxLayout()
        kartlar.setSpacing(12)
        self.kartlar = {}
        for anahtar, baslik, renk in [
            ("toplam", "Toplam Randevu", self.NAVY), ("tamamlandi", "Tamamlanan", "#16803C"),
            ("gelmedi", "Gelmedi", "#BE185D"), ("iptal", "İptal Edilen", "#64748B"),
        ]:
            kart, deger, alt = self._kart(baslik, renk)
            self.kartlar[anahtar] = (deger, alt)
            kartlar.addWidget(kart, 1)
        ana.addLayout(kartlar)

        orta = QHBoxLayout()
        orta.setSpacing(14)
        self.tablo_psikolog = self._tablo(PSIKOLOG_SUTUNLARI)
        self.tablo_neden = self._tablo(NEDEN_SUTUNLARI)
        orta.addWidget(self._bolum("Psikolog Bazlı", self.tablo_psikolog), 3)
        orta.addWidget(self._bolum("İptal Nedenleri", self.tablo_neden), 2)
        ana.addLayout(orta, 1)

        alt = QHBoxLayout()
        alt.setSpacing(14)
        self.tablo_gorusme = self._tablo(["Görüşme Tipi", "Sayı", "Pay"])
        self.tablo_terapi = self._tablo(["Terapi Türü", "Sayı", "Pay"])
        self.tablo_yas = self._tablo(["Yaş Grubu", "Sayı", "Pay"])
        alt.addWidget(self._bolum("Görüşme Tipi (iptaller hariç)", self.tablo_gorusme), 1)
        alt.addWidget(self._bolum("Terapi Türü (iptaller hariç)", self.tablo_terapi), 1)
        alt.addWidget(self._bolum("Yaş Grubu (iptaller hariç)", self.tablo_yas), 1)
        ana.addLayout(alt, 1)

        self.durum_etiketi = QLabel("")
        self.durum_etiketi.setStyleSheet("color: #697993; font-size: 12px;")
        ana.addWidget(self.durum_etiketi)

        self.donem.currentIndexChanged.connect(self._donem_degisti)
        self.baslangic.dateChanged.connect(self._tarih_elle_degisti)
        self.bitis.dateChanged.connect(self._tarih_elle_degisti)
        self.psikolog_sec.currentIndexChanged.connect(self._psikolog_degisti)
        self.oda_sec.currentIndexChanged.connect(self._filtre_degisti)
        self.excel_btn.clicked.connect(self.excel_aktar)
        self._donem_tarihlerini_yaz()

    # ------------------------------------------------------------------ süzgeç listeleri
    def _secenekleri_getir(self, psikolog_id=None):
        """Sunucudan psikolog ve oda seçeneklerini alır; odalar yalnızca psikologlara atanmış aktif odalardır."""
        params = {"psikolog_id": int(psikolog_id)} if psikolog_id is not None else {}
        try:
            yanit = oturum_kontrollu_istek("GET", f"{self.api_url}/api/randevu-raporu/secenekler",
                                           headers=self._headers(), params=params, timeout=5)
            if yanit is not None and yanit.status_code == 200:
                return yanit.json()
        except (requests.RequestException, ValueError):
            pass
        return None

    def _kutuyu_doldur(self, kutu, kayitlar, ad_alani, kimlik, secili=None):
        kutu.blockSignals(True)
        kutu.clear()
        kutu.addItem("Tümü", None)
        for kayit in kayitlar:
            kutu.addItem(str(kayit.get(ad_alani)), kayit.get(kimlik))
        indeks = kutu.findData(secili) if secili is not None else -1
        kutu.setCurrentIndex(max(indeks, 0))
        kutu.blockSignals(False)

    def _listeleri_yukle(self):
        """Psikolog ve oda açılır listelerini doldurur (yüklenemezse yalnızca 'Tümü' kalır)."""
        veri = self._secenekleri_getir()
        if veri is None:
            return
        if not self.psikolog_mu:
            self._kutuyu_doldur(self.psikolog_sec, veri.get("psikologlar", []), "ad_soyad", "personel_id")
        self._kutuyu_doldur(self.oda_sec, veri.get("odalar", []), "oda_adi", "oda_id")

    def _psikolog_degisti(self, *_):
        """Psikolog seçilince oda listesi o psikologun odalarına daralır; sonra rapor bir kez yenilenir."""
        veri = self._secenekleri_getir(self.psikolog_sec.currentData())
        if veri is not None:
            self._kutuyu_doldur(self.oda_sec, veri.get("odalar", []), "oda_adi", "oda_id", secili=self.oda_sec.currentData())
        self.yenile()

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
        if secim == "Tarih Aralığı":
            return self.baslangic.date(), self.bitis.date()
        return None, None

    def _donem_tarihlerini_yaz(self):
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
        for parca in (self.etiket_baslangic, self.baslangic, self.etiket_bitis, self.bitis):
            parca.setVisible(ozel)

    def _donem_degisti(self, *_):
        self._donem_tarihlerini_yaz()
        self.yenile()

    def _tarih_elle_degisti(self, *_):
        if self.donem.currentText() == "Tarih Aralığı":
            self.yenile()

    def _filtre_degisti(self, *_):
        self.yenile()

    def _parametreler(self):
        bas, bit = self._donem_araligi()
        if bas is not None and bit < bas:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz.")
        params = {}
        if bas is not None:
            params["baslangic"] = bas.toString("yyyy-MM-dd")
            params["bitis"] = bit.toString("yyyy-MM-dd")
        if self.psikolog_sec.currentData() is not None and not self.psikolog_mu:
            params["psikolog_id"] = int(self.psikolog_sec.currentData())
        if self.oda_sec.currentData() is not None:
            params["oda_id"] = int(self.oda_sec.currentData())
        return params

    def _filtre_ozeti(self, params):
        if "baslangic" in params:
            gun = lambda metin: QDate.fromString(metin, "yyyy-MM-dd").toString("dd.MM.yyyy")
            donem = f"{gun(params['baslangic'])} - {gun(params['bitis'])}"
        else:
            donem = "Tümü"
        return [
            ("Dönem", donem),
            ("Psikolog", "Yalnızca kendi randevularınız" if self.psikolog_mu else self.psikolog_sec.currentText()),
            ("Oda", self.oda_sec.currentText()),
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
                yanit = oturum_kontrollu_istek("GET", f"{self.api_url}/api/randevu-raporu", headers=self._headers(), params=params, timeout=15)
                if oturum_hatasi_mi(yanit):
                    return
                yanit.raise_for_status()
                veri = yanit.json()
            except (requests.RequestException, ValueError) as hata:
                QMessageBox.warning(self, "Rapor Hatası", f"Randevu raporu alınamadı:\n{hata}")
                return
        finally:
            self._yukleniyor = False
        self._son_params = params
        self._son_filtre = self._filtre_ozeti(params)
        self.excel_btn.setEnabled(True)
        self._goster(veri)

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

    def _doldur(self, tablo, satirlar):
        tablo.setRowCount(len(satirlar))
        for i, satir in enumerate(satirlar):
            for j, deger in enumerate(satir):
                tablo.setItem(i, j, self._hucre(deger, ortala=j > 0, kalin=j == 0))

    def _goster(self, veri):
        ozet = veri.get("ozet", {})
        deger, alt = self.kartlar["toplam"]
        deger.setText(str(ozet.get("toplam", 0)))
        sonucsuz = ozet.get("sonucsuz_gecmis", 0)
        alt.setText(f"{ozet.get('danisan_sayisi', 0)} danışan · {ozet.get('planlandi', 0)} planlı"
                    + (f" · {sonucsuz} geçmiş randevunun sonucu girilmemiş" if sonucsuz else ""))
        deger, alt = self.kartlar["tamamlandi"]
        deger.setText(str(ozet.get("tamamlandi", 0)))
        alt.setText(f"Tamamlanma oranı {yuzde_metni(ozet.get('tamamlanma_orani'))}")
        deger, alt = self.kartlar["gelmedi"]
        deger.setText(str(ozet.get("gelmedi", 0)))
        alt.setText(f"Gelmeme oranı {yuzde_metni(ozet.get('gelmeme_orani'))}")
        deger, alt = self.kartlar["iptal"]
        deger.setText(str(ozet.get("iptal_edildi", 0)))
        alt.setText("")

        self._doldur(self.tablo_psikolog, [
            [p.get("ad"), p.get("toplam", 0), p.get("planlandi", 0), p.get("tamamlandi", 0), p.get("gelmedi", 0), p.get("iptal_edildi", 0)]
            for p in veri.get("psikologlar", [])
        ])
        sayim = lambda liste: [[o.get("etiket"), o.get("sayi", 0), yuzde_metni(o.get("pay"))] for o in liste]
        self._doldur(self.tablo_neden, sayim(veri.get("iptal_nedenleri", [])))
        dagilim = veri.get("dagilimlar", {})
        self._doldur(self.tablo_gorusme, sayim(dagilim.get("gorusme_tipi", [])))
        self._doldur(self.tablo_terapi, sayim(dagilim.get("terapi_turu", [])))
        self._doldur(self.tablo_yas, sayim(dagilim.get("yas_grubu", [])))

        donem = dict(self._son_filtre).get("Dönem", "")
        self.durum_etiketi.setText(f"{ozet.get('toplam', 0)} randevu raporlandı  ·  Dönem: {donem}")

    # ------------------------------------------------------------------ excel
    def excel_aktar(self):
        if self._son_params is None:
            QMessageBox.information(self, "Excel'e Aktar", "Önce raporu getirin.")
            return
        varsayilan = f"randevu_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        dosya_yolu, _ = QFileDialog.getSaveFileName(self, "Raporu Kaydet", varsayilan, "Excel Dosyası (*.xlsx)")
        if not dosya_yolu:
            return
        if not dosya_yolu.lower().endswith(".xlsx"):
            dosya_yolu += ".xlsx"
        try:
            yanit = oturum_kontrollu_istek(
                "GET", f"{self.api_url}/api/randevu-raporu", headers=self._headers(),
                params={**self._son_params, "detay": "true"}, timeout=30,
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
                self, "Kaydedilemedi",
                f"Dosya kaydedilemedi. Aynı adlı dosya Excel'de açık olabilir ya da klasöre yazma izniniz olmayabilir.\n{hata}",
            )
            return
        QMessageBox.information(self, "Excel'e Aktar", f"Rapor kaydedildi:\n{dosya_yolu}")
