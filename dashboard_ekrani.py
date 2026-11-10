import datetime
import time
import requests
from api_yoneticisi import (
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)
from PySide6.QtWidgets import (QPushButton, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QGridLayout, QLabel,
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


def _tablo_boyutlandir(tablo, satir_sayisi, en_fazla_gorunen=None):
    """Tablo yüksekliğini ayarlar. en_fazla_gorunen verilmişse ve satır sayısı onu aşıyorsa tablo o satır
    kadar yükseklikte kalır, başlık sabit durur ve satırlar büyük renkli bir çubukla kaydırılır."""
    kaydirilabilir = en_fazla_gorunen is not None and satir_sayisi > en_fazla_gorunen
    gorunen = en_fazla_gorunen if kaydirilabilir else max(satir_sayisi, 1)
    tablo.setFixedHeight(46 + SATIR_YUKSEKLIK * gorunen + 4)
    tablo.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn if kaydirilabilir else Qt.ScrollBarAlwaysOff)
    tablo.setStyleSheet(TABLO_STIL + (CUBUK_STILI if kaydirilabilir else ""))
    return kaydirilabilir


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


CUBUK_STILI = """
QScrollBar:vertical { background: #DCE8FB; width: 18px; margin: 2px 0 2px 8px; border-radius: 9px; }
QScrollBar::handle:vertical { background: #2563EB; min-height: 70px; border-radius: 9px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #1D4ED8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""
KAYDIRMA_CUBUGU_STILI = """
QScrollArea#bildirimKaydirma { background: transparent; }
QScrollArea#bildirimKaydirma > QWidget > QWidget { background: transparent; }
""" + CUBUK_STILI
TABLO_GORUNEN_SATIR = 5        # tabloda kaydırmadan görünen satır sayısı; fazlası kaydırma çubuğuyla görülür


class DashboardEkrani(QWidget):
    """Ana kontrol paneli gövdesi.

    cihaz_ozeti=True  -> cihaz kartları, bildirimler, cihaz rezervasyonları ve
                         yaklaşan bakım/kalibrasyon tablosu da gösterilir
                         (müdür, admin, memur).
    Bugünkü randevu listesi her rolde gösterilir.
    """

    def __init__(self, api_url, token, cihaz_ozeti=True, sayfa_ac=None, sayfa_izinli_mi=None,
                 parola_talepleri_goster=False):
        """sayfa_ac(sayfa_adi): bildirime tıklanınca o sayfayı açar.
        sayfa_izinli_mi(sayfa_adi): kullanıcının o sayfaya yetkisi yoksa False; o sayfanın bildirimi hiç gösterilmez.
        İkisi de verilmezse bildirimler eskisi gibi yalnızca gösterilir (tıklanınca bir şey olmaz)."""
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.cihaz_ozeti = cihaz_ozeti
        self._sayfa_ac = sayfa_ac
        self._sayfa_izinli_mi = sayfa_izinli_mi
        self._parola_talepleri_goster = parola_talepleri_goster
        self.parola_talepleri = []
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
                ("KALİBRASYONDAKİ CİHAZ", "kalibrasyondaki_cihaz", "📏", "#0E7490", "#CFFAFE"),
                ("ARIZALI CİHAZ", "arizali_cihaz", "⚠️", "#B91C1C", "#FEE2E2"),
            ]
        self.kart_grid = QGridLayout()
        self.kart_grid.setSpacing(18)
        self.kart_widgetleri = []
        for baslik, anahtar, ikon, renk, zemin in tanimlar:
            kart, lbl_deger, lbl_alt = self._kart(baslik, ikon, renk, zemin)
            self.kartlar[anahtar] = (lbl_deger, lbl_alt)
            self.kart_widgetleri.append(kart)
        self._kartlari_diz(self._kolon_sayisi(0))
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
            self._islem_hedefleri = []          # tablodaki her satırın açacağı sayfa
            self.tablo_islem.cellClicked.connect(self._islem_satiri_tiklandi)
            if self._sayfa_ac is not None:
                self.tablo_islem.viewport().setCursor(Qt.PointingHandCursor)
            self.lbl_islem_bos = QLabel("Uyarı süresine giren ya da geciken bakım veya kalibrasyon yok.")
            self.panel_islem = self._panel("Yaklaşan ve Geciken Bakım/Kalibrasyonlar",
                                           "🛠️  uyarı süresi içinde ve geciken", self.tablo_islem, self.lbl_islem_bos)
            ana.addWidget(self.panel_islem)

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
    def _kolon_sayisi(self, genislik):
        """Geniş pencerede kartların hepsi tek sırada, dar pencerede 3 sütunda durur."""
        kart_sayisi = len(self.kart_widgetleri)
        genis_esik = 1450 if kart_sayisi <= 5 else 1750
        return min(kart_sayisi, 6) if genislik >= genis_esik else 3

    def _kartlari_diz(self, kolon):
        for i, kart in enumerate(self.kart_widgetleri):
            self.kart_grid.addWidget(kart, i // kolon, i % kolon)
        for c in range(kolon):
            self.kart_grid.setColumnStretch(c, 1)

    def resizeEvent(self, olay):
        """Dar pencerede kartlar 3 sütuna, paneller alt alta geçer."""
        super().resizeEvent(olay)
        genislik = self.width()
        kolon = self._kolon_sayisi(genislik)
        if getattr(self, "_kolon", None) != kolon:
            self._kolon = kolon
            for c in range(6):
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
        panel.ust = ust
        return panel

    def _getir(self, yol):
        yanit = oturum_kontrollu_istek("GET", f"{self.api_url}{yol}", headers=self.basliklar, timeout=10)
        if oturum_hatasi_mi(yanit):
            return
        yanit.raise_for_status()
        return yanit.json()

    def _liste_goster(self, tablo, bos_lbl, kayit_sayisi, en_fazla_gorunen=None):
        bos_lbl.setVisible(kayit_sayisi == 0)
        tablo.setVisible(kayit_sayisi > 0)
        tablo.setRowCount(kayit_sayisi)
        return _tablo_boyutlandir(tablo, kayit_sayisi, en_fazla_gorunen)

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
            self._parola_taleplerini_yukle()
            self._bildirimleri_olustur()

    def _ozet_yukle(self):
        try:
            self.ozet = self._getir("/api/dashboard/ozet")
        except Exception as e:
            print("Özet yükleme hatası:", e)
            return
        for anahtar in ("aktif_cihaz", "bakimdaki_cihaz", "kalibrasyondaki_cihaz", "arizali_cihaz"):
            self.kartlar[anahtar][0].setText(str(self.ozet.get(anahtar, 0)))
        self.kartlar["aktif_cihaz"][1].setText(f"Toplam {self.ozet.get('toplam_cihaz', 0)} cihaz içinde")
        self.kartlar["bakimdaki_cihaz"][1].setText("Geçici olarak kullanılamaz")
        self.kartlar["kalibrasyondaki_cihaz"][1].setText("Kalibrasyon bitene kadar kullanılamaz")
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
        # Yetkisi olmayan sayfanın satırı hiç gösterilmez; her satır kendi sayfasına gider.
        gorunen = [(islem, self._islem_hedefi(islem)) for islem in self.islemler]
        gorunen = [(islem, hedef) for islem, hedef in gorunen if hedef is not None and self._sayfa_izinli(hedef)]
        self._islem_hedefleri = [hedef for _, hedef in gorunen]
        self.lbl_islem_bos.setText("Uyarı süresine giren ya da geciken bakım veya kalibrasyon yok.")
        kaydirilabilir = self._liste_goster(self.tablo_islem, self.lbl_islem_bos, len(gorunen), TABLO_GORUNEN_SATIR)
        self._kaydirma_ipucu_guncelle(self.panel_islem, len(gorunen) if kaydirilabilir else 0)
        for i, (islem, hedef) in enumerate(gorunen):
            kritik = islem["kalan_gun"] <= 5
            uyari = islem["kalan_gun"] <= 15
            renk, arka = (("#991B1B", "#FEE2E2") if kritik else
                          ("#854D0E", "#FEF3C7") if uyari else ("#166534", "#DCFCE7"))
            gun = islem["kalan_gun"]
            kalan = "Bugün" if gun == 0 else (f"{-gun} gün gecikti" if gun < 0 else f"{gun} gün")
            ipucu = f"{hedef} sayfasına git" if self._sayfa_ac is not None else ""
            for kolon, item in enumerate((_item(islem["cihaz_adi"], ortala=False, kalin=True),
                                          _item(islem["islem_turu"]), _item(islem["tarih"]))):
                item.setToolTip(ipucu)
                self.tablo_islem.setItem(i, kolon, item)
            _hap(self.tablo_islem, i, 3, kalan, renk, arka)
            self.tablo_islem.cellWidget(i, 3).setToolTip(ipucu)

    def _kaydirma_ipucu_guncelle(self, panel, adet):
        """Tablo kaydırılabilirse başlık satırına dikkat çeken rozet koyar; değilse kaldırır."""
        eski = panel.findChild(QLabel, "tabloKaydirmaIpucu")
        if eski is not None:
            eski.hide()
            eski.setParent(None)
            eski.deleteLater()
        if adet:
            ipucu = QLabel(f"⇅  {adet} kayıt var — kaydırarak hepsini görün")
            ipucu.setObjectName("tabloKaydirmaIpucu")
            ipucu.setStyleSheet("background: #FEF3C7; color: #854D0E; border-radius: 10px; "
                                "font-size: 11px; font-weight: 800; padding: 4px 12px;")
            panel.ust.insertWidget(panel.ust.count() - 1, ipucu)        # sağdaki mevcut rozetin soluna

    def _islem_satiri_tiklandi(self, satir, _kolon):
        """Tabloda bir satıra (herhangi bir hücresine) tıklanınca ilgili sayfa açılır."""
        if self._sayfa_ac is not None and 0 <= satir < len(self._islem_hedefleri):
            self._sayfa_ac(self._islem_hedefleri[satir])

    def _parola_taleplerini_yukle(self):
        """Bekleyen parola sıfırlama talepleri (yalnızca yetkili yöneticide istenir; hata olursa liste boş kalır)."""
        self.parola_talepleri = []
        if not self._parola_talepleri_goster:
            return
        try:
            talepler = self._getir("/api/parola-sifirlama-talepleri")
            self.parola_talepleri = talepler if isinstance(talepler, list) else []
        except Exception as e:
            print("Parola talepleri yükleme hatası:", e)

    # ------------------------------------------------------------------
    BILDIRIM_SINIRI = 5          # kaydırmadan görünen satır sayısı; fazlası kaydırma çubuğuyla görülür
    HEDEF_SAYFALAR = {"Bakım": "Bakım Kayıtları", "Kalibrasyon": "Kalibrasyon"}
    ARIZA_SAYFASI = "Arıza Kayıtları"
    PAROLA_SAYFASI = "Kullanıcı & Personel"

    @staticmethod
    def _bekleme_metni(dakika):
        """'az önce', '5 dk önce', '2 saat önce', '3 gün önce'."""
        dakika = max(int(dakika or 0), 0)
        if dakika < 1:
            return "az önce"
        if dakika < 60:
            return f"{dakika} dk önce"
        if dakika < 1440:
            return f"{dakika // 60} saat önce"
        return f"{dakika // 1440} gün önce"

    def _islem_hedefi(self, islem):
        """Bakım ya da kalibrasyon işleminin açacağı sayfa (bilinmeyen tür için None)."""
        return self.HEDEF_SAYFALAR.get(islem.get("islem_turu"))

    def _sayfa_izinli(self, sayfa):
        """Kullanıcı o sayfaya girebiliyor mu? (Karar verilmemişse evet.)"""
        return True if self._sayfa_izinli_mi is None else bool(self._sayfa_izinli_mi(sayfa))

    def _bildirim_satirlari(self):
        """[(ikon, metin, yazı rengi, arka plan, hedef sayfa)] — yetkisiz olunan sayfaların bildirimleri çıkarılır."""
        satirlar = []
        if self._sayfa_izinli(self.PAROLA_SAYFASI):
            for talep in self.parola_talepleri:
                satirlar.append(("🔐", f"{talep['kullanici_adi']} parola sıfırlama istedi "
                                       f"({self._bekleme_metni(talep.get('bekleme_dakika'))})",
                                 "#1E3A8A", "#DBEAFE", self.PAROLA_SAYFASI))
        acik_ariza = self.ozet.get("acik_ariza_sayisi", 0)
        if acik_ariza and self._sayfa_izinli(self.ARIZA_SAYFASI):
            satirlar.append(("⚠️", f"{acik_ariza} açık arıza kaydı çözüm bekliyor.", "#991B1B", "#FEE2E2",
                             self.ARIZA_SAYFASI))
        for islem in self.islemler:
            hedef = self._islem_hedefi(islem)
            if hedef is None or not self._sayfa_izinli(hedef):
                continue
            gun = islem["kalan_gun"]   # liste zaten kayıt başına uyarı süresine göre süzülmüş ve sıralı
            zaman = "bugün" if gun == 0 else (f"{-gun} gün gecikti" if gun < 0 else f"{gun} gün içinde")
            kritik = gun <= 5
            satirlar.append((
                "🔴" if kritik else "🟡",
                f"{islem['cihaz_adi']}  —  {islem['islem_turu']} {zaman} ({islem['tarih']})",
                "#991B1B" if kritik else "#854D0E",
                "#FEE2E2" if kritik else "#FEF3C7",
                hedef))
        return satirlar

    def _bildirim_dugmesi(self, metin, renk, arka, hedef):
        """Tıklanınca ilgili sayfayı açan bildirim satırı. Tıklama tek bir yuvaya gider (lambda kullanılmaz)."""
        dugme = QPushButton(f"{metin}   →")
        dugme.setProperty("hedef", hedef)
        dugme.setCursor(Qt.PointingHandCursor)
        dugme.setToolTip(f"{hedef} sayfasına git")
        dugme.setStyleSheet(
            f"QPushButton {{ background: {arka}; color: {renk}; border: none; border-radius: 10px; "
            f"font-size: 13px; font-weight: 600; padding: 10px 14px; text-align: left; }} "
            f"QPushButton:hover {{ border: 1px solid {renk}; }}")
        dugme.clicked.connect(self._bildirim_tiklandi)
        return dugme

    def _bildirim_tiklandi(self):
        hedef = self.sender().property("hedef") if self.sender() is not None else None
        if hedef and self._sayfa_ac is not None:
            self._sayfa_ac(hedef)

    def _bildirimleri_olustur(self):
        """Üstteki bildirim kutusu: kritik bakım/kalibrasyon ve açık arıza uyarıları (tıklanınca ilgili sayfa açılır)."""
        while self.bildirim_lay.count():
            w = self.bildirim_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)            # silinene kadar eski satırlar kutuda görünmesin / sayılmasın
                w.deleteLater()

        satirlar = self._bildirim_satirlari()
        fazla = len(satirlar) > self.BILDIRIM_SINIRI

        ust = QHBoxLayout()
        baslik = QLabel(f"🔔  Bildirimler  ({len(satirlar)})" if satirlar else "🔔  Bildirimler")
        baslik.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1F5C;")
        ust.addWidget(baslik)
        ust.addStretch()
        if fazla:
            # Kullanıcının fark etmesi için dikkat çeken rozet: listenin kaydırılabildiğini söyler.
            ipucu = QLabel(f"⇅  {len(satirlar)} bildirim var — kaydırarak hepsini görün")
            ipucu.setObjectName("bildirimKaydirmaIpucu")
            ipucu.setStyleSheet("background: #FEF3C7; color: #854D0E; border-radius: 10px; "
                                "font-size: 12px; font-weight: 800; padding: 4px 12px;")
            ust.addWidget(ipucu)
        ust_kap = QWidget()
        ust_kap.setLayout(ust)
        ust.setContentsMargins(0, 0, 0, 0)
        self.bildirim_lay.addWidget(ust_kap)

        if not satirlar:
            ok = QLabel("✅  Bekleyen uyarı yok. Yaklaşan ya da geciken bakım, kalibrasyon ve açık arıza bulunmuyor.")
            ok.setStyleSheet("background: #DCFCE7; color: #166534; border-radius: 10px; "
                             "font-size: 13px; font-weight: 600; padding: 10px 14px;")
            self.bildirim_lay.addWidget(ok)
            return

        satir_kutusu = QWidget()
        satir_lay = QVBoxLayout(satir_kutusu)
        satir_lay.setContentsMargins(0, 0, 0, 0)
        satir_lay.setSpacing(8)
        dugmeler = [self._bildirim_dugmesi(f"{ikon}  {metin}", renk, arka, hedef)
                    for ikon, metin, renk, arka, hedef in satirlar]
        for dugme in dugmeler:
            satir_lay.addWidget(dugme)

        if not fazla:
            self.bildirim_lay.addWidget(satir_kutusu)
            return

        # Çok bildirim: ilk BILDIRIM_SINIRI satır görünür, gerisi büyük ve renkli bir kaydırma çubuğuyla kaydırılır.
        kaydirma = QScrollArea()
        kaydirma.setObjectName("bildirimKaydirma")
        kaydirma.setWidgetResizable(True)
        kaydirma.setFrameShape(QFrame.NoFrame)
        kaydirma.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        kaydirma.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)     # çubuk hep görünsün
        kaydirma.setStyleSheet(KAYDIRMA_CUBUGU_STILI)
        kaydirma.setWidget(satir_kutusu)
        satir_yuksekligi = dugmeler[0].sizeHint().height()
        kaydirma.setFixedHeight(self.BILDIRIM_SINIRI * satir_yuksekligi + (self.BILDIRIM_SINIRI - 1) * 8 + 4)
        self.bildirim_lay.addWidget(kaydirma)
