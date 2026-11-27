"""Ortak form diyaloğu tabanı: alanlar kaydırma alanında, düğmeler altta SABİT.

Neden: uzun bir form (ör. rol seçilince açılan yetki kartı + öğrenci alanları) ya da küçük ekran / yüksek Windows ekran ölçeği pencereyi ekranın
dışına taşırır; "Kaydet" düğmesi görünmez olur. Bu taban sınıf pencereyi ekranın en çok %90'ı kadar yapar (üstte ve altta eşit boşluk kalır),
taşan alanları projenin ortak kaydırma çubuğuyla kaydırır ve düğme çubuğunu her zaman görünür tutar. İçerik sığıyorsa kaydırma çubuğu çıkmaz:
pencere eskisi gibi içeriği kadar açılır.

Kullanım (bir diyalogun `arayuzu_kur` yönteminde):
    class Formum(KaydirmaliDiyalog):
        ...
        layout, alt_yerlesim = self.kaydirmali_kur()        # eski `layout = QVBoxLayout(self)` yerine
        ... alanları `layout`a ekleyin (kenar boşluğu/aralık ayarları aynen çalışır) ...
        alt_yerlesim.addLayout(butonlar)                    # düğme satırı `layout` yerine buraya
`adjustSize()` çağıran eski kodlar da aynen çalışır (içerik değişince pencere gerekirse büyür).
"""
from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QFrame, QScrollArea, QVBoxLayout, QWidget

# Pencerenin ekranın kullanılabilir yüksekliğinden alabileceği en büyük oran ve başlık çubuğu/kenarlık için ayrılan pay (piksel).
EN_COK_EKRAN_ORANI = 0.90
CERCEVE_PAYI = 40
EN_AZ_YUKSEKLIK = 300

# Arka planlar saydamdır: kaydırma alanı, her diyalogun kendi zemin rengini (ör. #F8FAFC ya da beyaz) olduğu gibi gösterir. Stiller, diyalogun
# kendi stil sayfası sonradan değişse de bozulmasın diye diyalogun değil, kaydırma alanı ve alt çubuk bileşenlerinin üzerindedir.
KAYDIRMA_ALANI_STILI = "QScrollArea#form_kaydirma { background: transparent; border: none; } QWidget#form_icerik { background: transparent; }"
ALT_CUBUK_STILI = "QFrame#form_alt_cubuk { background: transparent; border: none; border-top: 1px solid #E2E8F0; }"


class _YerlesimDinleyici(QObject):
    """İçerik alanının yerleşimi değişince (alan gizlendi/gösterildi) pencereyi gerekiyorsa büyütür; küçültmez."""

    def __init__(self, diyalog):
        super().__init__(diyalog)
        self._diyalog = diyalog
        self._bekliyor = False

    def eventFilter(self, nesne, olay):
        if olay.type() == QEvent.LayoutRequest and not self._bekliyor:
            self._bekliyor = True
            QTimer.singleShot(0, self._uygula)
        return False

    def _uygula(self):
        self._bekliyor = False
        try:
            if self._diyalog.isVisible():
                self._diyalog.boyutu_ayarla(yalniz_buyut=True)
        except RuntimeError:                # Qt nesnesi silinmiş
            pass


class KaydirmaliDiyalog(QDialog):
    """Bkz. modül açıklaması. `kaydirmali_kur()` bir kez, `arayuzu_kur` içinde çağrılır."""

    def kaydirmali_kur(self, alt_kenar=(20, 12, 20, 16), tercih_boyut=None):
        """(içerik yerleşimi, alt çubuk yerleşimi) döndürür.

        tercih_boyut: (genişlik, yükseklik) — içeriği ne olursa olsun pencerenin tercih ettiği boyut (eski sabit boyutlu pencereler için);
        ekrana sığmazsa yükseklik yine ekrana göre kısılır.
        """
        self._tercih_boyut = tercih_boyut
        self._ilk_gosterim = True
        dis = QVBoxLayout(self)
        dis.setContentsMargins(0, 0, 0, 0)
        dis.setSpacing(0)
        self.kaydirma = QScrollArea()
        self.kaydirma.setObjectName("form_kaydirma")
        self.kaydirma.setWidgetResizable(True)
        self.kaydirma.setFrameShape(QFrame.NoFrame)
        self.kaydirma.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.kaydirma.setStyleSheet(KAYDIRMA_ALANI_STILI)
        self.kaydirma.viewport().setAutoFillBackground(False)
        self.icerik = QWidget()
        self.icerik.setObjectName("form_icerik")
        self.kaydirma.setWidget(self.icerik)
        dis.addWidget(self.kaydirma, 1)
        self.alt_cubuk = QFrame()
        self.alt_cubuk.setObjectName("form_alt_cubuk")
        self.alt_cubuk.setStyleSheet(ALT_CUBUK_STILI)
        alt = QVBoxLayout(self.alt_cubuk)
        alt.setContentsMargins(*alt_kenar)
        alt.setSpacing(8)
        dis.addWidget(self.alt_cubuk)
        self.icerik.installEventFilter(_YerlesimDinleyici(self))
        return QVBoxLayout(self.icerik), alt

    # ------------------------------------------------------------------ boyut
    def _ekran_alani(self):
        ekran = self.screen() or QGuiApplication.primaryScreen()
        return ekran.availableGeometry()

    def en_cok_yukseklik(self):
        return max(int(self._ekran_alani().height() * EN_COK_EKRAN_ORANI) - CERCEVE_PAYI, EN_AZ_YUKSEKLIK)

    def boyutu_ayarla(self, yalniz_buyut=False):
        """Pencereyi içeriğine göre boyutlar; ekranın yüksekliğini aşarsa sınırlar ve kaydırma çubuğu devreye girer."""
        if not hasattr(self, "icerik"):
            return
        ic = self.icerik.sizeHint()
        gerekli = ic.height() + self.alt_cubuk.sizeHint().height()
        genislik = max(ic.width(), self.minimumWidth())
        if self._tercih_boyut:
            genislik = max(genislik, self._tercih_boyut[0])
            gerekli = max(gerekli, self._tercih_boyut[1])
        sinir = self.en_cok_yukseklik()
        yukseklik = min(gerekli, sinir)
        if gerekli > sinir:
            genislik += self.kaydirma.verticalScrollBar().sizeHint().width()       # çubuk içeriği daraltmasın
        if yalniz_buyut:
            yukseklik = max(yukseklik, self.height())
            genislik = max(genislik, self.width())
        if (genislik, yukseklik) != (self.width(), self.height()):
            self.resize(genislik, yukseklik)

    def adjustSize(self):                   # eski kodlar `adjustSize()` çağırır; kaydırmalı düzende doğru boyut buradan hesaplanır
        self.boyutu_ayarla()

    def showEvent(self, olay):
        if getattr(self, "_ilk_gosterim", False):
            self._ilk_gosterim = False
            self.boyutu_ayarla()
        super().showEvent(olay)
