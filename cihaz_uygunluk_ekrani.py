"""Cihaz Uygunluğu: haftalık takvim görünümü.

Her cihaz için haftanın her günü tek bakışta görünür: müsait, kısmen dolu, dolu, bakımda,
kalibrasyonda, arızalı ya da kullanım dışı. Bir güne tıklayınca saat çizelgesi ve nedenleri açılır.
"Müsait cihaz bul" ile belirli bir gün ve saat aralığında boş cihazlar listelenir.

Veri `/api/cihaz-uygunluk` ucundan gelir (yalnızca CIHAZ_UYGUNLUK_GORUNTULE izni gerekir; kişi adı,
işlem açıklaması gibi ayrıntılar içermez). Rezervasyon, arıza, bakım ve kalibrasyon sayfalarına
geçiş düğmeleri yalnızca kullanıcının o işlem için yetkisi varsa görünür.
"""
from datetime import date, datetime, time, timedelta

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QStyledItemDelegate, QTableWidgetItem, QVBoxLayout, QWidget)

import cihaz_uygunluk_mantigi as mantik
from api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from cihaz_rezervasyon_ekranlari import varsayilan_rezervasyon_zamanlari
from tablo_tasarimi import (FORM_STIL, bos_mesaj_olustur, sayfa_basligi, sayi_cipi, tablo_olustur,
                            yenile_butonu_olustur)

# durum kodu -> (yazı rengi, arka plan)
RENKLER = {
    mantik.MUSAIT: ("#166534", "#DCFCE7"),
    mantik.KISMEN: ("#1D4ED8", "#DBEAFE"),
    mantik.DOLU: ("#1E3A8A", "#93C5FD"),
    mantik.REZERVASYON: ("#1E3A8A", "#93C5FD"),
    mantik.BAKIM: ("#854D0E", "#FEF3C7"),
    mantik.KALIBRASYON: ("#6D28D9", "#EDE9FE"),
    mantik.ARIZA: ("#991B1B", "#FEE2E2"),
    mantik.KULLANIM_DISI: ("#475569", "#E2E8F0"),
}
KISA_AD = {**mantik.KOD_ADLARI, mantik.REZERVASYON: "Rezerve"}
FILTRELER = (("Tüm cihazlar", "TUMU"), ("Bugün müsait olanlar", "BUGUN_MUSAIT"), ("Sorunlu olanlar", "SORUNLU"))

SUTUN_CIHAZ, SUTUN_SU_AN, ILK_GUN_SUTUNU, UYARI_SUTUNU = 0, 1, 2, 9
SAAT_SECENEKLERI = [f"{h:02d}:{d:02d}" for h in range(8, 19) for d in (0, 30)]

ARAC_STILI = """
    QPushButton#gezinti { background: #EEF4FF; color: #1D4ED8; border: 1px solid #C7D9FB; border-radius: 10px;
                          padding: 8px 14px; font-size: 13px; font-weight: 700; }
    QPushButton#gezinti:hover { background: #DBEAFE; }
    QPushButton#birincil { background: #2563EB; color: white; border: none; border-radius: 10px;
                           padding: 9px 16px; font-size: 13px; font-weight: 800; }
    QPushButton#birincil:hover { background: #1D4ED8; }
    QLabel#hafta { color: #0A1F5C; font-size: 15px; font-weight: 800; padding: 0 6px; }
    QLabel#etiket { color: #1E3A8A; font-size: 12px; font-weight: 700; }
    QComboBox, QDateEdit { background: white; color: #0F2552; border: 1px solid #C7D9FB; border-radius: 10px;
                           padding: 7px 10px; font-size: 13px; }
    QComboBox QAbstractItemView { background: white; color: #0F2552; selection-background-color: #2563EB;
                                  selection-color: white; }
"""


UYARI_SATIR_KARAKTER = 36        # uyarı sütununda bir satıra sığan yaklaşık karakter sayısı (sütun 250 px)


