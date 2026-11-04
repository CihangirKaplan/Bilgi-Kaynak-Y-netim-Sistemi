"""Bakım ve kalibrasyon formlarının ortak 'tekrar aralığı' ve 'uyarı süresi' alanları.

Tekrar aralığı seçilince "sonraki tarih" kendiliğinden hesaplanır (bitiş tarihi + aralık);
tarih elle değiştirilirse aralık "Elle gireceğim"e döner ve bir daha ezilmez. Uyarı süresi,
sonraki tarihe kaç gün kala dashboard'da ve bildirim zilinde uyarı verileceğini belirler.
"""
import datetime

from PySide6.QtCore import QObject, QDate
from PySide6.QtWidgets import QComboBox, QLabel, QSpinBox

# (görünen ad, ay sayısı). None -> tarih elle girilir.
TEKRAR_SECENEKLERI = (
    ("Elle gireceğim", None),
    ("1 ay", 1),
    ("3 ay", 3),
    ("6 ay", 6),
    ("1 yıl", 12),
    ("2 yıl", 24),
)
VARSAYILAN_UYARI_GUN = 30

OZET_STILI = ("background: #EEF4FF; color: #1E3A8A; border-radius: 10px; padding: 10px 12px; "
              "font-size: 12px; font-weight: 600;")
SPIN_STILI = ("QSpinBox { background: white; color: #0F2552; border: 1px solid #C7D9FB; "
              "border-radius: 10px; padding: 9px 12px; font-size: 13px; } "
              "QSpinBox:focus { border: 2px solid #3B82F6; }")


class TekrarUyariAlanlari(QObject):
    """İki alan (tekrar aralığı, uyarı süresi) ve canlı özet metni üretir; tarih alanlarına bağlanır."""

    def __init__(self, bitis_alani, sonraki_alani, olay_adi="Sonraki bakım",
                 uyari_suresi=VARSAYILAN_UYARI_GUN, varsayilan_ay=None, ebeveyn=None):
        super().__init__(ebeveyn)
        self.bitis = bitis_alani
        self.sonraki = sonraki_alani
        self.olay_adi = olay_adi
        self._ayarlaniyor = False

        self.cmb_tekrar = QComboBox()
        for ad, _ in TEKRAR_SECENEKLERI:
            self.cmb_tekrar.addItem(ad, _)
        self.spin_uyari = QSpinBox()
        self.spin_uyari.setRange(0, 365)
        self.spin_uyari.setSuffix(" gün önce")
        self.spin_uyari.setButtonSymbols(QSpinBox.NoButtons)
        self.spin_uyari.setValue(int(uyari_suresi))
        self.spin_uyari.setStyleSheet(SPIN_STILI)
        self.spin_uyari.setToolTip("Sonraki tarihe kaç gün kala dashboard'da ve zilde uyarı gösterilir.")
        self.lbl_ozet = QLabel()
        self.lbl_ozet.setWordWrap(True)
        self.lbl_ozet.setStyleSheet(OZET_STILI)

        # Başlangıç durumu (varsayılan aralık varsa tarih ona göre hesaplanır)
        indeks = self._indeks_bul(varsayilan_ay)
        self.cmb_tekrar.setCurrentIndex(indeks)
        if indeks:
            self.hesapla()

        self.cmb_tekrar.activated.connect(self._tekrar_secildi)
        self.bitis.dateChanged.connect(self._bitis_degisti)
        self.sonraki.userDateChanged.connect(self._sonraki_elle_degistirildi)
        self.spin_uyari.valueChanged.connect(self.ozeti_guncelle)
        self.sonraki.dateChanged.connect(self.ozeti_guncelle)
        self.ozeti_guncelle()

    # ------------------------------------------------------------------- yerleşim
    def satirlari_ekle(self, form_layout):
        """QFormLayout'a 'Tekrar aralığı', 'Uyarı süresi' satırlarını ve özet kutusunu ekler."""
        form_layout.addRow("Tekrar aralığı:", self.cmb_tekrar)
        form_layout.addRow("Uyarı süresi:", self.spin_uyari)
        form_layout.addRow("", self.lbl_ozet)

    def uyari_suresi(self):
        return self.spin_uyari.value()

    # ------------------------------------------------------------------ davranış
    @staticmethod
    def _indeks_bul(ay):
        for i, (_, deger) in enumerate(TEKRAR_SECENEKLERI):
            if deger == ay:
                return i
        return 0

    def hesapla(self):
        """Seçili aralığa göre sonraki tarihi bitiş tarihinden hesaplar (elle seçimde dokunmaz)."""
        ay = self.cmb_tekrar.currentData()
        if not ay:
            return
        self._ayarlaniyor = True
        try:
            self.sonraki.setDate(self.bitis.date().addMonths(ay))
        finally:
            self._ayarlaniyor = False
        self.ozeti_guncelle()

    def _tekrar_secildi(self, _indeks):
        self.hesapla()

    def _bitis_degisti(self, _tarih):
        self.hesapla()

    def _sonraki_elle_degistirildi(self, _tarih):
        if not self._ayarlaniyor:
            self.cmb_tekrar.setCurrentIndex(0)                 # "Elle gireceğim"
        self.ozeti_guncelle()

    def ozeti_guncelle(self, *_):
        sonraki = self.sonraki.date().toPython()
        uyari = self.spin_uyari.value()
        bugun = datetime.date.today()
        uyari_baslangic = sonraki - datetime.timedelta(days=uyari)
        metin = f"{self.olay_adi}: {sonraki:%d.%m.%Y}. "
        if sonraki < bugun:
            metin += "Bu tarih geçmişte."
        elif uyari == 0:
            metin += "Yalnızca tarihi geldiği gün uyarı verilir."
        elif uyari_baslangic <= bugun:
            metin += f"{uyari} gün kala uyarılır; uyarı süresine girildi, bildirim şimdiden görünür."
        else:
            metin += f"{uyari} gün kala ({uyari_baslangic:%d.%m.%Y} itibarıyla) bildirim düşer."
        self.lbl_ozet.setText(metin)
