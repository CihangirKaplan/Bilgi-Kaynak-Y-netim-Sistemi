"""Bakım ve kalibrasyon formlarının ortak 'sonraki tarih' ve 'hatırlatma' bölümü.

Kullanıcıya tek soru sorulur: "Sonraki bakım ne zaman?"
  [ 3 ay ] [ 6 ay ] [ 1 yıl ] [ Tarih seç ]   -> seçilen düğmenin sonucu hemen yazı olarak görünür
  Tarih kutusu hep görünür; ay düğmelerinde kilitli (hesaplanan tarihi gösterir), "Tarih seç"te açılır.
  Hiçbir şey gizlenmediği için düğmeye basınca pencere düzeni kaymaz.
Altında "Hatırlatma" listesi (tarihe kaç gün kala bildirim düşsün) ve tek cümlelik özet bulunur.
"""
import datetime

from PySide6.QtCore import QObject
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

# (düğme yazısı, bitişten sonra kaç ay). None -> tarih kullanıcı tarafından seçilir.
TEKRAR_SECENEKLERI = (
    ("3 ay", 3),
    ("6 ay", 6),
    ("1 yıl", 12),
    ("Tarih seç", None),
)
# (görünen ad, gün sayısı)
UYARI_SECENEKLERI = (
    ("Tarihi geldiği gün", 0),
    ("7 gün önce", 7),
    ("15 gün önce", 15),
    ("30 gün önce", 30),
    ("60 gün önce", 60),
    ("90 gün önce", 90),
)
VARSAYILAN_UYARI_GUN = 30

DUGME_STILI = (
    "QPushButton { background: white; color: #1E3A8A; border: 1px solid #C7D9FB; border-radius: 10px; "
    "padding: 6px 6px; min-height: 22px; font-size: 12px; font-weight: 600; } "
    "QPushButton:hover { background: #EEF4FF; } "
    "QPushButton:checked { background: #2563EB; color: white; border: 1px solid #2563EB; }"
)
SONUC_STILI = "color: #0F2552; font-size: 13px; font-weight: 700; padding: 2px 2px;"
OZET_STILI = ("background: #EEF4FF; color: #1E3A8A; border-radius: 10px; padding: 10px 12px; "
              "font-size: 12px; font-weight: 600;")


