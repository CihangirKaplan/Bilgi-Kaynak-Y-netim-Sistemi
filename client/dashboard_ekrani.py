import logging
import datetime
import time
from client.tablo_tasarimi import cihaz_hucresi_uygula, cihaz_ipucu
from client.sayfa_tema import KAYDIRMA_CUBUGU_STILI as CUBUK_STILI      # tek ortak kaydırma çubuğu
from client.ikon_kutusu import renkli_ikon_pixmap, ikon_pixmap
from client.bildirim_ikonlari import cizgi_ikonu, ikon_boyutu
from client.api_yoneticisi import (
    istek_hatasi_metni,
    oturum_kontrollu_istek,
    oturum_hatasi_mi,
)
from client.duyuru_diyaloglari import DuyuruDiyalogu, duyuru_kaldir
from PySide6.QtWidgets import (QDialog, QMessageBox, QPushButton, QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout, QGridLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
                               QSizePolicy)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QColor

logger = logging.getLogger(__name__)

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


class KaydirmaKilitliTablo(QTableWidget):
    """Kaydırma çubuğu açıkken fare tekerleği olayını hep bu tabloda tutar.

    Qt'de tablo sonuna/başına gelince tekerlek olayı üstteki sayfaya geçer ve bütün ana ekran kayar. Burada olay,
    tablo kaydırılamaz durumdayken (çubuk yok) sayfaya bırakılır; kaydırılabilirken uçlara gelinse bile tabloda kalır.
    """

    def wheelEvent(self, olay):
        super().wheelEvent(olay)
        if self.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn:
            olay.accept()


class KaydirmaKilitliAlan(QScrollArea):
    """Bildirim kutusu için aynı davranış: uçlara gelince ana ekranı kaydırmaz."""

    def wheelEvent(self, olay):
        super().wheelEvent(olay)
        if self.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn:
            olay.accept()


class TiklanabilirKart(QFrame):
    """Özet kartı: tıklanınca ilgili sayfayı açar. Tıklanabilir değilken eskisi gibi yalnızca bilgi gösterir."""
    tiklandi = Signal()

    def __init__(self):
        super().__init__()
        self._tiklanabilir = False
        self._basili = False

    def tiklanabilir_yap(self, acik, ipucu=""):
        self._tiklanabilir = acik
        self.setProperty("tiklanabilir", "true" if acik else "false")
        self.setCursor(Qt.PointingHandCursor if acik else Qt.ArrowCursor)
        self.setToolTip(ipucu if acik else "")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, olay):
        self._basili = self._tiklanabilir and olay.button() == Qt.LeftButton
        super().mousePressEvent(olay)

    def mouseReleaseEvent(self, olay):
        if self._basili and olay.button() == Qt.LeftButton and self.rect().contains(olay.position().toPoint()):
            self.tiklandi.emit()
        self._basili = False
        super().mouseReleaseEvent(olay)


KART_TIKLANABILIR_STILI = """
QFrame#kart[tiklanabilir="true"] { border: 1px solid transparent; }
QFrame#kart[tiklanabilir="true"]:hover { border: 1px solid #2563EB; background: #F5F9FF; }
"""


def _tablo_olustur(kolonlar):
    tablo = KaydirmaKilitliTablo(0, len(kolonlar))
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


KAYDIRMA_CUBUGU_STILI = """
QScrollArea#bildirimKaydirma { background: transparent; }
QScrollArea#bildirimKaydirma > QWidget > QWidget { background: transparent; }
""" + CUBUK_STILI
# Özet kartı -> (açılacak sayfa, cihaz durumu filtresi, ipucu). Filtre yalnızca Cihaz Envanteri'nde uygulanır.
KART_HEDEFLERI = {
    "randevu": ("Randevu Yönetimi", None, "Randevuları aç"),
    "rezervasyon": ("Cihaz Rezervasyonu", None, "Cihaz rezervasyonlarını aç"),
    "aktif_cihaz": ("Cihaz Envanteri", "Kullanima_Hazir", "Kullanıma hazır cihazları envanterde göster"),
    "bakimdaki_cihaz": ("Cihaz Envanteri", "Bakimda", "Bakımdaki cihazları envanterde göster"),
    "kalibrasyondaki_cihaz": ("Cihaz Envanteri", "Kalibrasyonda", "Kalibrasyondaki cihazları envanterde göster"),
    "arizali_cihaz": ("Cihaz Envanteri", "Arizali", "Arızalı cihazları envanterde göster"),
}
TABLO_GORUNEN_SATIR = 5        # tabloda kaydırmadan görünen satır sayısı; fazlası kaydırma çubuğuyla görülür


