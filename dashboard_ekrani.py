import datetime
import time
import requests
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QGridLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
                               QSizePolicy)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
         "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# durum kodu -> (yazı, yazı rengi, arka plan)
DURUM_METIN = {
    "PLANLANDI": ("Planlandı", "#1D4ED8", "#DBEAFE"),
    "TAMAMLANDI": ("Tamamlandı", "#15803D", "#DCFCE7"),
    "IPTAL_EDILDI": ("İptal", "#B91C1C", "#FEE2E2"),
}

SATIR_YUKSEKLIK = 42
TABLO_STIL = """
    QTableWidget { background: white; border: none; font-size: 13px; color: #0F2552; }
    QTableWidget::item { padding: 6px; border-bottom: 1px solid #EEF2FA; }
    QTableWidget::item:selected { background: #EEF4FF; color: #0F2552; }
    QHeaderView::section { background: #F3F7FF; color: #6B7FA8; padding: 10px;
                           font-size: 11px; font-weight: 800; border: none; }
"""


def _tablo_olustur(kolonlar):
    tablo = QTableWidget(0, len(kolonlar))
    tablo.setHorizontalHeaderLabels(kolonlar)
    tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tablo.verticalHeader().setVisible(False)
    tablo.verticalHeader().setDefaultSectionSize(SATIR_YUKSEKLIK)
    tablo.setEditTriggers(QTableWidget.NoEditTriggers)
    tablo.setSelectionBehavior(QTableWidget.SelectRows)
    tablo.setFocusPolicy(Qt.NoFocus)
    tablo.setShowGrid(False)
    tablo.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tablo.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    tablo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    tablo.setStyleSheet(TABLO_STIL)
    return tablo


def _tablo_boyutlandir(tablo, satir_sayisi):
    tablo.setFixedHeight(46 + SATIR_YUKSEKLIK * max(satir_sayisi, 1) + 4)


def _item(metin, ortala=True, renk=None, kalin=False):
    item = QTableWidgetItem(metin)
    if ortala:
        item.setTextAlignment(Qt.AlignCenter)
    if renk:
        item.setForeground(QColor(renk))
    if kalin:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    return item


def _hap(tablo, satir, kolon, metin, renk, arka):
    """Hücreye renkli durum 'hapı' (pill) koyar."""
    lbl = QLabel(metin)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background: {arka}; color: {renk}; border-radius: 11px; "
        f"font-size: 11px; font-weight: 800; padding: 4px 12px;")
    kap = QWidget()
    lay = QHBoxLayout(kap)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.addStretch()
    lay.addWidget(lbl)
    lay.addStretch()
    tablo.setCellWidget(satir, kolon, kap)