class TekrarUyariAlanlari(QObject):
    """Düğmeler + tarih + hatırlatma + özet. Tarih alanı (sonraki_alani) bu sınıfın yerleşimine taşınır."""

    def __init__(self, bitis_alani, sonraki_alani, olay_adi="Sonraki bakım",
                 uyari_suresi=VARSAYILAN_UYARI_GUN, varsayilan_ay=None, ebeveyn=None):
        super().__init__(ebeveyn)
        self.bitis = bitis_alani
        self.sonraki = sonraki_alani
        self.olay_adi = olay_adi

        # --- düğmeler
        self.grup = QButtonGroup(self)
        self.grup.setExclusive(True)
        self.butonlar = {}                                     # ay (veya None) -> düğme
        for ad, ay in TEKRAR_SECENEKLERI:
            dugme = QPushButton(ad)
            dugme.setCheckable(True)
            dugme.setAutoDefault(False)
            dugme.setMinimumHeight(36)
            dugme.setStyleSheet(DUGME_STILI)
            self.grup.addButton(dugme)
            self.butonlar[ay] = dugme
            dugme.clicked.connect(self._secim_degisti)

        self.lbl_sonuc = QLabel()
        self.lbl_sonuc.setStyleSheet(SONUC_STILI)

        # --- hatırlatma
        self.cmb_uyari = QComboBox()
        for ad, gun in UYARI_SECENEKLERI:
            self.cmb_uyari.addItem(ad, gun)
        uyari_suresi = int(uyari_suresi)
        if self.cmb_uyari.findData(uyari_suresi) < 0:           # kayıtlı özel değer listede yoksa ekle
            self.cmb_uyari.addItem(f"{uyari_suresi} gün önce", uyari_suresi)
        self.cmb_uyari.setCurrentIndex(self.cmb_uyari.findData(uyari_suresi))
        self.cmb_uyari.setToolTip("Tarihe bu kadar gün kala dashboard'da ve zilde uyarı gösterilir.")

        self.lbl_ozet = QLabel()
        self.lbl_ozet.setWordWrap(True)
        self.lbl_ozet.setStyleSheet(OZET_STILI)

        # Başlangıç: varsayılan ay varsa o düğme, yoksa kayıtlı tarih ("Tarih seç") gösterilir.
        self.sec(varsayilan_ay if varsayilan_ay in self.butonlar else None)

        self.bitis.dateChanged.connect(self._bitis_degisti)
        self.sonraki.dateChanged.connect(self.ozeti_guncelle)
        self.cmb_uyari.currentIndexChanged.connect(self.ozeti_guncelle)

    # ------------------------------------------------------------------- yerleşim
    def satirlari_ekle(self, form_layout, etiket="Sonraki bakım:"):
        """Forma 'Sonraki ... ne zaman?' bölümünü, 'Hatırlatma' satırını ve özeti ekler.
        Tarih alanı bu çağrıyla yerleşir; forma ayrıca addRow edilmemelidir."""
        kutu = QWidget()
        dikey = QVBoxLayout(kutu)
        dikey.setContentsMargins(0, 0, 0, 0)
        dikey.setSpacing(8)
        yatay = QHBoxLayout()
        yatay.setSpacing(6)
        for dugme in self.butonlar.values():
            yatay.addWidget(dugme, 1)
        dikey.addLayout(yatay)
        dikey.addWidget(self.sonraki)
        dikey.addWidget(self.lbl_sonuc)
        form_layout.addRow(etiket, kutu)
        form_layout.addRow("Hatırlatma:", self.cmb_uyari)
        form_layout.addRow("", self.lbl_ozet)

    def uyari_suresi(self):
        return int(self.cmb_uyari.currentData())

    # ------------------------------------------------------------------ davranış
    def secili_ay(self):
        """Seçili düğmenin ay sayısı; 'Tarih seç' için None."""
        for ay, dugme in self.butonlar.items():
            if dugme.isChecked():
                return ay
        return None

    def sec(self, ay):
        """Düğmeyi seçer (ay=None -> 'Tarih seç'); ay seçiliyse tarihi bitişten hesaplar."""
        self.butonlar[ay].setChecked(True)
        self._secim_degisti()

    def _secim_degisti(self, *_):
        ay = self.secili_ay()
        self.sonraki.setEnabled(ay is None)                    # kutu hep görünür; yalnızca 'Tarih seç'te açık
        if ay:
            self.sonraki.setDate(self.bitis.date().addMonths(ay))
        self.ozeti_guncelle()

    def _bitis_degisti(self, _tarih):
        if self.secili_ay():
            self._secim_degisti()

    def ozeti_guncelle(self, *_):
        sonraki = self.sonraki.date().toPython()
        ay = self.secili_ay()
        if ay:
            self.lbl_sonuc.setText(f"→ {sonraki:%d.%m.%Y}  (bitişten {self._ay_yazisi(ay)} sonra)")
        else:
            self.lbl_sonuc.setText("↑ Tarihi yukarıdaki kutudan seçin")
        uyari = self.uyari_suresi()
        bugun = datetime.date.today()
        baslangic = sonraki - datetime.timedelta(days=uyari)
        if sonraki < bugun:
            metin = f"{self.olay_adi} tarihi ({sonraki:%d.%m.%Y}) geçmişte."
        elif uyari == 0:
            metin = f"Yalnızca {sonraki:%d.%m.%Y} günü bildirim düşer."
        elif baslangic <= bugun:
            metin = (f"{sonraki:%d.%m.%Y} tarihine {uyari} gün kaldığı için "
                     "bildirim şimdiden görünür.")
        else:
            metin = f"{baslangic:%d.%m.%Y} tarihinden itibaren bildirim düşer ({uyari} gün kala)."
        self.lbl_ozet.setText(metin)

    @staticmethod
    def _ay_yazisi(ay):
        return "1 yıl" if ay == 12 else f"{ay} ay"
