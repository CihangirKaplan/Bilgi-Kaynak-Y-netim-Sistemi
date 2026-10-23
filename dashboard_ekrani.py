import datetime
import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
                               QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

DURUM_METIN = {
    "PLANLANDI": ("Planlandı", "#1D4ED8", "#DBEAFE"),
    "TAMAMLANDI": ("Tamamlandı", "#15803D", "#DCFCE7"),
    "IPTAL_EDILDI": ("İptal", "#B91C1C", "#FEE2E2"),
}

TABLO_STIL = """
    QTableWidget { background: white; border: none; gridline-color: transparent;
                   font-size: 13px; color: #0F2552; }
    QTableWidget::item { padding: 6px; border-bottom: 1px solid #EEF2FA; }
    QHeaderView::section { background: #F3F7FF; color: #6B7FA8; padding: 9px;
                           font-size: 11px; font-weight: 800; border: none; }
"""


def _tablo_olustur(kolonlar, yukseklik):
    tablo = QTableWidget(0, len(kolonlar))
    tablo.setHorizontalHeaderLabels(kolonlar)
    tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tablo.verticalHeader().setVisible(False)
    tablo.setEditTriggers(QTableWidget.NoEditTriggers)
    tablo.setSelectionBehavior(QTableWidget.SelectRows)
    tablo.setShowGrid(False)
    tablo.setFixedHeight(yukseklik)
    tablo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    tablo.setStyleSheet(TABLO_STIL)
    return tablo


def _item(metin, ortala=True, renk=None, arka=None, kalin=False):
    item = QTableWidgetItem(metin)
    if ortala:
        item.setTextAlignment(Qt.AlignCenter)
    if renk:
        item.setForeground(QColor(renk))
    if arka:
        item.setBackground(QColor(arka))
    if kalin:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    return item