def satir_yuksekligi(uyari_metinleri):
    """Satır yüksekliği: varsayılan 54 px; uyarı metni sütunda kaç satıra sararsa ona göre uzar.

    Yükseklik sütun genişliğine bağlı ölçülmez (pencere açılmadan genişlikler bilinmez), tahmin edilir.
    """
    satir = sum(-(-(len(m) + 2) // UYARI_SATIR_KARAKTER) for m in uyari_metinleri)       # tavan bölme
    return max(54, 22 + 17 * satir)


def _renkli(item, kod, kalin=False):
    fg, bg = RENKLER[kod]
    item.setForeground(QBrush(QColor(fg)))
    item.setBackground(QBrush(QColor(bg)))
    if kalin:
        yazi = item.font()
        yazi.setBold(True)
        item.setFont(yazi)
    return item


def _merkez(metin):
    item = QTableWidgetItem(metin)
    item.setTextAlignment(Qt.AlignCenter)
    return item


class DurumHucreCizici(QStyledItemDelegate):
    """Durum hücrelerini yuvarlak köşeli renkli kutu olarak çizer.

    Tablonun genel stilindeki `::item` kuralı öğe arka plan rengini ezdiği için renk burada elle çizilir.
    """

    def paint(self, painter, option, index):
        arka = index.data(Qt.BackgroundRole)
        if arka is None:
            return super().paint(painter, option, index)
        renk = arka.color() if isinstance(arka, QBrush) else QColor(arka)
        on = index.data(Qt.ForegroundRole)
        yazi_rengi = on.color() if isinstance(on, QBrush) else QColor(on) if on is not None else QColor("#0F2552")
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        kutu = option.rect.adjusted(4, 4, -4, -4)
        painter.setPen(Qt.NoPen)
        painter.setBrush(renk)
        painter.drawRoundedRect(kutu, 9, 9)
        yazi = index.data(Qt.FontRole)
        painter.setFont(yazi if yazi is not None else option.font)
        painter.setPen(yazi_rengi)
        painter.drawText(kutu.adjusted(4, 0, -4, 0), int(Qt.AlignCenter | Qt.TextWordWrap), index.data(Qt.DisplayRole) or "")
        painter.restore()


class GunDetayDialog(QDialog):
    """Bir cihazın bir gündeki durumu: saat çizelgesi, nedenler, uyarılar ve (izne göre) işlem düğmeleri."""

    def __init__(self, cihaz, gun, bugun, simdi, yetkiler, sayfaya_git=None, rezervasyon_ac=None, parent=None):
        super().__init__(parent)
        self.cihaz, self.gun = cihaz, gun
        self.sayfaya_git, self.rezervasyon_ac = sayfaya_git, rezervasyon_ac
        self.sonraki_islem = None            # (fonksiyon, argümanlar): pencere kapandıktan sonra ekran çalıştırır
        donemler = mantik.donemleri_coz(cihaz)
        self.durum = mantik.gun_durumu(donemler, gun, simdi)
        self.cizelge = mantik.saat_cizelgesi(donemler, gun)
        self.oneri = mantik.rezervasyon_onerisi(self.durum, self.cizelge, gun, bugun, simdi)

        self.setWindowTitle(f"{cihaz.get('envanter_kodu', '')} — {mantik.uzun_tarih(gun)}")
        self.setMinimumWidth(580)
        self.setStyleSheet(FORM_STIL + "QPushButton#kaydet:disabled { background: #CBD5E1; color: #64748B; }")
        ana = QVBoxLayout(self)
        ana.setSpacing(12)

        baslik = QLabel(f"{cihaz.get('envanter_kodu', '')} · {cihaz.get('cihaz_adi', '')}")
        baslik.setStyleSheet("font-size: 17px; font-weight: 800; color: #0A1F5C;")
        ana.addWidget(baslik)
        alt = QHBoxLayout()
        tarih = QLabel(mantik.uzun_tarih(gun))
        tarih.setStyleSheet("font-size: 13px; color: #6B7FA8; font-weight: 600;")
        fg, bg = RENKLER[self.durum.kod]
        self.lbl_durum = QLabel(mantik.KOD_ADLARI[self.durum.kod])
        self.lbl_durum.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 12px; font-size: 12px; "
                                     "font-weight: 800; padding: 5px 14px;")
        alt.addWidget(tarih)
        alt.addStretch()
        alt.addWidget(self.lbl_durum)
        ana.addLayout(alt)

        # Saat çizelgesi (mesai saatleri)
        self.cizelge_etiketleri = []
        serit = QHBoxLayout()
        serit.setSpacing(3)
        for saat, kod in self.cizelge:
            hucre = QLabel(f"{saat:02d}")
            hucre.setAlignment(Qt.AlignCenter)
            hucre.setMinimumHeight(34)
            fg, bg = RENKLER[kod]
            hucre.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 6px; font-size: 12px; font-weight: 800;")
            hucre.setToolTip(f"{saat:02d}:00 – {saat + 1:02d}:00  {KISA_AD[kod]}")
            self.cizelge_etiketleri.append(hucre)
            serit.addWidget(hucre, 1)
        ana.addLayout(serit)
        not_ = QLabel("Saat çizelgesi: 08:00 – 18:00 mesai saatleri (her kutu bir saat).")
        not_.setStyleSheet("font-size: 11px; color: #8A9BC0; font-weight: 500;")
        ana.addWidget(not_)

        # Nedenler ve rezervasyon saatleri
        self.satir_metinleri = [mantik.donem_aciklamasi(e) for e in self.durum.engeller]
        self.satir_metinleri += [f"Rezervasyon: {b:%H:%M} – {'24:00' if s.hour == 0 and s.minute == 0 else f'{s:%H:%M}'}"
                                 for b, s in self.durum.rezervasyonlar]
        if self.durum.engelli:
            self.satir_metinleri.append(mantik.ENGEL_ACIKLAMA[self.durum.kod])
        uyarilar = mantik.uyari_satirlari(cihaz, bugun)
        for metin in self.satir_metinleri:
            etiket = QLabel("• " + metin)
            etiket.setWordWrap(True)
            etiket.setStyleSheet("font-size: 13px; color: #0F2552; font-weight: 600;")
            ana.addWidget(etiket)
        if not self.satir_metinleri:
            etiket = QLabel("Bu gün için engel ya da rezervasyon yok.")
            etiket.setStyleSheet("font-size: 13px; color: #166534; font-weight: 600;")
            ana.addWidget(etiket)
        self.uyari_etiketleri = []
        for metin, ciddiyet in uyarilar:
            renk, arka = ("#991B1B", "#FEE2E2") if ciddiyet == "kritik" else ("#854D0E", "#FEF3C7")
            etiket = QLabel("⚠ " + metin)
            etiket.setWordWrap(True)
            etiket.setStyleSheet(f"background: {arka}; color: {renk}; border-radius: 10px; font-size: 12px; "
                                 "font-weight: 700; padding: 8px 12px;")
            self.uyari_etiketleri.append(etiket)
            ana.addWidget(etiket)

        # Eylem düğmeleri: yalnızca izni olan kullanıcıya
        self.btn_rezervasyon = self.btn_ariza = self.btn_bakim = self.btn_kalibrasyon = None
        eylemler = QHBoxLayout()
        eylemler.setSpacing(8)
        gecis = QHBoxLayout()                                   # ilgili sayfalara geçiş düğmeleri ayrı satırda
        gecis.setSpacing(8)
        turler = {e.tur for e in self.durum.engeller}
        if yetkiler.get("rezervasyon") and rezervasyon_ac:
            self.btn_rezervasyon = QPushButton("Rezervasyon yap")
            self.btn_rezervasyon.setObjectName("kaydet")
            baslangic, bitis, neden = self.oneri
            if baslangic is None:
                self.btn_rezervasyon.setEnabled(False)
                self.btn_rezervasyon.setToolTip(neden)
            else:
                self.btn_rezervasyon.setToolTip(f"{baslangic} – {bitis} için rezervasyon formunu açar")
            self.btn_rezervasyon.clicked.connect(self._rezervasyon_yap)
            eylemler.addWidget(self.btn_rezervasyon)
        if sayfaya_git:
            if yetkiler.get("ariza") and mantik.ARIZA in turler:
                self.btn_ariza = self._gecis_dugmesi("Arıza kayıtlarına git", self._ariza_sayfasi, gecis)
            if yetkiler.get("bakim") and (mantik.BAKIM in turler or cihaz.get("bakim_uyari")):
                self.btn_bakim = self._gecis_dugmesi("Bakım kayıtlarına git", self._bakim_sayfasi, gecis)
            if yetkiler.get("kalibrasyon") and (mantik.KALIBRASYON in turler or cihaz.get("kalibrasyon_uyari")):
                self.btn_kalibrasyon = self._gecis_dugmesi("Kalibrasyona git", self._kalibrasyon_sayfasi, gecis)
        if gecis.count():
            etiket = QLabel("İlgili kayıtlar:")
            etiket.setStyleSheet("font-size: 12px; font-weight: 700; color: #6B7FA8;")
            gecis.insertWidget(0, etiket)
            gecis.addStretch()
            ana.addLayout(gecis)
        eylemler.addStretch()
        kapat = QPushButton("Kapat")
        kapat.setStyleSheet("QPushButton { background: white; color: #1E3A8A; border: 1px solid #C7D9FB; "
                            "border-radius: 10px; padding: 10px 18px; font-weight: 700; }")
        kapat.clicked.connect(self.reject)
        eylemler.addWidget(kapat)
        ana.addLayout(eylemler)

    # Not: Düğmeler anonim fonksiyonla değil bağlı metotla bağlanır. Anonim fonksiyon pencere ile düğme
    # arasında döngüsel referans kurar ve PySide6'da kapanışta çökmeye yol açabilir.
    def _ariza_sayfasi(self):
        self._git("Arıza Kayıtları")

    def _bakim_sayfasi(self):
        self._git("Bakım Kayıtları")

    def _kalibrasyon_sayfasi(self):
        self._git("Kalibrasyon")

    def _gecis_dugmesi(self, yazi, yontem, yerlesim):
        dugme = QPushButton(yazi)
        dugme.setStyleSheet("QPushButton { background: #EEF4FF; color: #1D4ED8; border: 1px solid #C7D9FB; "
                            "border-radius: 10px; padding: 10px 14px; font-weight: 700; } "
                            "QPushButton:hover { background: #DBEAFE; }")
        dugme.clicked.connect(yontem)
        yerlesim.addWidget(dugme)
        return dugme

    # İşlemler pencere içinde değil, pencere kapandıktan sonra yürütülür: böylece ikinci bir pencere
    # (rezervasyon formu) bu pencerenin olay döngüsü içinde açılmaz.
    def _git(self, sayfa):
        self.sonraki_islem = (self.sayfaya_git, (sayfa,))
        self.accept()

    def _rezervasyon_yap(self):
        baslangic, bitis, _ = self.oneri
        self.sonraki_islem = (self.rezervasyon_ac, (self.cihaz.get("cihaz_id"), self.gun, baslangic, bitis))
        self.accept()


class CihazUygunlukEkrani(QWidget):
    """Haftalık cihaz uygunluk takvimi."""

    def __init__(self, api_url, token, yetkiler=None, sayfaya_git=None, rezervasyon_ac=None):
        super().__init__()
        self.api_url = api_url
        self.token = token
        self.basliklar = {"Authorization": f"Bearer {token}"}
        self.yetkiler = {"rezervasyon": False, "ariza": False, "bakim": False, "kalibrasyon": False}
        self.yetkiler.update(yetkiler or {})
        self.sayfaya_git, self.rezervasyon_ac = sayfaya_git, rezervasyon_ac
        self.hafta_basi = mantik.hafta_basi(self._bugun())
        self.gunler = mantik.hafta_gunleri(self.hafta_basi)
        self.hafta_verisi = self.bugun_verisi = None
        self.musait_idler = None
        self._yukleniyor = False
        self.arayuzu_olustur()
        self._yukle()

    # ------------------------------------------------------------------ zaman (testte değiştirilebilir)
    def _bugun(self):
        return date.today()

    def _simdi(self):
        return datetime.now()

    # --------------------------------------------------------------------------------- arayüz
    def arayuzu_olustur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(16)

        self.arama = QLineEdit()
        self.arama.setPlaceholderText("🔍  Cihaz kodu veya adı ara...")
        self.arama.textChanged.connect(self._doldur)

        self.cip_musait = sayi_cipi("bugün 0 müsait", "#166534", "#DCFCE7")
        self.cip_dolu = sayi_cipi("0 dolu", "#1E3A8A", "#BFDBFE")
        self.cip_bakim = sayi_cipi("0 bakımda", "#854D0E", "#FEF3C7")
        self.cip_kalibrasyon = sayi_cipi("0 kalibrasyonda", "#6D28D9", "#EDE9FE")
        self.cip_ariza = sayi_cipi("0 arızalı", "#991B1B", "#FEE2E2")
        self.cip_kdisi = sayi_cipi("0 kullanım dışı", "#475569", "#E2E8F0")
        ana.addWidget(sayfa_basligi(
            "Cihaz Uygunluğu", "Cihazların haftalık durumu: rezervasyon, bakım, kalibrasyon ve arıza",
            self.arama, yenile_butonu_olustur(self.verileri_yukle),
            [self.cip_musait, self.cip_dolu, self.cip_bakim, self.cip_kalibrasyon, self.cip_ariza, self.cip_kdisi]))

        # --- hafta gezintisi ve filtre
        gezinti = QFrame()
        gezinti.setObjectName("kart")
        gezinti.setStyleSheet(ARAC_STILI)
        g = QHBoxLayout(gezinti)
        g.setContentsMargins(18, 12, 18, 12)
        g.setSpacing(8)
        self.btn_onceki = QPushButton("◀  Önceki hafta")
        self.btn_bugun = QPushButton("Bugün")
        self.btn_sonraki = QPushButton("Sonraki hafta  ▶")
        for dugme in (self.btn_onceki, self.btn_bugun, self.btn_sonraki):
            dugme.setObjectName("gezinti")
            dugme.setCursor(Qt.PointingHandCursor)
        self.btn_onceki.clicked.connect(self._onceki_hafta)
        self.btn_sonraki.clicked.connect(self._sonraki_hafta)
        self.btn_bugun.clicked.connect(self._bu_hafta)
        self.lbl_hafta = QLabel()
        self.lbl_hafta.setObjectName("hafta")
        self.cmb_filtre = QComboBox()
        for ad, kod in FILTRELER:
            self.cmb_filtre.addItem(ad, kod)
        self.cmb_filtre.currentIndexChanged.connect(self._doldur)
        self.dt_git = QDateEdit(QDate.currentDate())
        self.dt_git.setCalendarPopup(True)
        self.dt_git.setToolTip("Seçilen tarihin haftasına git")
        self.dt_git.dateChanged.connect(self._tarih_secildi)
        for parca in (self.btn_onceki, self.btn_bugun, self.btn_sonraki, self.lbl_hafta):
            g.addWidget(parca)
        g.addStretch()
        etiket = QLabel("Göster:")
        etiket.setObjectName("etiket")
        g.addWidget(etiket)
        g.addWidget(self.cmb_filtre)
        etiket = QLabel("Haftaya git:")
        etiket.setObjectName("etiket")
        g.addWidget(etiket)
        g.addWidget(self.dt_git)
        ana.addWidget(gezinti)

        # --- müsait cihaz bul
        bul = QFrame()
        bul.setObjectName("kart")
        bul.setStyleSheet(ARAC_STILI)
        b = QHBoxLayout(bul)
        b.setContentsMargins(18, 12, 18, 12)
        b.setSpacing(8)
        etiket = QLabel("Müsait cihaz bul:")
        etiket.setObjectName("etiket")
        varsayilan_tarih, varsayilan_bas, varsayilan_bit = varsayilan_rezervasyon_zamanlari()
        self.dt_bul = QDateEdit(varsayilan_tarih)
        self.dt_bul.setCalendarPopup(True)
        self.cmb_bul_bas, self.cmb_bul_bit = QComboBox(), QComboBox()
        for kutu, deger in ((self.cmb_bul_bas, varsayilan_bas), (self.cmb_bul_bit, varsayilan_bit)):
            kutu.addItems(SAAT_SECENEKLERI)
            kutu.setCurrentText(deger)
        self.btn_bul = QPushButton("Müsait olanları göster")
        self.btn_bul.setObjectName("birincil")
        self.btn_bul.setCursor(Qt.PointingHandCursor)
        self.btn_bul.clicked.connect(self._musait_bul)
        self.btn_temizle = QPushButton("Temizle")
        self.btn_temizle.setObjectName("gezinti")
        self.btn_temizle.setCursor(Qt.PointingHandCursor)
        self.btn_temizle.clicked.connect(self._bulmayi_temizle)
        self.lbl_sonuc = QLabel()
        self.lbl_sonuc.setStyleSheet("font-size: 13px; font-weight: 700; color: #166534;")
        for parca in (etiket, self.dt_bul, self.cmb_bul_bas, QLabel("–"), self.cmb_bul_bit, self.btn_bul, self.btn_temizle):
            b.addWidget(parca)
        b.addWidget(self.lbl_sonuc, 1)
        ana.addWidget(bul)

        # --- ızgara
        self.tablo = tablo_olustur(["CİHAZ", "ŞU AN"] + [""] * 7 + ["UYARILAR"])
        self.tablo.setSelectionMode(self.tablo.SelectionMode.NoSelection)    # seçim rengi durum renklerini ezmesin
        self.tablo.setMouseTracking(True)
        kb = self.tablo.horizontalHeader()
        kb.setSectionResizeMode(SUTUN_CIHAZ, QHeaderView.ResizeToContents)
        kb.setSectionResizeMode(SUTUN_SU_AN, QHeaderView.Fixed)
        self.tablo.setColumnWidth(SUTUN_SU_AN, 120)
        for sutun in range(ILK_GUN_SUTUNU, ILK_GUN_SUTUNU + 7):
            kb.setSectionResizeMode(sutun, QHeaderView.Stretch)
        kb.setSectionResizeMode(UYARI_SUTUNU, QHeaderView.Fixed)
        self.tablo.setColumnWidth(UYARI_SUTUNU, 250)
        self.cizici = DurumHucreCizici(self.tablo)
        for sutun in range(SUTUN_SU_AN, ILK_GUN_SUTUNU + 7):
            self.tablo.setItemDelegateForColumn(sutun, self.cizici)
        self.tablo.cellClicked.connect(self._hucre_tiklandi)
        self.bos_mesaj = bos_mesaj_olustur("Henüz cihaz kaydı yok.")

        kart = QFrame()
        kart.setObjectName("kart")
        kl = QVBoxLayout(kart)
        kl.setContentsMargins(8, 8, 8, 8)
        kl.addWidget(self.tablo)
        kl.addWidget(self.bos_mesaj)
        kl.addLayout(self._aciklama_serit())
        ana.addWidget(kart, 1)

    def _aciklama_serit(self):
        serit = QHBoxLayout()
        serit.setContentsMargins(8, 6, 8, 2)
        serit.setSpacing(8)
        for kod in (mantik.MUSAIT, mantik.KISMEN, mantik.DOLU, mantik.BAKIM, mantik.KALIBRASYON, mantik.ARIZA,
                    mantik.KULLANIM_DISI):
            fg, bg = RENKLER[kod]
            e = QLabel(mantik.KOD_ADLARI[kod])
            e.setStyleSheet(f"background: {bg}; color: {fg}; border-radius: 8px; font-size: 11px; font-weight: 800; "
                            "padding: 3px 10px;")
            serit.addWidget(e)
        ipucu = QLabel("Bir güne tıklayınca saat çizelgesi açılır.")
        ipucu.setStyleSheet("font-size: 11px; color: #8A9BC0;")
        serit.addStretch()
        serit.addWidget(ipucu)
        return serit

    # ------------------------------------------------------------------------------------ veri
    def _getir(self, baslangic, bitis):
        cevap = oturum_kontrollu_istek(
            "GET", f"{self.api_url}/api/cihaz-uygunluk", headers=self.basliklar, timeout=10,
            params={"baslangic": baslangic.isoformat(), "bitis": bitis.isoformat()})
        if oturum_hatasi_mi(cevap):
            return None
        cevap.raise_for_status()
        return cevap.json()

    def verileri_yukle(self, *_):
        """Sayfa yenileme düğmesi ve ana pencere (sayfaya geçince) bunu çağırır."""
        self._yukle()

    def _yukle(self, doldur=True):
        self.gunler = mantik.hafta_gunleri(self.hafta_basi)
        bugun = self._bugun()
        try:
            hafta = self._getir(self.hafta_basi, self.hafta_basi + timedelta(days=6))
            if hafta is None:
                return
            bugunku = hafta if self.hafta_basi <= bugun <= self.hafta_basi + timedelta(days=6) \
                else self._getir(bugun, bugun)
            if bugunku is None:
                return
        except Exception as hata:
            print("Cihaz uygunluk yükleme hatası:", hata)
            yanit = getattr(hata, "response", None)
            yetkisiz = yanit is not None and getattr(yanit, "status_code", None) == 403
            self.hafta_verisi = self.bugun_verisi = None
            self.bos_mesaj.setText("Bu bilgiyi görüntüleme yetkiniz yok." if yetkisiz
                                   else "Cihaz uygunluk bilgisi yüklenemedi. Sunucu bağlantısını kontrol edin.")
            self.bos_mesaj.show()
            self.tablo.hide()
            self.tablo.setRowCount(0)
            return
        self.hafta_verisi, self.bugun_verisi = hafta, bugunku
        if doldur:
            self._doldur()

    # ------------------------------------------------------------------------------- gezinti
    def _onceki_hafta(self, *_):
        self.haftaya_git(self.hafta_basi - timedelta(days=7))

    def _sonraki_hafta(self, *_):
        self.haftaya_git(self.hafta_basi + timedelta(days=7))

    def _bu_hafta(self, *_):
        self.haftaya_git(self._bugun())

    def haftaya_git(self, gun):
        self.hafta_basi = mantik.hafta_basi(gun)
        self.musait_idler = None                      # başka haftaya geçince 'müsait bul' sonucu geçersiz
        self.lbl_sonuc.setText("")
        self._yukle()

    def _tarih_secildi(self, tarih):
        if not self._yukleniyor:
            self.haftaya_git(tarih.toPython())

    # ------------------------------------------------------------------------------------ çizim
    def _doldur(self, *_):
        if self.hafta_verisi is None:
            return
        bugun = self._bugun()
        self._yukleniyor = True
        self.dt_git.setDate(QDate(self.hafta_basi.year, self.hafta_basi.month, self.hafta_basi.day))
        self._yukleniyor = False
        self.lbl_hafta.setText(mantik.hafta_etiketi(self.gunler))
        basliklar = ["CİHAZ", "ŞU AN"]
        for g in self.gunler:
            # Sütunlar dar olduğundan gün adı ve tarih ayrı satırlarda (yan yana yazınca kırpılıyordu).
            metin = f"{mantik.GUN_KISA[g.weekday()]}\n{g.day} {mantik.AYLAR[g.month - 1][:3]}"
            basliklar.append(metin + ("\nBUGÜN" if g == bugun else ""))
        self.tablo.setHorizontalHeaderLabels(basliklar + ["UYARILAR"])

        self._sayaclari_guncelle()
        tum = self.hafta_verisi["cihazlar"]
        simdi = self._simdi()
        gorunen = mantik.filtrele(tum, self.arama.text(), self.cmb_filtre.currentData(), self.gunler, bugun,
                                  self.musait_idler, simdi)
        bugun_cihazlari = {c["cihaz_id"]: c for c in (self.bugun_verisi or {}).get("cihazlar", [])}
        self.tablo.setRowCount(len(gorunen))
        for satir, cihaz in enumerate(gorunen):
            kimlik = cihaz["cihaz_id"]
            ad = QTableWidgetItem(f"{cihaz.get('envanter_kodu', '')}  ·  {cihaz.get('cihaz_adi', '')}")
            ad.setData(Qt.UserRole, kimlik)
            yazi = ad.font()
            yazi.setBold(True)
            ad.setFont(yazi)
            self.tablo.setItem(satir, SUTUN_CIHAZ, ad)

            su_an = mantik.su_anki_durum(mantik.donemleri_coz(bugun_cihazlari.get(kimlik, cihaz)), simdi)
            self.tablo.setItem(satir, SUTUN_SU_AN, _renkli(_merkez(KISA_AD[su_an]), su_an, kalin=True))

            donemler = mantik.donemleri_coz(cihaz)
            for sira, gun in enumerate(self.gunler):
                durum = mantik.gun_durumu(donemler, gun, simdi)
                metin = mantik.KOD_ADLARI[durum.kod]
                if durum.kod == mantik.KISMEN:
                    metin += f"\n{durum.dolu_dakika // 60} sa {durum.dolu_dakika % 60:02d} dk" if durum.dolu_dakika else "\nmesai dışı"
                item = _renkli(_merkez(metin), durum.kod, kalin=(gun == bugun))
                item.setToolTip(mantik.gun_ipucu(gun, durum))
                self.tablo.setItem(satir, ILK_GUN_SUTUNU + sira, item)

            uyarilar = mantik.uyari_satirlari(cihaz, bugun)
            uyari = QTableWidgetItem("\n".join("⚠ " + m for m, _ in uyarilar))
            if uyarilar:
                kritik = any(c == "kritik" for _, c in uyarilar)
                uyari.setForeground(QBrush(QColor("#991B1B" if kritik else "#854D0E")))
                uyari.setToolTip("\n".join(m for m, _ in uyarilar))
            self.tablo.setItem(satir, UYARI_SUTUNU, uyari)
            self.tablo.setRowHeight(satir, satir_yuksekligi([m for m, _ in uyarilar]))

        if not tum:
            self.bos_mesaj.setText("Henüz cihaz kaydı yok.")
        elif not gorunen:
            self.bos_mesaj.setText("Seçili filtrelere uyan cihaz bulunamadı.")
        self.bos_mesaj.setVisible(not gorunen)
        self.tablo.setVisible(bool(gorunen))

    def _sayaclari_guncelle(self):
        ozet = mantik.bugun_ozeti((self.bugun_verisi or self.hafta_verisi)["cihazlar"], self._bugun(), self._simdi())
        self.cip_musait.setText(f"bugün {ozet['musait']} müsait")
        self.cip_dolu.setText(f"{ozet['dolu']} dolu")
        self.cip_bakim.setText(f"{ozet['bakim']} bakımda")
        self.cip_kalibrasyon.setText(f"{ozet['kalibrasyon']} kalibrasyonda")
        self.cip_ariza.setText(f"{ozet['ariza']} arızalı")
        self.cip_kdisi.setText(f"{ozet['kullanim_disi']} kullanım dışı")

    # ----------------------------------------------------------------- müsait cihaz bul
    def _musait_bul(self, *_):
        tarih = self.dt_bul.date().toPython()
        baslangic = datetime.combine(tarih, time.fromisoformat(self.cmb_bul_bas.currentText()))
        bitis = datetime.combine(tarih, time.fromisoformat(self.cmb_bul_bit.currentText()))
        if bitis <= baslangic:
            self.lbl_sonuc.setStyleSheet("font-size: 13px; font-weight: 700; color: #991B1B;")
            self.lbl_sonuc.setText("Bitiş saati başlangıçtan sonra olmalıdır.")
            return
        if mantik.hafta_basi(tarih) != self.hafta_basi:
            self.hafta_basi = mantik.hafta_basi(tarih)
            self._yukle(doldur=False)
        if self.hafta_verisi is None:
            return
        self.musait_idler = mantik.musait_cihazlar(self.hafta_verisi["cihazlar"], baslangic, bitis)
        aralik = f"{mantik.tarih_yazi(tarih)}, {baslangic:%H:%M} – {bitis:%H:%M}"
        if self.musait_idler:
            self.lbl_sonuc.setStyleSheet("font-size: 13px; font-weight: 700; color: #166534;")
            self.lbl_sonuc.setText(f"{len(self.musait_idler)} cihaz müsait ({aralik})")
        else:
            self.lbl_sonuc.setStyleSheet("font-size: 13px; font-weight: 700; color: #991B1B;")
            self.lbl_sonuc.setText(f"Bu aralıkta müsait cihaz yok ({aralik})")
        self._doldur()

    def _bulmayi_temizle(self, *_):
        self.musait_idler = None
        self.lbl_sonuc.setText("")
        self._doldur()

    # ------------------------------------------------------------------------ gün detayı
    def _hucre_tiklandi(self, satir, sutun):
        ad = self.tablo.item(satir, SUTUN_CIHAZ)
        if ad is None or self.hafta_verisi is None:
            return
        kimlik = ad.data(Qt.UserRole)
        if sutun == SUTUN_SU_AN:
            cihaz = next((c for c in (self.bugun_verisi or {}).get("cihazlar", []) if c["cihaz_id"] == kimlik), None)
            gun = self._bugun()
        elif ILK_GUN_SUTUNU <= sutun < ILK_GUN_SUTUNU + 7:
            cihaz = next((c for c in self.hafta_verisi["cihazlar"] if c["cihaz_id"] == kimlik), None)
            gun = self.gunler[sutun - ILK_GUN_SUTUNU]
        else:
            return
        if cihaz is not None:
            self.gun_detayi_ac(cihaz, gun)

    def gun_detayi_ac(self, cihaz, gun):
        pencere = GunDetayDialog(cihaz, gun, self._bugun(), self._simdi(), self.yetkiler,
                                 self.sayfaya_git, self.rezervasyon_ac, self)
        pencere.exec()
        if pencere.sonraki_islem:
            fonksiyon, argumanlar = pencere.sonraki_islem
            fonksiyon(*argumanlar)
        return pencere