class DashboardEkrani(QWidget):
    """Ana kontrol paneli gövdesi.

    cihaz_ozeti=True  -> cihaz kartları, bildirimler, cihaz rezervasyonları ve
                         yaklaşan bakım/kalibrasyon tablosu da gösterilir
                         (müdür, admin, memur).
    Bugünkü randevu listesi her rolde gösterilir.
    """

    duyuru_degisti = Signal()           # duyuru yayınlandı/kaldırıldı/okundu işaretlendi: ana pencere zil sayısını yeniler

    def __init__(self, api_url, token, cihaz_ozeti=True, sayfa_ac=None, sayfa_izinli_mi=None,
                 parola_talepleri_goster=False, kart_ac=None, rezervasyon_paneli=False, etkinlik_paneli=False,
                 duyuru_yonetebilir=False):
        """kart_ac(sayfa_adi, cihaz_durumu): özet kartına tıklanınca o sayfayı (cihaz kartlarında o duruma göre
        süzülmüş) açar; verilmezse kartlar yalnızca bilgi gösterir. Yetkisiz olunan sayfanın kartı tıklanamaz.
        sayfa_ac(sayfa_adi): bildirime tıklanınca o sayfayı açar.
        sayfa_izinli_mi(sayfa_adi): kullanıcının o sayfaya yetkisi yoksa False; o sayfanın bildirimi hiç gösterilmez.
        İkisi de verilmezse bildirimler eskisi gibi yalnızca gösterilir (tıklanınca bir şey olmaz).
        rezervasyon_paneli: cihaz özeti yetkisi olmayan ama cihaz rezervasyonlarını görebilen kullanıcılar (rezervasyon yapanlar, Cihaz Uygunluğu'nu
        görenler) için "Cihaz Rezervasyonları" panelini de gösterir; cihaz_ozeti True ise panel zaten vardır.
        etkinlik_paneli: oda etkinliklerini görebilen kullanıcılar için bugünkü "Oda Etkinlikleri" panelini gösterir.
        duyuru_yonetebilir: Duyurular panelinde "Yeni duyuru" ve "Kaldır" düğmelerini gösterir (sunucu yine DUYURU_YONET ister)."""
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.cihaz_ozeti = cihaz_ozeti
        self._sayfa_ac = sayfa_ac
        self._sayfa_izinli_mi = sayfa_izinli_mi
        self._kart_ac = kart_ac
        self.rezervasyon_paneli = bool(cihaz_ozeti or rezervasyon_paneli)
        self.etkinlik_paneli = bool(etkinlik_paneli)
        self.duyuru_yonetebilir = bool(duyuru_yonetebilir)
        self.aralik = "bugun"                       # gün seçici: bugun | yarin | hafta
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

        # ---- 1b. DUYURULAR (herkes okur) ve BENİM GÜNÜM (yalnızca kişinin kendi kaydı varsa görünür) ----
        self.duyurular = []
        self._okunanlar_acik = False                # "Okunan duyurular" bölümü açık mı (yenilemelerde korunur)
        self._duyuru_hata = False                   # son yükleme başarısız mı (boş kutuda "yüklenemedi" yazılsın)
        self._benim_gunum_hata = False
        self.benim_gunum = {}
        self.panel_duyuru = QFrame()
        self.panel_duyuru.setObjectName("kart")
        self.duyuru_lay = QVBoxLayout(self.panel_duyuru)
        self.duyuru_lay.setContentsMargins(22, 16, 22, 16)
        self.duyuru_lay.setSpacing(8)
        ana.addWidget(self.panel_duyuru)            # kutu boş olsa da HER ZAMAN görünür (boşken kısa bir açıklama yazar)

        self.panel_benim_gunum = QFrame()
        self.panel_benim_gunum.setObjectName("kart")
        self.benim_gunum_lay = QVBoxLayout(self.panel_benim_gunum)
        self.benim_gunum_lay.setContentsMargins(22, 16, 22, 16)
        self.benim_gunum_lay.setSpacing(6)
        ana.addWidget(self.panel_benim_gunum)       # kutu boş olsa da HER ZAMAN görünür (boşken kısa bir açıklama yazar)

        # ---- 2. ÖZET KARTLARI ----
        self.kartlar = {}
        tanimlar = [("BUGÜNKÜ RANDEVU", "randevu", "calendar", "#1D4ED8", "#DBEAFE")]
        if cihaz_ozeti:
            tanimlar += [
                ("BUGÜNKÜ REZERVASYON", "rezervasyon", "pin", "#6D28D9", "#EDE9FE"),
                ("KULLANILABİLİR CİHAZ", "aktif_cihaz", "check-square", "#15803D", "#DCFCE7"),
                ("BAKIMDAKİ CİHAZ", "bakimdaki_cihaz", "wrench", "#B45309", "#FEF3C7"),
                ("KALİBRASYONDAKİ CİHAZ", "kalibrasyondaki_cihaz", "ruler", "#0E7490", "#CFFAFE"),
                ("ARIZALI CİHAZ", "arizali_cihaz", "warning", "#B91C1C", "#FEE2E2"),
            ]
        self.kart_grid = QGridLayout()
        self.kart_grid.setSpacing(18)
        self.kart_widgetleri = []
        for baslik, anahtar, ikon, renk, zemin in tanimlar:
            kart, lbl_deger, lbl_alt = self._kart(baslik, ikon, renk, zemin)
            self.kartlar[anahtar] = (lbl_deger, lbl_alt)
            self.kart_widgetleri.append(kart)
            self._karti_baglantila(kart, anahtar)
        self._kartlari_diz(self._kolon_sayisi(0))
        ana.addLayout(self.kart_grid)

        # ---- 2b. GÜN SEÇİCİ: Bugün | Yarın | Bu hafta (randevu, rezervasyon ve etkinlik panelleri için) ----
        secici = QHBoxLayout()
        secici.setSpacing(8)
        self.aralik_dugmeleri = {}
        for anahtar, metin in (("bugun", "Bugün"), ("yarin", "Yarın"), ("hafta", "Bu hafta (7 gün)")):
            dugme = QPushButton(metin)
            dugme.setCheckable(True)
            dugme.setChecked(anahtar == "bugun")
            dugme.setCursor(Qt.PointingHandCursor)
            dugme.setStyleSheet(
                "QPushButton { background: #EEF4FF; color: #3B5BA9; border: none; border-radius: 14px; "
                "font-size: 12px; font-weight: 700; padding: 7px 16px; } "
                "QPushButton:checked { background: #1D4ED8; color: white; } "
                "QPushButton:hover:!checked { background: #DBE7FF; }")
            dugme.setProperty("aralik", anahtar)
            dugme.clicked.connect(self._aralik_dugmesi_tiklandi)          # lambda KULLANILMAZ: panelle döngü kurar, kapanışta çökme yapar
            self.aralik_dugmeleri[anahtar] = dugme
            secici.addWidget(dugme)
        secici.addStretch()
        ana.addLayout(secici)

        # ---- 3. RANDEVULAR  |  CİHAZ REZERVASYONLARI ----
        bugun = datetime.date.today()
        tarih = f"{bugun.day} {AYLAR[bugun.month - 1]} {bugun.year}"

        self.tablo_randevu = _tablo_olustur(["SAAT", "DANIŞAN KODU", "PSİKOLOG", "ODA", "DURUM"])
        self.lbl_randevu_bos = QLabel("Bugün için kayıtlı randevu bulunmuyor.")
        panel_randevu = self.panel_randevu = self._panel("Danışan Randevuları", tarih,
                                    self.tablo_randevu, self.lbl_randevu_bos)

        if self.rezervasyon_paneli:
            self.tablo_rez = _tablo_olustur(["SAAT", "CİHAZ", "REZERVE EDEN", "ODA"])
            cihaz_hucresi_uygula(self.tablo_rez, 1, en_az_satir_yuksekligi=0)      # ad üstte, kod altta (satır yüksekliği değişmez)
            self.lbl_rez_bos = QLabel("Bugün için cihaz rezervasyonu bulunmuyor.")
            panel_rez = self.panel_rez = self._panel("Cihaz Rezervasyonları", tarih,
                                    self.tablo_rez, self.lbl_rez_bos)
            self.yan_yana = QBoxLayout(QBoxLayout.LeftToRight)
            self.yan_yana.setSpacing(18)
            self.yan_yana.addWidget(panel_randevu, 1, Qt.AlignTop)
            self.yan_yana.addWidget(panel_rez, 1, Qt.AlignTop)
            ana.addLayout(self.yan_yana)
        else:
            ana.addWidget(panel_randevu)

        # ---- 3b. BUGÜNKÜ ODA ETKİNLİKLERİ ----
        if self.etkinlik_paneli:
            self.tablo_etkinlik = _tablo_olustur(["SAAT", "ETKİNLİK", "ODA", "KATILIMCI"])
            self.lbl_etkinlik_bos = QLabel("Bugün için oda etkinliği bulunmuyor.")
            self.panel_etkinlik = self._panel("Oda Etkinlikleri", tarih, self.tablo_etkinlik, self.lbl_etkinlik_bos)
            ana.addWidget(self.panel_etkinlik)

        # ---- 4. YAKLAŞAN BAKIM / KALİBRASYON ----
        if cihaz_ozeti:
            self.tablo_islem = _tablo_olustur(["CİHAZ", "İŞLEM", "SON TARİH", "KALAN SÜRE"])
            cihaz_hucresi_uygula(self.tablo_islem, 0, en_az_satir_yuksekligi=0)    # ad üstte, kod altta (satır yüksekliği değişmez)
            self._islem_hedefleri = []          # tablodaki her satırın açacağı sayfa
            self.tablo_islem.cellClicked.connect(self._islem_satiri_tiklandi)
            if self._sayfa_ac is not None:
                self.tablo_islem.viewport().setCursor(Qt.PointingHandCursor)
            self.lbl_islem_bos = QLabel("Uyarı süresine giren ya da geciken bakım veya kalibrasyon yok.")
            self.panel_islem = self._panel("Yaklaşan ve Geciken Bakım/Kalibrasyonlar",
                                           "uyarı süresi içinde ve geciken", self.tablo_islem, self.lbl_islem_bos)
            ana.addWidget(self.panel_islem)

        self.tarih_panelleri = [(panel_randevu, "")]
        if self.rezervasyon_paneli:
            self.tarih_panelleri.append((panel_rez, ""))
        if self.etkinlik_paneli:
            self.tarih_panelleri.append((self.panel_etkinlik, ""))

        self._son_yukleme = 0
        self.yenile()

        # Ekran açık kalırsa her dakika kendini günceller (gün değişimi dahil)
        self.zamanlayici = QTimer(self)
        self.zamanlayici.timeout.connect(self.yenile)
        self.zamanlayici.start(60_000)
    # ------------------------------------------------------------------
    def _kolon_sayisi(self, genislik):
        """Geniş pencerede kartların hepsi tek sırada; daraldıkça 3, 2 ve 1 sütuna iner (sayfa sağdan taşmaz)."""
        kart_sayisi = len(self.kart_widgetleri)
        genis_esik = 1450 if kart_sayisi <= 5 else 1750
        if genislik >= genis_esik:
            kolon = 6
        elif genislik >= 820:
            kolon = 3
        elif genislik >= 520:
            kolon = 2
        else:
            kolon = 1
        return max(1, min(kart_sayisi, kolon))

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
        if self.rezervasyon_paneli:
            yon = QBoxLayout.LeftToRight if genislik >= 1200 else QBoxLayout.TopToBottom
            self.yan_yana.setDirection(yon)

    # ------------------------------------------------------------------
    def _karti_baglantila(self, kart, anahtar):
        """Kart, kart_ac verilmişse ve kullanıcı hedef sayfaya girebiliyorsa tıklanabilir olur."""
        sayfa, _durum, ipucu = KART_HEDEFLERI[anahtar]
        kart.setProperty("anahtar", anahtar)
        kart.setStyleSheet(KART_TIKLANABILIR_STILI)
        kart.tiklandi.connect(self._kart_tiklandi)
        kart.tiklanabilir_yap(self._kart_ac is not None and self._sayfa_izinli(sayfa), ipucu)

    def _kart_tiklandi(self):
        kart = self.sender()
        hedef = KART_HEDEFLERI.get(kart.property("anahtar")) if kart is not None else None
        if hedef is not None and self._kart_ac is not None:
            self._kart_ac(hedef[0], hedef[1])

    def _kart(self, baslik, ikon, renk, zemin):
        kart = TiklanabilirKart()
        kart.setObjectName("kart")
        ana = QHBoxLayout(kart)
        ana.setContentsMargins(18, 16, 18, 16)
        ana.setSpacing(14)

        chip = QLabel()
        chip.setFixedSize(46, 46)
        chip.setAlignment(Qt.AlignCenter)
        chip.setPixmap(renkli_ikon_pixmap(ikon, renk, zemin))       # yumuşak renkli zemin + çizgi ikon (emoji yok)

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
        tarih = self._aralik_rozeti()
        for panel, ikon in self.tarih_panelleri:
            panel.rozet.setText(f"{ikon}  {tarih}".strip())
        self._son_yukleme = time.monotonic()
        self.verileri_yukle()

    @staticmethod
    def _tarih_metni(gun):
        return f"{gun.day} {AYLAR[gun.month - 1]} {gun.year}"

    def _aralik_rozeti(self):
        bugun = datetime.date.today()
        if self.aralik == "yarin":
            return f"Yarın · {self._tarih_metni(bugun + datetime.timedelta(days=1))}"
        if self.aralik == "hafta":
            son = bugun + datetime.timedelta(days=6)
            return f"{bugun.day} {AYLAR[bugun.month - 1]} – {son.day} {AYLAR[son.month - 1]}"
        return self._tarih_metni(bugun)

    def _aralik_yolu(self, yol):
        """Bugün için yol olduğu gibi kalır (eski sunucuyla da çalışır); yarın/hafta için aralık eklenir."""
        return yol if self.aralik == "bugun" else f"{yol}?aralik={self.aralik}"

    def _aralik_adi(self):
        """Boş liste metinleri için: "Bugün" / "Yarın" / "Önümüzdeki 7 gün"."""
        return {"bugun": "Bugün", "yarin": "Yarın", "hafta": "Önümüzdeki 7 gün"}[self.aralik]

    def _aralik_dugmesi_tiklandi(self):
        aralik = self.sender().property("aralik") if self.sender() is not None else None
        if aralik:
            self.aralik_sec(aralik)

    def aralik_sec(self, aralik):
        """Gün seçici: randevu, rezervasyon ve etkinlik panelleri seçilen güne göre yeniden yüklenir."""
        if aralik not in self.aralik_dugmeleri:
            return
        self.aralik = aralik
        for anahtar, dugme in self.aralik_dugmeleri.items():
            dugme.setChecked(anahtar == aralik)
        self.yenile()

    def _saat_metni(self, kayit):
        """Haftalık görünümde saatin önüne gün-ay eklenir (rezervasyonda sunucu zaten tarihli verir)."""
        saat = f"{kayit['baslangic']} – {kayit['bitis']}"
        if self.aralik == "hafta" and kayit.get("tarih") and "." not in kayit["baslangic"]:
            return f"{kayit['tarih']}  {saat}"
        return saat

    def showEvent(self, olay):
        """Ana panele her dönüşte (başka sayfadan gelince) veriyi tazeler."""
        super().showEvent(olay)
        if time.monotonic() - self._son_yukleme > 5:
            self.yenile()

    def verileri_yukle(self):
        self._duyurulari_yukle()
        self._benim_gunumu_yukle()
        if self.cihaz_ozeti:
            self._ozet_yukle()
        self._randevulari_yukle()
        if self.rezervasyon_paneli:
            self._rezervasyonlari_yukle()
        if self.etkinlik_paneli:
            self._etkinlikleri_yukle()
        if self.cihaz_ozeti:
            self._islemleri_yukle()
            self._parola_taleplerini_yukle()
            self._bildirimleri_olustur()

    def _ozet_yukle(self):
        try:
            self.ozet = self._getir("/api/dashboard/ozet")
        except Exception:
            for anahtar in (
                "aktif_cihaz", "bakimdaki_cihaz",
                "kalibrasyondaki_cihaz", "arizali_cihaz"
            ):
                deger, alt = self.kartlar[anahtar]
                deger.setText("?")
                alt.setText("Özet yüklenemedi.")
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
            # İptal edilen randevular ana panelde gösterilmez (sunucu da döndürmez; eski sunucuya karşı burada da süzülür).
            randevular = [r for r in self._getir(self._aralik_yolu("/api/dashboard/bugunku-randevular")) if r["durum"] != "IPTAL_EDILDI"]
            # Özet kartı her zaman BUGÜNÜ sayar; başka gün seçiliyse bugün için ayrıca sorulur.
            bugunku = randevular if self.aralik == "bugun" else [r for r in self._getir("/api/dashboard/bugunku-randevular") if r["durum"] != "IPTAL_EDILDI"]
        except Exception as e:
            logger.warning("Randevu listesi yüklenemedi: %s", e)
            lbl_deger.setText("?")
            self.lbl_randevu_bos.setText("Randevular yüklenemedi.")
            self._liste_goster(self.tablo_randevu, self.lbl_randevu_bos, 0)
            self._kaydirma_ipucu_guncelle(self.panel_randevu, 0)
            return

        lbl_deger.setText(str(len(bugunku)))
        lbl_alt.setText("Bugün planlanan seans")
        self.lbl_randevu_bos.setText(f"{self._aralik_adi()} için kayıtlı randevu bulunmuyor.")
        kaydirilabilir = self._liste_goster(self.tablo_randevu, self.lbl_randevu_bos, len(randevular), TABLO_GORUNEN_SATIR)
        self._kaydirma_ipucu_guncelle(self.panel_randevu, len(randevular) if kaydirilabilir else 0)
        for i, r in enumerate(randevular):
            metin, renk, arka = DURUM_METIN.get(r["durum"], (r["durum"], "#374151", "#F3F4F6"))
            self.tablo_randevu.setItem(i, 0, _item(self._saat_metni(r), kalin=True))
            self.tablo_randevu.setItem(i, 1, _item(r["danisan_kod_id"]))
            self.tablo_randevu.setItem(i, 2, _item(r["psikolog"]))
            self.tablo_randevu.setItem(i, 3, _item(r["oda"]))
            _hap(self.tablo_randevu, i, 4, metin, renk, arka)

    def _rezervasyonlari_yukle(self):
        lbl_deger, lbl_alt = self.kartlar.get("rezervasyon") or (QLabel(), QLabel())          # özet kartı yalnızca cihaz özeti yetkisi olanlarda var
        try:
            rezervasyonlar = self._getir(self._aralik_yolu("/api/dashboard/bugunku-rezervasyonlar"))
            bugunku = rezervasyonlar if self.aralik == "bugun" else self._getir("/api/dashboard/bugunku-rezervasyonlar")
        except Exception as e:
            logger.warning("Rezervasyon listesi yüklenemedi: %s", e)
            lbl_deger.setText("?")
            self.lbl_rez_bos.setText("Rezervasyonlar yüklenemedi.")
            self._liste_goster(self.tablo_rez, self.lbl_rez_bos, 0)
            self._kaydirma_ipucu_guncelle(self.panel_rez, 0)
            return

        # Sunucu rezerve eden adını yalnızca cihaz yöneticisine / rezervasyon yapana verir; yalnızca görüntüleyen kullanıcıda sütun gizlenir.
        self.tablo_rez.setColumnHidden(2, bool(rezervasyonlar) and all(r.get("rezerve_eden") is None for r in rezervasyonlar))
        lbl_deger.setText(str(len(bugunku)))
        lbl_alt.setText("Bugün rezerve edilen cihaz")
        self.lbl_rez_bos.setText(f"{self._aralik_adi()} için cihaz rezervasyonu bulunmuyor.")
        kaydirilabilir = self._liste_goster(self.tablo_rez, self.lbl_rez_bos, len(rezervasyonlar), TABLO_GORUNEN_SATIR)
        self._kaydirma_ipucu_guncelle(self.panel_rez, len(rezervasyonlar) if kaydirilabilir else 0)
        for i, r in enumerate(rezervasyonlar):
            self.tablo_rez.setItem(i, 0, _item(self._saat_metni(r), kalin=True))
            rez_cihaz = _item(r["cihaz"])
            rez_cihaz.setToolTip(cihaz_ipucu(r["cihaz"]))                          # "…" ile kısalan ad/kod ipucunda tam
            self.tablo_rez.setItem(i, 1, rez_cihaz)
            self.tablo_rez.setItem(i, 2, _item(r.get("rezerve_eden") or "—"))
            self.tablo_rez.setItem(i, 3, _item(r["oda"]))

    def _etkinlikleri_yukle(self):
        try:
            etkinlikler = self._getir(self._aralik_yolu("/api/dashboard/bugunku-etkinlikler"))
        except Exception as e:
            logger.warning("Etkinlik listesi yüklenemedi: %s", e)
            self.lbl_etkinlik_bos.setText("Etkinlikler yüklenemedi.")
            self._liste_goster(self.tablo_etkinlik, self.lbl_etkinlik_bos, 0)
            self._kaydirma_ipucu_guncelle(self.panel_etkinlik, 0)
            return

        self.lbl_etkinlik_bos.setText(f"{self._aralik_adi()} için oda etkinliği bulunmuyor.")
        kaydirilabilir = self._liste_goster(self.tablo_etkinlik, self.lbl_etkinlik_bos, len(etkinlikler), TABLO_GORUNEN_SATIR)
        self._kaydirma_ipucu_guncelle(self.panel_etkinlik, len(etkinlikler) if kaydirilabilir else 0)
        for i, ek in enumerate(etkinlikler):
            self.tablo_etkinlik.setItem(i, 0, _item(self._saat_metni(ek), kalin=True))
            ad = _item(ek["etkinlik"])
            ad.setToolTip(ek["etkinlik"])                                           # uzun ad "…" ile kısalır, ipucunda tam
            self.tablo_etkinlik.setItem(i, 1, ad)
            self.tablo_etkinlik.setItem(i, 2, _item(ek["oda"]))
            self.tablo_etkinlik.setItem(i, 3, _item("—" if ek.get("katilimci") is None else str(ek["katilimci"])))

    # ------------------------------------------------------------------
    # Duyurular ve "Benim günüm"
    # ------------------------------------------------------------------
    @staticmethod
    def _kutuyu_bosalt(lay):
        while lay.count():
            oge = lay.takeAt(0)
            w = oge.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif oge.layout() is not None:
                DashboardEkrani._kutuyu_bosalt(oge.layout())

    def _duyurulari_yukle(self):
        try:
            duyurular = self._getir("/api/duyurular")
            if not isinstance(duyurular, list):
                raise ValueError("Geçersiz duyuru listesi")
            self._duyuru_hata = False
        except Exception as e:
            logger.warning("Duyurular yüklenemedi: %s", e)
            duyurular = []
            self._duyuru_hata = True
        self.duyurular = duyurular
        self._duyurulari_ciz()

    DUGME_STILI = ("QPushButton { background: %s; color: %s; border: none; border-radius: 8px; "
                   "font-size: 11px; font-weight: 700; padding: 4px 10px; } QPushButton:hover { background: %s; }")

    def _duyuru_dugmesi(self, metin, ad, duyuru_id, renkler, yuva):
        dugme = QPushButton(metin)
        dugme.setObjectName(ad)
        dugme.setProperty("duyuru_id", duyuru_id)
        dugme.setCursor(Qt.PointingHandCursor)
        dugme.setStyleSheet(self.DUGME_STILI % renkler)
        dugme.clicked.connect(yuva)                                   # lambda KULLANILMAZ (panelle döngü kurar); düğme kimliği özellikten okunur
        return dugme

    def _duyuru_karti(self, d, okundu):
        """Tek duyuru kartı. Okunmamış: "Okudum" düğmesi; okunmuş (sönük): "Tekrar göster". Yetkili kişide ayrıca "Kaldır" (herkesten siler)."""
        kutu = QFrame()
        kutu.setObjectName("duyuruSatiri")
        kutu.setStyleSheet("QFrame#duyuruSatiri { background: %s; border-radius: 10px; }" % ("#F8FAFC" if okundu else "#F3F7FF"))
        lay = QVBoxLayout(kutu)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(3)
        ust_satir = QHBoxLayout()
        if not okundu:                                                  # okunmamış duyuru: emoji yerine küçük "Yeni" rozeti
            rozet = QLabel("Yeni")
            rozet.setObjectName("yeniRozeti")
            rozet.setFixedHeight(18)
            rozet.setAlignment(Qt.AlignCenter)
            rozet.setStyleSheet("background: #DBEAFE; color: #1D4ED8; font-size: 10px; font-weight: 800; border-radius: 9px; padding: 0px 9px;")
            ust_satir.addWidget(rozet, 0, Qt.AlignVCenter)
        ad = QLabel(str(d.get("baslik", "")))
        ad.setStyleSheet("font-size: 14px; font-weight: 800; color: %s;" % ("#64748B" if okundu else "#0A1F5C"))
        ad.setWordWrap(True)
        ust_satir.addWidget(ad, 1)
        kimlik = d.get("duyuru_id")
        if "okundu" not in d:
            pass                                                        # eski sunucu: okundu işareti desteklenmez, düğme gösterilmez
        elif okundu:
            ust_satir.addWidget(self._duyuru_dugmesi("Tekrar göster", "tekrarGosterDugmesi", kimlik, ("#E2E8F0", "#334155", "#CBD5E1"),
                                                     self._duyuru_geri_al_tiklandi), 0)
        else:
            ust_satir.addWidget(self._duyuru_dugmesi("Okudum", "okunduDugmesi", kimlik, ("#DCFCE7", "#166534", "#BBF7D0"),
                                                     self._duyuru_okundu_tiklandi), 0)
        if self.duyuru_yonetebilir and d.get("yonetebilir"):
            ust_satir.addWidget(self._duyuru_dugmesi("Kaldır", "kaldirDugmesi", kimlik, ("#FEE2E2", "#991B1B", "#FECACA"),
                                                     self._duyuru_kaldir_tiklandi), 0)
        lay.addLayout(ust_satir)
        metin = QLabel(str(d.get("metin", "")))
        metin.setWordWrap(True)
        metin.setStyleSheet("font-size: 13px; color: %s;" % ("#64748B" if okundu else "#0F2552"))
        lay.addWidget(metin)
        ayrinti = d.get("tarih", "")
        if d.get("yazan"):
            ayrinti += f"  ·  {d['yazan']}"
        if d.get("son_gecerlilik"):
            ayrinti += f"  ·  {d['son_gecerlilik']} tarihine kadar"
        alt = QLabel(ayrinti)
        alt.setStyleSheet("font-size: 11px; color: #6B7FA8;")
        lay.addWidget(alt)
        return kutu

    @staticmethod
    def _baslik_ikonu(ikon, renk, zemin):
        """Panel başlığının solundaki yumuşak renkli zeminli çizgi ikon (kartlardakiyle aynı stil; emoji yok)."""
        etiket = QLabel()
        etiket.setObjectName("panelBaslikIkonu")
        etiket.setFixedSize(30, 30)
        etiket.setAlignment(Qt.AlignCenter)
        etiket.setPixmap(renkli_ikon_pixmap(ikon, renk, zemin, kutu=30, ikon_boyutu=17, yaricap=9))
        return etiket

    def _duyurulari_ciz(self):
        """Okunmamış duyurular üstte; okunanlar "Okunan duyurular" düğmesinin arkasında gizli (silinmez, istenirse yeniden gösterilir)."""
        self._kutuyu_bosalt(self.duyuru_lay)
        okunmamis = [d for d in self.duyurular if not d.get("okundu")]          # "okundu" alanı yoksa (eski sunucu) hepsi okunmamış sayılır
        okunan = [d for d in self.duyurular if d.get("okundu")]
        self.panel_duyuru.setVisible(True)                      # duyuru yoksa da kutu görünür ("Şu an yayında duyuru yok")

        ust = QHBoxLayout()
        ust.addWidget(self._baslik_ikonu("megaphone", "#1D4ED8", "#DBEAFE"))
        baslik = QLabel("Duyurular" + (f"  ({len(okunmamis)} yeni)" if okunmamis else ""))
        baslik.setObjectName("duyuruBasligi")
        baslik.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1F5C;")
        ust.addWidget(baslik)
        ust.addStretch()
        if len(okunmamis) > 1 and all("okundu" in d for d in okunmamis):
            ust.addWidget(self._duyuru_dugmesi("Hepsini okudum", "hepsiniOkuduDugmesi", None, ("#DCFCE7", "#166534", "#BBF7D0"),
                                               self._tumunu_okundu_tiklandi))
        if self.duyuru_yonetebilir:
            yeni = QPushButton("＋ Yeni duyuru")
            yeni.setObjectName("yeniDuyuruDugmesi")
            yeni.setCursor(Qt.PointingHandCursor)
            yeni.setStyleSheet("QPushButton { background: #1D4ED8; color: white; border: none; border-radius: 10px; "
                               "font-size: 12px; font-weight: 700; padding: 6px 14px; } QPushButton:hover { background: #1E40AF; }")
            yeni.clicked.connect(self._yeni_duyuru)
            ust.addWidget(yeni)
        ust_kap = QWidget()
        ust.setContentsMargins(0, 0, 0, 0)
        ust_kap.setLayout(ust)
        self.duyuru_lay.addWidget(ust_kap)

        if not self.duyurular:
            bos = QLabel("Duyurular yüklenemedi." if self._duyuru_hata else "Şu an yayında duyuru yok.")
            bos.setObjectName("duyuruBos")
            bos.setStyleSheet("font-size: 13px; color: #8A9BC0; padding: 6px;")
            self.duyuru_lay.addWidget(bos)
            return

        for d in okunmamis:
            self.duyuru_lay.addWidget(self._duyuru_karti(d, okundu=False))
        if not okunmamis:
            tamam = QLabel("✅  Tüm duyuruları okudunuz.")
            tamam.setObjectName("duyuruHepsiOkundu")
            tamam.setStyleSheet("background: #DCFCE7; color: #166534; border-radius: 10px; font-size: 13px; font-weight: 600; padding: 10px 14px;")
            self.duyuru_lay.addWidget(tamam)

        if okunan:
            dugme = QPushButton(f"{'▴' if self._okunanlar_acik else '▾'}  Okunan duyurular ({len(okunan)})")
            dugme.setObjectName("okunanlariGosterDugmesi")
            dugme.setCursor(Qt.PointingHandCursor)
            dugme.setStyleSheet("QPushButton { background: transparent; color: #3B5BA9; border: none; font-size: 12px; font-weight: 700; "
                                "text-align: left; padding: 4px 2px; } QPushButton:hover { color: #1D4ED8; }")
            dugme.clicked.connect(self._okunanlari_degistir)
            self.duyuru_lay.addWidget(dugme)
            if self._okunanlar_acik:
                for d in okunan:
                    self.duyuru_lay.addWidget(self._duyuru_karti(d, okundu=True))

    def _okunanlari_degistir(self):
        self._okunanlar_acik = not self._okunanlar_acik
        self._duyurulari_ciz()

    def duyurulari_yenile(self):
        """Dışarıdan (örn. zil panelinde okundu işaretlenince) duyuru kutusunu sunucudan yeniden yükler."""
        self._duyurulari_yukle()

    def _okundu_istegi(self, yontem, yol):
        """Okundu işareti isteği; başarısızsa kullanıcıya uyarı gösterilir. Başarılıysa True."""
        try:
            yanit = oturum_kontrollu_istek(yontem, f"{self.api_url}{yol}", headers=self.basliklar, timeout=10)
            if oturum_hatasi_mi(yanit):
                return False
            yanit.raise_for_status()
            return True
        except Exception as hata:
            logger.warning("Duyuru okundu işareti başarısız: %s", hata)
            QMessageBox.warning(self, "İşlem yapılamadı", istek_hatasi_metni(hata, "Duyuru işaretlenemedi."))
            return False

    def _duyuru_okundu_tiklandi(self):
        kimlik = self.sender().property("duyuru_id") if self.sender() is not None else None
        if kimlik is not None and self._okundu_istegi("POST", f"/api/duyurular/{int(kimlik)}/okundu"):
            self._duyurulari_yukle()
            self.duyuru_degisti.emit()                                   # zil sayısı güncellensin

    def _duyuru_geri_al_tiklandi(self):
        kimlik = self.sender().property("duyuru_id") if self.sender() is not None else None
        if kimlik is not None and self._okundu_istegi("DELETE", f"/api/duyurular/{int(kimlik)}/okundu"):
            self._duyurulari_yukle()
            self.duyuru_degisti.emit()

    def _tumunu_okundu_tiklandi(self):
        if self._okundu_istegi("POST", "/api/duyurular/okundu"):
            self._duyurulari_yukle()
            self.duyuru_degisti.emit()

    def _yeni_duyuru(self):
        if DuyuruDiyalogu(self.api_url, self.token, self).exec() == QDialog.Accepted:
            self._duyurulari_yukle()
            self.duyuru_degisti.emit()

    def _duyuru_kaldir_tiklandi(self):
        duyuru_id = self.sender().property("duyuru_id") if self.sender() is not None else None
        if duyuru_id is not None and duyuru_kaldir(self.api_url, self.token, duyuru_id, self):
            self._duyurulari_yukle()
            self.duyuru_degisti.emit()

    def _benim_gunumu_yukle(self):
        try:
            veri = self._getir("/api/dashboard/benim-gunum")
            if not isinstance(veri, dict):
                raise ValueError("Geçersiz yanıt")
        except Exception as e:
            logger.warning("Benim günüm yüklenemedi: %s", e)
            veri = {"randevular": [], "rezervasyonlar": []}
            self._benim_gunum_hata = True
        else:
            self._benim_gunum_hata = False
        self.benim_gunum = veri
        self._benim_gunumu_ciz()

    def _benim_gunumu_ciz(self):
        self._kutuyu_bosalt(self.benim_gunum_lay)
        randevular = self.benim_gunum.get("randevular") or []
        rezervasyonlar = self.benim_gunum.get("rezervasyonlar") or []
        isler = [i for i in (self.benim_gunum.get("isler") or []) if isinstance(i, dict) and i.get("metin")]
        self.panel_benim_gunum.setVisible(True)                                       # kaydınız yoksa da kutu görünür
        baslik = QLabel("Benim Günüm")
        baslik.setObjectName("benimGunumBasligi")
        baslik.setStyleSheet("font-size: 15px; font-weight: 800; color: #0A1F5C;")
        baslik_satiri = QHBoxLayout()
        baslik_satiri.setContentsMargins(0, 0, 0, 0)
        baslik_satiri.addWidget(self._baslik_ikonu("user", "#6D28D9", "#EDE9FE"))
        baslik_satiri.addWidget(baslik)
        baslik_satiri.addStretch()
        baslik_kap = QWidget()
        baslik_kap.setLayout(baslik_satiri)
        self.benim_gunum_lay.addWidget(baslik_kap)
        if not (randevular or rezervasyonlar or isler):
            bos = QLabel("Günlük bilgileriniz yüklenemedi." if self._benim_gunum_hata
                         else "Bugün ve yarın için size ait randevu ya da cihaz rezervasyonu yok.")
            bos.setObjectName("benimGunumBos")
            bos.setStyleSheet("font-size: 13px; color: #8A9BC0; padding: 6px;")
            self.benim_gunum_lay.addWidget(bos)
            return
        if isler:                                                                     # rol bazlı bekleyen işler (izne göre sunucu hesaplar)
            ust = QLabel("Bekleyen işlerim")
            ust.setObjectName("benimIslerBasligi")
            ust.setStyleSheet("font-size: 12px; font-weight: 800; color: #3B5BA9; padding-top: 4px;")
            self.benim_gunum_lay.addWidget(ust)
            for i in isler:
                uyari = i.get("onem") == "uyari"
                hedef = f"   →  {i['hedef']}" if i.get("hedef") else ""
                etiket = QLabel(f"{i['metin']}{hedef}")
                etiket.setObjectName("benimIsSatiri")
                etiket.setWordWrap(True)
                etiket.setStyleSheet("font-size: 13px; border-radius: 8px; padding: 7px 12px; " +
                                     ("color: #854D0E; background: #FEF3C7;" if uyari else "color: #0F2552; background: #F3F7FF;"))
                self.benim_gunum_lay.addWidget(etiket)
        for gun, gun_adi in (("bugun", "Bugün"), ("yarin", "Yarın")):
            satirlar = [f"{r['saat']}  ·  Randevu  ·  Danışan {r['danisan_kod_id']}  ·  {r['oda']}" for r in randevular if r.get("gun") == gun]
            satirlar += [f"{r['saat']}  ·  Cihaz  ·  {r['cihaz']}  ·  {r['oda']}" for r in rezervasyonlar if r.get("gun") == gun]
            if not satirlar:
                continue
            ust = QLabel(gun_adi)
            ust.setStyleSheet("font-size: 12px; font-weight: 800; color: #3B5BA9; padding-top: 4px;")
            self.benim_gunum_lay.addWidget(ust)
            for satir in satirlar:
                etiket = QLabel(satir)
                etiket.setStyleSheet("font-size: 13px; color: #0F2552; background: #F3F7FF; border-radius: 8px; padding: 7px 12px;")
                self.benim_gunum_lay.addWidget(etiket)

    def _islemleri_yukle(self):
        yukleme_hatasi = False
        try:
            self.islemler = self._getir("/api/dashboard/yaklasan-islemler")
            if not isinstance(self.islemler, list):
                raise ValueError("Geçersiz işlem listesi")
        except Exception:
            yukleme_hatasi = True
            self.islemler = []
        # Yetkisi olmayan sayfanın satırı hiç gösterilmez; her satır kendi sayfasına gider.
        gorunen = [(islem, self._islem_hedefi(islem)) for islem in self.islemler]
        gorunen = [(islem, hedef) for islem, hedef in gorunen if hedef is not None and self._sayfa_izinli(hedef)]
        self._islem_hedefleri = [hedef for _, hedef in gorunen]
        self.lbl_islem_bos.setText(
            "Yaklaşan işlemler yüklenemedi. Lütfen yeniden deneyin."
            if yukleme_hatasi
            else "Uyarı süresine giren ya da geciken bakım veya kalibrasyon yok."
        )
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
            logger.warning("Parola talepleri yüklenemedi: %s", e)

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
        """[(çizgi ikon adı, metin, yazı rengi, arka plan, hedef sayfa)] — yetkisiz olunan sayfaların bildirimleri çıkarılır."""
        satirlar = []
        if self._sayfa_izinli(self.PAROLA_SAYFASI):
            for talep in self.parola_talepleri:
                satirlar.append(("key", f"{talep['kullanici_adi']} parola sıfırlama istedi "
                                       f"({self._bekleme_metni(talep.get('bekleme_dakika'))})",
                                 "#1E3A8A", "#DBEAFE", self.PAROLA_SAYFASI))
        acik_ariza = self.ozet.get("acik_ariza_sayisi", 0)
        if acik_ariza and self._sayfa_izinli(self.ARIZA_SAYFASI):
            satirlar.append(("warning", f"{acik_ariza} açık arıza kaydı çözüm bekliyor.", "#991B1B", "#FEE2E2",
                             self.ARIZA_SAYFASI))
        for islem in self.islemler:
            hedef = self._islem_hedefi(islem)
            if hedef is None or not self._sayfa_izinli(hedef):
                continue
            gun = islem["kalan_gun"]   # liste zaten kayıt başına uyarı süresine göre süzülmüş ve sıralı
            zaman = "bugün" if gun == 0 else (f"{-gun} gün gecikti" if gun < 0 else f"{gun} gün içinde")
            kritik = gun <= 5
            satirlar.append((
                "warning" if kritik else "wrench",
                f"{islem['cihaz_adi']}  —  {islem['islem_turu']} {zaman} ({islem['tarih']})",
                "#991B1B" if kritik else "#854D0E",
                "#FEE2E2" if kritik else "#FEF3C7",
                hedef))
        return satirlar

    def _bildirim_dugmesi(self, metin, renk, arka, hedef, ikon=None):
        """Tıklanınca ilgili sayfayı açan bildirim satırı. Tıklama tek bir yuvaya gider (lambda kullanılmaz)."""
        dugme = QPushButton(f"{metin}   →")
        if ikon:
            dugme.setIcon(cizgi_ikonu(ikon, renk))
            dugme.setIconSize(ikon_boyutu())
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
        bell = QLabel()
        bell.setPixmap(ikon_pixmap("bell", "#0A1F5C", 18))
        bell.setFixedSize(18, 18)
        ust.addWidget(bell)
        baslik = QLabel(f"Bildirimler  ({len(satirlar)})" if satirlar else "Bildirimler")
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
            ok = QFrame()
            ok.setStyleSheet("QFrame { background: #DCFCE7; border-radius: 10px; } "
                             "QLabel { background: transparent; color: #166534; font-size: 13px; font-weight: 600; }")
            ok_lay = QHBoxLayout(ok)
            ok_lay.setContentsMargins(14, 10, 14, 10)
            ok_lay.setSpacing(8)
            tik = QLabel()
            tik.setPixmap(ikon_pixmap("circle-check", "#166534", 16))
            tik.setFixedSize(16, 16)
            ok_lay.addWidget(tik)
            ok_yazi = QLabel("Bekleyen uyarı yok. Yaklaşan ya da geciken bakım, kalibrasyon ve açık arıza bulunmuyor.")
            ok_yazi.setWordWrap(True)
            ok_lay.addWidget(ok_yazi, 1)
            self.bildirim_lay.addWidget(ok)
            return

        satir_kutusu = QWidget()
        satir_lay = QVBoxLayout(satir_kutusu)
        satir_lay.setContentsMargins(0, 0, 0, 0)
        satir_lay.setSpacing(8)
        dugmeler = [self._bildirim_dugmesi(metin, renk, arka, hedef, ikon)
                    for ikon, metin, renk, arka, hedef in satirlar]
        for dugme in dugmeler:
            satir_lay.addWidget(dugme)

        if not fazla:
            self.bildirim_lay.addWidget(satir_kutusu)
            return

        # Çok bildirim: ilk BILDIRIM_SINIRI satır görünür, gerisi büyük ve renkli bir kaydırma çubuğuyla kaydırılır.
        kaydirma = KaydirmaKilitliAlan()
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