class DashboardEkrani(QWidget):
    """Ana kontrol paneli gövdesi.

    cihaz_ozeti=True  -> cihaz kartları + yaklaşan bakım/kalibrasyon tablosu da gösterilir
                         (müdür, admin, memur).
    Bugünkü randevu listesi her rolde gösterilir.
    """

    def __init__(self, api_url, token, cihaz_ozeti=True):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.cihaz_ozeti = cihaz_ozeti
        self.basliklar = {"Authorization": f"Bearer {token}"}

        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(20)

        # ---- 1. ÖZET KARTLARI ----
        self.lbl_degerler = {}
        kartlar = [("BUGÜNKÜ RANDEVULAR", "bugunku_randevu_sayisi", "Bugün planlanan seans", "#1D4ED8")]
        if cihaz_ozeti:
            kartlar += [
                ("KULLANILABİLİR CİHAZ", "aktif_cihaz", "Şu an kullanıma hazır", "#15803D"),
                ("BAKIMDAKİ CİHAZ", "bakimdaki_cihaz", "Geçici olarak kullanılamaz", "#B45309"),
                ("ARIZALI CİHAZ", "arizali_cihaz", "Onarım bekleyen", "#B91C1C"),
                ("AÇIK ARIZA KAYDI", "acik_ariza_sayisi", "Çözülmemiş bildirim", "#B91C1C"),
                ("TOPLAM CİHAZ", "toplam_cihaz", "Envanterdeki tüm cihazlar", "#6D28D9"),
            ]
        grid = QGridLayout()
        grid.setSpacing(18)
        for i, (baslik, anahtar, alt, renk) in enumerate(kartlar):
            kart, lbl = self._kart(baslik, alt, renk)
            self.lbl_degerler[anahtar] = lbl
            grid.addWidget(kart, i // 3, i % 3)
        for c in range(3):
            grid.setColumnStretch(c, 1)
        ana.addLayout(grid)

        # ---- 2. BUGÜNKÜ RANDEVULAR ----
        bugun = datetime.date.today()
        self.lbl_randevu_baslik = QLabel(
            f"📅  Bugünkü Randevular  —  {bugun.day} {AYLAR[bugun.month - 1]} {bugun.year}")
        self.tablo_randevu = _tablo_olustur(
            ["SAAT", "DANIŞAN KODU", "PSİKOLOG", "ODA", "DURUM"], 220)
        self.lbl_randevu_bos = QLabel("Bugün için kayıtlı randevu bulunmuyor.")
        ana.addWidget(self._panel(self.lbl_randevu_baslik, self.tablo_randevu, self.lbl_randevu_bos))

        # ---- 3. YAKLAŞAN BAKIM / KALİBRASYON ----
        if cihaz_ozeti:
            self.tablo_islem = _tablo_olustur(
                ["CİHAZ", "İŞLEM", "SON TARİH", "KALAN"], 200)
            self.lbl_islem_bos = QLabel("Önümüzdeki 60 gün içinde bakım veya kalibrasyon yok.")
            ana.addWidget(self._panel(
                QLabel("🛠️  Yaklaşan Bakım ve Kalibrasyonlar  (önümüzdeki 60 gün)"),
                self.tablo_islem, self.lbl_islem_bos))

        self.verileri_yukle()

    # ------------------------------------------------------------------
    def _kart(self, baslik, alt, renk):
        kart = QFrame()
        kart.setObjectName("kart")
        lay = QVBoxLayout(kart)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(2)
        l1 = QLabel(baslik)
        l1.setObjectName("kartBaslik")
        l2 = QLabel("–")
        l2.setObjectName("kartDeger")
        l2.setStyleSheet(f"font-size: 30px; font-weight: 800; color: {renk};")
        l3 = QLabel(alt)
        l3.setObjectName("kartAlt")
        for w in (l1, l2, l3):
            lay.addWidget(w)
        return kart, l2

    def _panel(self, baslik_lbl, tablo, bos_lbl):
        panel = QFrame()
        panel.setObjectName("kart")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)
        baslik_lbl.setStyleSheet("font-size: 16px; font-weight: 800; color: #0A1F5C;")
        bos_lbl.setStyleSheet("font-size: 13px; color: #8A9BC0; padding: 24px;")
        bos_lbl.setAlignment(Qt.AlignCenter)
        bos_lbl.hide()
        lay.addWidget(baslik_lbl)
        lay.addWidget(tablo)
        lay.addWidget(bos_lbl)
        return panel

    def _getir(self, yol):
        yanit = requests.get(f"{self.api_url}{yol}", headers=self.basliklar, timeout=10)
        yanit.raise_for_status()
        return yanit.json()

    # ------------------------------------------------------------------
    def verileri_yukle(self):
        if self.cihaz_ozeti:
            self._ozet_yukle()
        self._randevulari_yukle()
        if self.cihaz_ozeti:
            self._islemleri_yukle()

    def _ozet_yukle(self):
        try:
            veri = self._getir("/api/dashboard/ozet")
            for anahtar, lbl in self.lbl_degerler.items():
                lbl.setText(str(veri.get(anahtar, 0)))
        except Exception as e:
            print("Özet yükleme hatası:", e)

    def _randevulari_yukle(self):
        self.tablo_randevu.setRowCount(0)
        try:
            randevular = self._getir("/api/dashboard/bugunku-randevular")
        except Exception as e:
            print("Randevu listesi yükleme hatası:", e)
            self.lbl_degerler["bugunku_randevu_sayisi"].setText("?")
            self.lbl_randevu_bos.setText("Randevular yüklenemedi.")
            self.lbl_randevu_bos.show()
            self.tablo_randevu.hide()
            return

        aktif = [r for r in randevular if r["durum"] != "IPTAL_EDILDI"]
        self.lbl_degerler["bugunku_randevu_sayisi"].setText(str(len(aktif)))

        self.lbl_randevu_bos.setText("Bugün için kayıtlı randevu bulunmuyor.")
        self.lbl_randevu_bos.setVisible(not randevular)
        self.tablo_randevu.setVisible(bool(randevular))
        self.tablo_randevu.setRowCount(len(randevular))
        for i, r in enumerate(randevular):
            iptal = r["durum"] == "IPTAL_EDILDI"
            gri = "#9CA3AF" if iptal else None
            metin, renk, arka = DURUM_METIN.get(r["durum"], (r["durum"], "#374151", "#F3F4F6"))
            self.tablo_randevu.setItem(i, 0, _item(f"{r['baslangic']} – {r['bitis']}", renk=gri, kalin=not iptal))
            self.tablo_randevu.setItem(i, 1, _item(r["danisan_kod_id"], renk=gri))
            self.tablo_randevu.setItem(i, 2, _item(r["psikolog"], renk=gri))
            self.tablo_randevu.setItem(i, 3, _item(r["oda"], renk=gri))
            self.tablo_randevu.setItem(i, 4, _item(metin, renk=renk, arka=arka, kalin=True))
        self.tablo_randevu.setFixedHeight(min(44 + 38 * len(randevular), 420))

    def _islemleri_yukle(self):
        self.tablo_islem.setRowCount(0)
        try:
            islemler = self._getir("/api/dashboard/yaklasan-islemler")
        except Exception as e:
            print("Yaklaşan işlemler yükleme hatası:", e)
            return
        self.lbl_islem_bos.setVisible(not islemler)
        self.tablo_islem.setVisible(bool(islemler))
        self.tablo_islem.setRowCount(len(islemler))
        self.tablo_islem.setFixedHeight(min(44 + 38 * len(islemler), 420))
        for i, islem in enumerate(islemler):
            kritik = islem["durum_kodu"] == "KRITIK"
            arka = "#FEE2E2" if kritik else "#FEF9C3"
            renk = "#991B1B" if kritik else "#854D0E"
            kalan = "Bugün" if islem["kalan_gun"] == 0 else f"{islem['kalan_gun']} gün"
            self.tablo_islem.setItem(i, 0, _item(islem["cihaz_adi"], ortala=False))
            self.tablo_islem.setItem(i, 1, _item(islem["islem_turu"]))
            self.tablo_islem.setItem(i, 2, _item(islem["tarih"]))
            self.tablo_islem.setItem(i, 3, _item(kalan, renk=renk, arka=arka, kalin=True))