class DashboardEkrani(QWidget):
    """Ana kontrol paneli gövdesi.

    cihaz_ozeti=True  -> cihaz kartları, bildirimler, cihaz rezervasyonları ve
                         yaklaşan bakım/kalibrasyon tablosu da gösterilir
                         (müdür, admin, memur).
    Bugünkü randevu listesi her rolde gösterilir.
    """

    def __init__(self, api_url, token, cihaz_ozeti=True):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.cihaz_ozeti = cihaz_ozeti
        self.basliklar = {"Authorization": f"Bearer {token}"}
        self.ozet = {}
        self.islemler = []

        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(20)

        # ---- 1. BİLDİRİMLER (yalnızca cihaz yetkili roller) ----
        if cihaz_ozeti:
            self.bildirim_paneli = QFrame()
            self.bildirim_paneli.setObjectName("kart")
            self.bildirim_lay = QVBoxLayout(self.bildirim_paneli)
            self.bildirim_lay.setContentsMargins(22, 16, 22, 16)
            self.bildirim_lay.setSpacing(8)
            ana.addWidget(self.bildirim_paneli)

        # ---- 2. ÖZET KARTLARI ----
        self.kartlar = {}
        tanimlar = [("BUGÜNKÜ RANDEVU", "randevu", "📅", "#1D4ED8", "#DBEAFE")]
        if cihaz_ozeti:
            tanimlar += [
                ("BUGÜNKÜ REZERVASYON", "rezervasyon", "📌", "#6D28D9", "#EDE9FE"),
                ("KULLANILABİLİR CİHAZ", "aktif_cihaz", "✅", "#15803D", "#DCFCE7"),
                ("BAKIMDAKİ CİHAZ", "bakimdaki_cihaz", "🛠️", "#B45309", "#FEF3C7"),
                ("ARIZALI CİHAZ", "arizali_cihaz", "⚠️", "#B91C1C", "#FEE2E2"),
            ]
        self.kart_grid = QGridLayout()
        self.kart_grid.setSpacing(18)
        self.kart_widgetleri = []
        for baslik, anahtar, ikon, renk, zemin in tanimlar:
            kart, lbl_deger, lbl_alt = self._kart(baslik, ikon, renk, zemin)
            self.kartlar[anahtar] = (lbl_deger, lbl_alt)
            self.kart_widgetleri.append(kart)
        self._kartlari_diz(5)
        ana.addLayout(self.kart_grid)

        # ---- 3. RANDEVULAR  |  CİHAZ REZERVASYONLARI ----
        bugun = datetime.date.today()
        tarih = f"{bugun.day} {AYLAR[bugun.month - 1]} {bugun.year}"

        self.tablo_randevu = _tablo_olustur(["SAAT", "DANIŞAN KODU", "PSİKOLOG", "ODA", "DURUM"])
        self.lbl_randevu_bos = QLabel("Bugün için kayıtlı randevu bulunmuyor.")
        panel_randevu = self._panel("Danışan Randevuları", f"📅  {tarih}",
                                    self.tablo_randevu, self.lbl_randevu_bos)

        if cihaz_ozeti:
            self.tablo_rez = _tablo_olustur(["SAAT", "CİHAZ", "REZERVE EDEN", "ODA"])
            self.lbl_rez_bos = QLabel("Bugün için cihaz rezervasyonu bulunmuyor.")
            panel_rez = self._panel("Cihaz Rezervasyonları", f"📌  {tarih}",
                                    self.tablo_rez, self.lbl_rez_bos)
            self.yan_yana = QBoxLayout(QBoxLayout.LeftToRight)
            self.yan_yana.setSpacing(18)
            self.yan_yana.addWidget(panel_randevu, 1, Qt.AlignTop)
            self.yan_yana.addWidget(panel_rez, 1, Qt.AlignTop)
            ana.addLayout(self.yan_yana)
        else:
            ana.addWidget(panel_randevu)

        # ---- 4. YAKLAŞAN BAKIM / KALİBRASYON ----
        if cihaz_ozeti:
            self.tablo_islem = _tablo_olustur(["CİHAZ", "İŞLEM", "SON TARİH", "KALAN SÜRE"])
            self.lbl_islem_bos = QLabel("Önümüzdeki 60 gün içinde bakım veya kalibrasyon yok.")
            ana.addWidget(self._panel("Yaklaşan Bakım ve Kalibrasyonlar",
                                      "🛠️  önümüzdeki 60 gün", self.tablo_islem, self.lbl_islem_bos))

        self.tarih_panelleri = [(panel_randevu, "📅")]
        if cihaz_ozeti:
            self.tarih_panelleri.append((panel_rez, "📌"))

        self._son_yukleme = 0
        self.yenile()

        # Ekran açık kalırsa her dakika kendini günceller (gün değişimi dahil)
        self.zamanlayici = QTimer(self)
        self.zamanlayici.timeout.connect(self.yenile)
        self.zamanlayici.start(60_000)
    # ------------------------------------------------------------------
    def _kartlari_diz(self, kolon):
        for i, kart in enumerate(self.kart_widgetleri):
            self.kart_grid.addWidget(kart, i // kolon, i % kolon)
        for c in range(kolon):
            self.kart_grid.setColumnStretch(c, 1)

    def resizeEvent(self, olay):
        """Dar pencerede kartlar 3 sütuna, paneller alt alta geçer."""
        super().resizeEvent(olay)
        genislik = self.width()
        kolon = 5 if genislik >= 1450 else 3
        if getattr(self, "_kolon", None) != kolon:
            self._kolon = kolon
            for c in range(5):
                self.kart_grid.setColumnStretch(c, 0)
            self._kartlari_diz(kolon)
        if self.cihaz_ozeti:
            yon = QBoxLayout.LeftToRight if genislik >= 1200 else QBoxLayout.TopToBottom
            self.yan_yana.setDirection(yon)

    # ------------------------------------------------------------------
    def _kart(self, baslik, ikon, renk, zemin):
        kart = QFrame()
        kart.setObjectName("kart")
        ana = QHBoxLayout(kart)
        ana.setContentsMargins(18, 16, 18, 16)
        ana.setSpacing(14)

        chip = QLabel(ikon)
        chip.setFixedSize(46, 46)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(f"background: {zemin}; border-radius: 14px; font-size: 20px;")

        sag = QVBoxLayout()
        sag.setSpacing(0)
        l1 = QLabel(baslik)
        l1.setObjectName("kartBaslik")
        l2 = QLabel("–")
        l2.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {renk};")
        l3 = QLabel(" ")
        l3.setObjectName("kartAlt")
        for w in (l1, l2, l3):
            sag.addWidget(w)

        ana.addWidget(chip, 0, Qt.AlignTop)
        ana.addLayout(sag, 1)
        return kart, l2, l3

    def _panel(self, baslik, alt_baslik, tablo, bos_lbl):
        panel = QFrame()
        panel.setObjectName("kart")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(10)

        ust = QHBoxLayout()
        b = QLabel(baslik)
        b.setStyleSheet("font-size: 16px; font-weight: 800; color: #0A1F5C;")
        a = QLabel(alt_baslik)
        a.setStyleSheet("background: #EEF4FF; color: #3B5BA9; border-radius: 10px; "
                        "font-size: 11px; font-weight: 700; padding: 4px 12px;")
        ust.addWidget(b)
        ust.addStretch()
        ust.addWidget(a)

        bos_lbl.setStyleSheet("font-size: 13px; color: #8A9BC0; padding: 26px;")
        bos_lbl.setAlignment(Qt.AlignCenter)
        bos_lbl.hide()
        lay.addLayout(ust)
        lay.addWidget(tablo)
        lay.addWidget(bos_lbl)
        panel.rozet = a
        return panel

    def _getir(self, yol):
        yanit = requests.get(f"{self.api_url}{yol}", headers=self.basliklar, timeout=10)
        yanit.raise_for_status()
        return yanit.json()

    def _liste_goster(self, tablo, bos_lbl, kayit_sayisi):
        bos_lbl.setVisible(kayit_sayisi == 0)
        tablo.setVisible(kayit_sayisi > 0)
        tablo.setRowCount(kayit_sayisi)
        _tablo_boyutlandir(tablo, kayit_sayisi)

    # ------------------------------------------------------------------
    def yenile(self):
        bugun = datetime.date.today()
        tarih = f"{bugun.day} {AYLAR[bugun.month - 1]} {bugun.year}"
        for panel, ikon in self.tarih_panelleri:
            panel.rozet.setText(f"{ikon}  {tarih}")
        self._son_yukleme = time.monotonic()
        self.verileri_yukle()

    def showEvent(self, olay):
        """Ana panele her dönüşte (başka sayfadan gelince) veriyi tazeler."""
        super().showEvent(olay)
        if time.monotonic() - self._son_yukleme > 5:
            self.yenile()

    def verileri_yukle(self):
        if self.cihaz_ozeti:
            self._ozet_yukle()
        self._randevulari_yukle()
        if self.cihaz_ozeti:
            self._rezervasyonlari_yukle()
            self._islemleri_yukle()
            self._bildirimleri_olustur()

    def _ozet_yukle(self):
        try:
            self.ozet = self._getir("/api/dashboard/ozet")
        except Exception as e:
            print("Özet yükleme hatası:", e)
            return
        for anahtar in ("aktif_cihaz", "bakimdaki_cihaz", "arizali_cihaz"):
            self.kartlar[anahtar][0].setText(str(self.ozet.get(anahtar, 0)))
        self.kartlar["aktif_cihaz"][1].setText(f"Toplam {self.ozet.get('toplam_cihaz', 0)} cihaz içinde")
        self.kartlar["bakimdaki_cihaz"][1].setText("Geçici olarak kullanılamaz")
        self.kartlar["arizali_cihaz"][1].setText(f"{self.ozet.get('acik_ariza_sayisi', 0)} açık arıza kaydı")

    def _randevulari_yukle(self):
        lbl_deger, lbl_alt = self.kartlar["randevu"]
        try:
            randevular = self._getir("/api/dashboard/bugunku-randevular")
        except Exception as e:
            print("Randevu listesi yükleme hatası:", e)
            lbl_deger.setText("?")
            self.lbl_randevu_bos.setText("Randevular yüklenemedi.")
            self._liste_goster(self.tablo_randevu, self.lbl_randevu_bos, 0)
            return

        aktif = [r for r in randevular if r["durum"] != "IPTAL_EDILDI"]
        lbl_deger.setText(str(len(aktif)))
        lbl_alt.setText("Bugün planlanan seans")
        self.lbl_randevu_bos.setText("Bugün için kayıtlı randevu bulunmuyor.")
        self._liste_goster(self.tablo_randevu, self.lbl_randevu_bos, len(randevular))
        for i, r in enumerate(randevular):
            iptal = r["durum"] == "IPTAL_EDILDI"
            gri = "#9CA3AF" if iptal else None
            metin, renk, arka = DURUM_METIN.get(r["durum"], (r["durum"], "#374151", "#F3F4F6"))
            self.tablo_randevu.setItem(i, 0, _item(f"{r['baslangic']} – {r['bitis']}", renk=gri, kalin=not iptal))
            self.tablo_randevu.setItem(i, 1, _item(r["danisan_kod_id"], renk=gri))
            self.tablo_randevu.setItem(i, 2, _item(r["psikolog"], renk=gri))
            self.tablo_randevu.setItem(i, 3, _item(r["oda"], renk=gri))
            _hap(self.tablo_randevu, i, 4, metin, renk, arka)

    def _rezervasyonlari_yukle(self):
        lbl_deger, lbl_alt = self.kartlar["rezervasyon"]
        try:
            rezervasyonlar = self._getir("/api/dashboard/bugunku-rezervasyonlar")
        except Exception as e:
            print("Rezervasyon listesi yükleme hatası:", e)
            lbl_deger.setText("?")
            self.lbl_rez_bos.setText("Rezervasyonlar yüklenemedi.")
            self._liste_goster(self.tablo_rez, self.lbl_rez_bos, 0)
            return

        lbl_deger.setText(str(len(rezervasyonlar)))
        lbl_alt.setText("Bugün rezerve edilen cihaz")
        self.lbl_rez_bos.setText("Bugün için cihaz rezervasyonu bulunmuyor.")
        self._liste_goster(self.tablo_rez, self.lbl_rez_bos, len(rezervasyonlar))
        for i, r in enumerate(rezervasyonlar):
            self.tablo_rez.setItem(i, 0, _item(f"{r['baslangic']} – {r['bitis']}", kalin=True))
            self.tablo_rez.setItem(i, 1, _item(r["cihaz"]))
            self.tablo_rez.setItem(i, 2, _item(r["rezerve_eden"]))
            self.tablo_rez.setItem(i, 3, _item(r["oda"]))

    def _islemleri_yukle(self):
        try:
            self.islemler = self._getir("/api/dashboard/yaklasan-islemler")
        except Exception as e:
            print("Yaklaşan işlemler yükleme hatası:", e)
            self.islemler = []
        self.lbl_islem_bos.setText("Önümüzdeki 60 gün içinde bakım veya kalibrasyon yok.")
        self._liste_goster(self.tablo_islem, self.lbl_islem_bos, len(self.islemler))
        for i, islem in enumerate(self.islemler):
            kritik = islem["kalan_gun"] <= 5
            uyari = islem["kalan_gun"] <= 15
            renk, arka = (("#991B1B", "#FEE2E2") if kritik else
                          ("#854D0E", "#FEF3C7") if uyari else ("#166534", "#DCFCE7"))
            kalan = "Bugün" if islem["kalan_gun"] == 0 else f"{islem['kalan_gun']} gün"
            self.tablo_islem.setItem(i, 0, _item(islem["cihaz_adi"], ortala=False, kalin=True))
            self.tablo_islem.setItem(i, 1, _item(islem["islem_turu"]))
            self.tablo_islem.setItem(i, 2, _item(islem["tarih"]))
            _hap(self.tablo_islem, i, 3, kalan, renk, arka)

    # ------------------------------------------------------------------
    def _bildirimleri_olustur(self):
        """Üstteki bildirim kutusu: kritik bakım/kalibrasyon ve açık arıza uyarıları."""
        while self.bildirim_lay.count():
            w = self.bildirim_lay.takeAt(0).widget()
            if w:
                w.deleteLater()

        satirlar = []  # (ikon, metin, yazı rengi, arka plan)
        acik_ariza = self.ozet.get("acik_ariza_sayisi", 0)
        if acik_ariza:
            satirlar.append(("⚠️", f"{acik_ariza} açık arıza kaydı çözüm bekliyor.", "#991B1B", "#FEE2E2"))
        for islem in self.islemler:
            gun = islem["kalan_gun"]
            if gun > 15:
                break  # liste kalan güne göre sıralı
            zaman = "bugün" if gun == 0 else f"{gun} gün içinde"
            kritik = gun <= 5
            satirlar.append((
                "🔴" if kritik else "🟡",
                f"{islem['cihaz_adi']}  —  {islem['islem_turu']} {zaman} ({islem['tarih']})",
                "#991B1B" if kritik else "#854D0E",
                "#FEE2E2" if kritik else "#FEF3C7"))

        baslik = QLabel(f"🔔  Bildirimler  ({len(satirlar)})" if satirlar else "🔔  Bildirimler")
        baslik.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1F5C;")
        self.bildirim_lay.addWidget(baslik)

        if not satirlar:
            ok = QLabel("✅  Bekleyen uyarı yok. Yaklaşan bakım, kalibrasyon ve açık arıza bulunmuyor.")
            ok.setStyleSheet("background: #DCFCE7; color: #166534; border-radius: 10px; "
                             "font-size: 13px; font-weight: 600; padding: 10px 14px;")
            self.bildirim_lay.addWidget(ok)
            return

        for ikon, metin, renk, arka in satirlar[:6]:
            lbl = QLabel(f"{ikon}  {metin}")
            lbl.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 10px; "
                              f"font-size: 13px; font-weight: 600; padding: 10px 14px;")
            self.bildirim_lay.addWidget(lbl)
        if len(satirlar) > 6:
            diger = QLabel(f"… ve {len(satirlar) - 6} bildirim daha (aşağıdaki tabloya bakın)")
            diger.setStyleSheet("font-size: 12px; color: #6B7FA8; padding-left: 6px;")
            self.bildirim_lay.addWidget(diger)