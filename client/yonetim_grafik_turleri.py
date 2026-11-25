"""Yönetim raporlarında ortak grafik türü seçimi ve grafik çizimi.

Bütün yönetim grafikleri aynı üç türle gösterilir: Sütun, Çizgi, Pasta. Seçim her grafiğin başlık satırının
sağındaki üç düğmeli seçiciyle yapılır; renkler, eksenler ve ipuçları da her grafikte aynıdır.

Renkler doğrulanmış bir kategorik paletten gelir (renk körlüğünde ayırt edilebilirlik denetlendi):
  - Dönem karşılaştırması: seçilen dönem mavi, önceki dönem turuncu (çizgide önceki dönem ayrıca kesikli çizilir).
  - Pasta dilimleri: paletin sırasıyla; 7'den fazla kategori "Diğer" diliminde toplanır.
Açık tonların beyaz zemin üzerindeki kontrastı düşük olduğundan pastada her dilimin adı, değeri ve payı
lejantta yazılıdır (renk tek başına bilgi taşımaz).
"""

import math

from PySide6.QtCore import Qt, QMargins, QPointF, QSize, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QGradient
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QGraphicsTextItem, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)
from PySide6.QtCharts import (
    QAbstractBarSeries, QAreaSeries, QBarCategoryAxis, QBarSeries, QBarSet, QCategoryAxis, QChart, QLineSeries,
    QPieSeries, QValueAxis,
)

GRAFIK_TURLERI = ("Sütun", "Çizgi", "Pasta")

# Doğrulanmış kategorik palet (sıra sabittir, döngüyle yeni renk üretilmez).
PALET = ("#1D4ED8", "#EB6834", "#1BAF7A", "#EDA100", "#E87BA4", "#008300", "#6250D6", "#E34948")
RENKLER = (PALET[0], PALET[1])          # seçilen dönem, önceki dönem
DIGER_RENGI = "#A3AEBD"
PASTA_EN_FAZLA_DILIM = 7

METIN_RENGI = "#1E293B"
IKINCIL_METIN = "#5B6B82"
IZGARA_RENGI = "#EDF1F7"
EKSEN_RENGI = "#D5DEEA"

# Eski çağrılar için: her rapor aynı üç türü kullanır.
RAPORA_GORE_TURLER = {}


def uygun_grafik_turleri(rapor=None):
    return GRAFIK_TURLERI


def _veriler(rapor, args):
    if rapor == "randevu":
        kayitlar = sorted(args[0], key=lambda x: x["tarih"])
        return (
            [str(x["tarih"]) for x in kayitlar],
            [("Randevu Sayısı", [float(x["sayi"]) for x in kayitlar])],
        )

    if rapor == "ogrenci":
        return (
            [str(x["faaliyet"]) for x in args[0]],
            [("Toplam Puan", [float(x["toplam_puan"] or 0) for x in args[0]])],
        )

    if rapor == "proje":
        return (
            [str(x.get("tur") or "Belirtilmemiş") for x in args[0]],
            [("Rezervasyon", [float(x.get("rezervasyon_sayisi") or 0) for x in args[0]])],
        )

    return (
        [str(x) for x in args[0]],
        [
            ("Seçilen Dönem", [float(x) for x in args[1]]),
            ("Önceki Dönem", [float(x) for x in args[2]]),
        ],
    )


def kisa_etiket(ad):
    """ISO tarihleri eksende daha okunabilir göster."""
    ad = str(ad)

    from datetime import date

    try:
        return date.fromisoformat(ad).strftime("%d.%m")
    except ValueError:
        return ad


def _kisalt(ad, en_fazla=18):
    ad = kisa_etiket(ad)
    return ad if len(ad) <= en_fazla else ad[: en_fazla - 1].rstrip() + "…"


def deger_metni(deger):
    """12 -> "12", 12.5 -> "12,5" (Türkçe ondalık)."""
    deger = float(deger)
    if deger.is_integer():
        return f"{int(deger):,}".replace(",", ".")
    return f"{deger:.1f}".replace(".", ",")


def sayisal_eksen(eksen, maksimum, tam_sayi=True):
    """Okunaklı adımlı değer ekseni: 0, 5, 10, 15 ... ya da 0, 250, 500 ... (adım 1, 2, 2,5 ya da 5'in katları)."""
    maks = max(float(maksimum or 0), 0.0) * 1.12          # sütun üstü sayılara yer kalsın
    if maks <= 0:
        maks = 4.0 if tam_sayi else 1.0

    ham_adim = maks / 4
    buyukluk = 10 ** math.floor(math.log10(ham_adim))
    adim = buyukluk
    for katsayi in (1, 2, 2.5, 5, 10):
        adim = katsayi * buyukluk
        if adim >= ham_adim:
            break
    if tam_sayi:
        adim = max(1, math.ceil(adim))

    ust = adim * math.ceil(maks / adim)
    eksen.setRange(0, ust)
    eksen.setTickCount(int(round(ust / adim)) + 1)
    eksen.setLabelFormat("%.0f" if float(adim).is_integer() else "%.1f")


def _yazi(boyut, kalin=False):
    yazi = QFont()
    yazi.setPointSizeF(boyut)
    yazi.setBold(kalin)
    return yazi


def _ekseni_sadelestir(eksen, izgara=True):
    eksen.setLabelsColor(QColor(IKINCIL_METIN))
    eksen.setLabelsFont(_yazi(8.5))
    eksen.setLinePenColor(QColor(EKSEN_RENGI))
    eksen.setGridLineVisible(izgara)
    eksen.setGridLineColor(QColor(IZGARA_RENGI))
    eksen.setMinorGridLineVisible(False)


def _lejant(chart, gorunur, hiza=Qt.AlignTop):
    lejant = chart.legend()
    lejant.setVisible(gorunur)
    if gorunur:
        lejant.setAlignment(hiza)
        lejant.setLabelColor(QColor(IKINCIL_METIN))
        lejant.setFont(_yazi(9))
        lejant.setMarkerShape(lejant.MarkerShape.MarkerShapeCircle)


def _tam_sayi_mi(seriler):
    return all(float(v).is_integer() for _, dizi in seriler for v in dizi)


def _pasta_dilimleri(kategoriler, seriler):
    """[(ad, değer, renk)]: iki dönemli veride seçilen dönem; tek kategoride iki dönem; fazlası "Diğer"de toplanır."""
    if len(seriler) > 1 and len(kategoriler) == 1:
        # Tek gösterge: pasta iki dönemin payını gösterir.
        ham = [(ad, max(0.0, dizi[0])) for ad, dizi in seriler]
        return [(ad, deger, RENKLER[i]) for i, (ad, deger) in enumerate(ham) if deger > 0]

    ham = [(ad, max(0.0, deger)) for ad, deger in zip(kategoriler, seriler[0][1]) if deger > 0]
    if list(kategoriler) != list(GUN_ADLARI):
        ham.sort(key=lambda oge: oge[1], reverse=True)    # haftanın günleri kendi sırasında kalır
    if len(ham) > PASTA_EN_FAZLA_DILIM:
        kalan = sum(deger for _, deger in ham[PASTA_EN_FAZLA_DILIM - 1:])
        ham = ham[: PASTA_EN_FAZLA_DILIM - 1] + [("Diğer", kalan)]
    return [
        (ad, deger, DIGER_RENGI if ad == "Diğer" else PALET[i % len(PALET)])
        for i, (ad, deger) in enumerate(ham)
    ]


def _pasta(chart, kategoriler, seriler):
    dilimler = _pasta_dilimleri(kategoriler, seriler)
    toplam = sum(deger for _, deger, _ in dilimler)

    pasta = QPieSeries()
    pasta.setHoleSize(0.56)
    pasta.setPieSize(0.86)
    for ad, deger, renk in dilimler:
        oran = 100 * deger / toplam if toplam else 0
        dilim = pasta.append(f"{_kisalt(ad, 26)}   {deger_metni(deger)}  (%{oran:.0f})", deger)
        dilim.setColor(QColor(renk))
        dilim.setBorderColor(QColor("white"))
        dilim.setBorderWidth(2)
        dilim.setProperty("tam_ad", kisa_etiket(ad))
        dilim.setProperty("oran", oran)

    def uzerinde(dilim, durum):
        dilim.setExploded(durum)
        dilim.setExplodeDistanceFactor(0.06)

    pasta.hovered.connect(uzerinde)
    chart.addSeries(pasta)
    chart._pasta_serisi = pasta
    _lejant(chart, True, Qt.AlignRight)
    _halka_ortasi_yazisi(chart, deger_metni(toplam), "Toplam")

    baslik = None
    if list(kategoriler) == list(GUN_ADLARI):
        baslik = "Haftanın günlerine göre dağılım"
    elif len(seriler) > 1 and len(kategoriler) > 1:
        baslik = "Dağılım: yalnızca seçilen dönem"
    if baslik:
        chart.setTitle(baslik)
        chart.setTitleFont(_yazi(9))
        chart.setTitleBrush(QColor(IKINCIL_METIN))


def _halka_ortasi_yazisi(chart, deger, alt_yazi):
    """Halkanın ortasına toplam değeri yazar; grafik boyutu değişince ortada kalır."""
    yazi = QGraphicsTextItem(chart)
    yazi.setHtml(
        f"<div align='center'><span style='color:{METIN_RENGI}; font-size:20px; font-weight:800'>{deger}</span>"
        f"<br><span style='color:{IKINCIL_METIN}; font-size:11px'>{alt_yazi}</span></div>"
    )
    yazi.setZValue(10)

    def yerlestir(alan):
        kutu = yazi.boundingRect()
        yazi.setPos(alan.center().x() - kutu.width() / 2, alan.center().y() - kutu.height() / 2)

    chart.plotAreaChanged.connect(yerlestir)
    chart._halka_yazisi = yazi


def _sutun(chart, kategoriler, seriler):
    seri = QBarSeries()
    if len(kategoriler) == 1:
        seri.setBarWidth(0.32)                    # tek gösterge: sütunlar ekranı kaplamasın
    else:
        seri.setBarWidth(0.55 if len(seriler) == 1 else 0.72)
    for i, (ad, sayilar) in enumerate(seriler):
        kume = QBarSet(ad)
        kume.setColor(QColor(RENKLER[i % len(RENKLER)]))
        kume.setBorderColor(QColor("white"))
        kume.setLabelColor(QColor(METIN_RENGI))
        kume.setLabelFont(_yazi(8.5, kalin=True))
        kume.append([float(v) for v in sayilar])
        seri.append(kume)

    # Az sütunda değerler sütunun üstünde yazılır (ipucu kutusu kullanılmaz).
    seri.setLabelsVisible(len(kategoriler) * len(seriler) <= 16)
    seri.setLabelsPosition(QAbstractBarSeries.LabelsOutsideEnd)
    seri.setLabelsFormat("@value")
    seri.setLabelsPrecision(6)

    chart.addSeries(seri)

    etiketler = [_kisalt(k) for k in kategoriler]
    kategori_ekseni = QBarCategoryAxis()
    kategori_ekseni.append(etiketler)
    _ekseni_sadelestir(kategori_ekseni, izgara=False)
    if _etiketler_egik_mi(etiketler):
        kategori_ekseni.setLabelsAngle(-35)

    deger_ekseni = QValueAxis()
    _ekseni_sadelestir(deger_ekseni)
    deger_ekseni.setLineVisible(False)
    sayisal_eksen(deger_ekseni, max([0] + [v for _, dizi in seriler for v in dizi]), _tam_sayi_mi(seriler))

    chart.addAxis(kategori_ekseni, Qt.AlignBottom)
    chart.addAxis(deger_ekseni, Qt.AlignLeft)
    seri.attachAxis(kategori_ekseni)
    seri.attachAxis(deger_ekseni)
    _lejant(chart, len(seriler) > 1)


def _etiketler_egik_mi(etiketler):
    """Etiketler yan yana sığmıyorsa eğik yazılır (yaklaşık 7 px/karakter, ~760 px çizim alanı)."""
    if not etiketler:
        return False
    yuva = 760 / len(etiketler)
    return max(len(e) for e in etiketler) * 7 > yuva


def _cizgi(chart, kategoriler, seriler):
    chart._alan_sinir_serileri = []        # QAreaSeries sınır serisinin sahipliğini almaz: grafik yaşadıkça korunur

    x = QCategoryAxis()
    x.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)
    adim = max(1, math.ceil(len(kategoriler) / 8))
    for i, ad in enumerate(kategoriler):
        if i % adim == 0 or i == len(kategoriler) - 1:
            x.append(_kisalt(ad, 14), float(i))
    x.setRange(-0.25 if len(kategoriler) > 1 else -1, float(len(kategoriler) - 1) + (0.25 if len(kategoriler) > 1 else 1))
    _ekseni_sadelestir(x, izgara=False)
    if len(kategoriler) <= 8 and _etiketler_egik_mi([_kisalt(k, 14) for k in kategoriler]):
        x.setLabelsAngle(-35)

    y = QValueAxis()
    _ekseni_sadelestir(y)
    y.setLineVisible(False)
    sayisal_eksen(y, max([0] + [v for _, dizi in seriler for v in dizi]), _tam_sayi_mi(seriler))

    chart.addAxis(x, Qt.AlignBottom)
    chart.addAxis(y, Qt.AlignLeft)

    for i, (ad, sayilar) in enumerate(seriler):
        renk = QColor(RENKLER[i % len(RENKLER)])

        if len(seriler) == 1:
            # Tek seride çizginin altı hafif renkli: eğilim bir bakışta okunur.
            ust = QLineSeries()
            alt = QLineSeries()
            for j, deger in enumerate(sayilar):
                ust.append(float(j), float(deger))
                alt.append(float(j), 0.0)
            chart._alan_sinir_serileri.extend([ust, alt])
            alan = QAreaSeries(ust, alt)
            egim = QLinearGradient(QPointF(0, 0), QPointF(0, 1))
            egim.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            ust_renk, alt_renk = QColor(renk), QColor(renk)
            ust_renk.setAlpha(70)
            alt_renk.setAlpha(5)
            egim.setColorAt(0, ust_renk)
            egim.setColorAt(1, alt_renk)
            alan.setBrush(egim)
            alan.setPen(QPen(Qt.NoPen))
            alan.setName(ad)
            chart.addSeries(alan)
            alan.attachAxis(x)
            alan.attachAxis(y)

        cizgi = QLineSeries()
        cizgi.setName(ad)
        kalem = QPen(renk, 2.5)
        kalem.setCapStyle(Qt.RoundCap)
        kalem.setJoinStyle(Qt.RoundJoin)
        if i == 1:
            kalem.setStyle(Qt.DashLine)            # önceki dönem: renkten bağımsız da ayırt edilsin
        cizgi.setPen(kalem)
        cizgi.setPointsVisible(True)
        cizgi.setMarkerSize(8 if len(sayilar) <= 15 else 6)
        if len(kategoriler) == 1:
            # Tek göstergede çizgi oluşmaz: noktaların değeri yanında yazılır.
            cizgi.setPointLabelsVisible(True)
            cizgi.setPointLabelsFormat("@yPoint")
            cizgi.setPointLabelsColor(QColor(METIN_RENGI))
            cizgi.setPointLabelsFont(_yazi(8.5, kalin=True))
        for j, deger in enumerate(sayilar):
            cizgi.append(float(j), float(deger))

        chart.addSeries(cizgi)
        cizgi.attachAxis(x)
        cizgi.attachAxis(y)

    _lejant(chart, len(seriler) > 1)
    # Tek seride alan + çizgi iki lejant girdisi üretir; gerek yok.
    if len(seriler) == 1:
        chart.legend().setVisible(False)


def grafik_olustur(kategoriler, seriler, tur):
    """Aynı sayısal verilerden seçilen QtCharts grafiğini üret (Sütun, Çizgi ya da Pasta)."""
    chart = QChart()
    chart.setBackgroundVisible(False)
    chart.setPlotAreaBackgroundVisible(False)
    chart.setMargins(QMargins(2, 6, 2, 2))
    chart.layout().setContentsMargins(0, 0, 0, 0)
    chart.setAnimationOptions(QChart.SeriesAnimations)
    chart.setAnimationDuration(450)

    if not kategoriler or not seriler:
        return chart

    if tur == "Pasta":
        _pasta(chart, kategoriler, seriler)
    elif tur == "Çizgi":
        _cizgi(chart, kategoriler, seriler)
    else:
        _sutun(chart, kategoriler, seriler)
    return chart


def grafik_yuksekligi(tur, kategori_sayisi, etiketler=None):
    """Grafiğin yüksekliği: türe ve kategori sayısına göre, gereksiz boşluk bırakmadan."""
    if tur == "Pasta":
        dilim = min(kategori_sayisi, PASTA_EN_FAZLA_DILIM)
        return max(250, min(330, 90 + dilim * 30))
    yukseklik = 290
    if etiketler is not None and _etiketler_egik_mi([_kisalt(e) for e in etiketler]):
        yukseklik += 45                                # eğik etiketlere yer
    return yukseklik


# ================================================================== üç düğmeli seçici
def _tur_ikonu(tur, renk):
    """Seçici düğmeleri için küçük çizim (emoji yerine: her işletim sisteminde aynı görünür)."""
    pix = QPixmap(32, 32)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(renk))
    if tur == "Sütun":
        for x, yuk in ((5, 14), (13, 22), (21, 9)):
            p.drawRoundedRect(x, 28 - yuk, 6, yuk, 1.5, 1.5)
    elif tur == "Çizgi":
        kalem = QPen(QColor(renk), 3.2)
        kalem.setCapStyle(Qt.RoundCap)
        kalem.setJoinStyle(Qt.RoundJoin)
        p.setPen(kalem)
        p.setBrush(Qt.NoBrush)
        p.drawPolyline([QPointF(4, 24), QPointF(12, 14), QPointF(19, 19), QPointF(28, 7)])
    else:
        p.drawPie(4, 4, 24, 24, 90 * 16, -250 * 16)
        soluk = QColor(renk)
        soluk.setAlpha(90)
        p.setBrush(soluk)
        p.drawPie(4, 4, 24, 24, 90 * 16, 110 * 16)
    p.end()
    return QIcon(pix)


SECICI_STILI = """
QFrame#grafikTuruSecici {
    background: #F1F5FB;
    border: 1px solid #DCE5F1;
    border-radius: 9px;
}
QFrame#grafikTuruSecici QPushButton {
    background: transparent;
    color: #5B6B82;
    border: none;
    border-radius: 7px;
    padding: 5px 11px;
    font-size: 12px;
    font-weight: 600;
}
QFrame#grafikTuruSecici QPushButton:hover { color: #1E3A8A; background: #E6EEF9; }
QFrame#grafikTuruSecici QPushButton:checked {
    background: #FFFFFF;
    color: #1D4ED8;
    border: 1px solid #C9D8EE;
}
"""


class GrafikTuruSecici(QFrame):
    """Sütun / Çizgi / Pasta için yan yana üç düğme. QComboBox'ın kullanılan arayüzüyle uyumludur
    (currentText, setCurrentText, currentTextChanged, count, itemText, addItems, clear)."""

    currentTextChanged = Signal(str)

    def __init__(self, ebeveyn=None, turler=GRAFIK_TURLERI, varsayilan=None):
        super().__init__(ebeveyn)
        self.setObjectName("grafikTuruSecici")
        self.setStyleSheet(SECICI_STILI)
        self._duzen = QHBoxLayout(self)
        self._duzen.setContentsMargins(3, 3, 3, 3)
        self._duzen.setSpacing(2)
        self._grup = QButtonGroup(self)
        self._grup.setExclusive(True)
        self._dugmeler = {}
        self.addItems(turler)
        if varsayilan:
            self.setCurrentText(varsayilan)
        self.setToolTip("Grafik türünü seçin")

    def addItems(self, turler):
        for tur in turler:
            dugme = QPushButton(tur, self)
            dugme.setCheckable(True)
            dugme.setCursor(Qt.PointingHandCursor)
            dugme.setIcon(_tur_ikonu(tur, "#5B6B82"))
            dugme.setIconSize(QSize(15, 15))
            dugme.setToolTip(f"{tur} grafiği")
            dugme.toggled.connect(self._dugme_degisti)      # lambda değil: self'i yakalayan lambda çıkışta çökme döngüsü yaratır
            self._grup.addButton(dugme)
            self._duzen.addWidget(dugme)
            self._dugmeler[tur] = dugme
        if self._dugmeler and self._grup.checkedButton() is None:
            gecmis = self.blockSignals(True)
            next(iter(self._dugmeler.values())).setChecked(True)
            self.blockSignals(gecmis)

    def _dugme_degisti(self, secili):
        dugme = self.sender()
        if dugme is not None:
            self._degisti(dugme.text(), secili)

    def _degisti(self, tur, secili):
        dugme = self._dugmeler.get(tur)
        if dugme is not None:
            dugme.setIcon(_tur_ikonu(tur, "#1D4ED8" if secili else "#5B6B82"))
        if secili:
            self.currentTextChanged.emit(tur)

    def clear(self):
        for dugme in list(self._dugmeler.values()):
            self._grup.removeButton(dugme)
            dugme.deleteLater()
        self._dugmeler = {}

    def count(self):
        return len(self._dugmeler)

    def itemText(self, sira):
        return list(self._dugmeler)[sira]

    def currentText(self):
        dugme = self._grup.checkedButton()
        return dugme.text() if dugme is not None else ""

    def setCurrentText(self, tur):
        dugme = self._dugmeler.get(tur)
        if dugme is not None and not dugme.isChecked():
            dugme.setChecked(True)


# ================================================================== grafik kartı
KART_STILI = """
QFrame#%(ad)s {
    background: #FFFFFF;
    border: none;
    border-radius: 16px;
}
QFrame#%(ad)s QLabel { background: transparent; border: none; }
"""


def grafik_karti_baslik_satiri(widget, secici):
    """Kartın başlık ve açıklamasını, sağında seçiciyle tek satıra alır. Kartın ilk iki öğesi başlık/açıklama etiketidir."""
    duzen = widget.layout()
    etiketler = []
    while duzen.count() and len(etiketler) < 2:
        oge = duzen.itemAt(0).widget()
        if not isinstance(oge, QLabel):
            break
        duzen.takeAt(0)
        etiketler.append(oge)

    satir = QWidget(widget)
    satir_duzeni = QHBoxLayout(satir)
    satir_duzeni.setContentsMargins(0, 0, 0, 4)
    satir_duzeni.setSpacing(12)
    sol = QVBoxLayout()
    sol.setSpacing(2)
    for etiket in etiketler:
        etiket.setWordWrap(True)
        sol.addWidget(etiket)
    satir_duzeni.addLayout(sol, 1)
    satir_duzeni.addWidget(secici, 0, Qt.AlignTop)
    duzen.insertWidget(0, satir)
    return satir


def grafik_kartini_bicimlendir(widget):
    """Bütün grafik kartları aynı kenarlık, boşluk ve başlık yazısıyla görünür."""
    ad = widget.objectName() or "yonetimGrafikKarti"
    widget.setObjectName(ad)
    widget.setStyleSheet(KART_STILI % {"ad": ad})
    widget.layout().setContentsMargins(20, 16, 20, 14)
    widget.layout().setSpacing(6)
    etiketler = [e for e in widget.findChildren(QLabel) if e.parent() is widget]
    if etiketler:
        etiketler[0].setStyleSheet("color: #0F2552; font-size: 15px; font-weight: 800;")
    if len(etiketler) > 1:
        etiketler[1].setStyleSheet("color: #6B7C96; font-size: 11.5px;")
    gorunum = getattr(widget, "gorunum", None)
    if gorunum is not None:
        gorunum.setStyleSheet("background: transparent; border: none;")
        gorunum.setBackgroundBrush(QColor("#FFFFFF"))
        gorunum.setFrameShape(QFrame.NoFrame)
        gorunum.setRenderHint(QPainter.Antialiasing)


def bos_etiketi_olustur(widget):
    bos = QLabel("Seçilen dönemde görüntülenecek kayıt bulunmuyor.", widget)
    bos.setAlignment(Qt.AlignCenter)
    bos.setMinimumHeight(110)
    bos.setStyleSheet(
        "color: #7A8BA3; font-size: 12.5px; background: #F8FAFD; border: 1px dashed #DCE5F1; border-radius: 10px;"
    )
    bos.hide()
    return bos


GUN_ADLARI = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")


def haftanin_gunlerine_gore(tarihler, seriler):
    """ISO tarihli günlük sayıları haftanın günlerine toplar (Pazartesi ... Pazar)."""
    from datetime import date

    toplamlar = [0.0] * 7
    for tarih, deger in zip(tarihler, seriler[0][1]):
        try:
            toplamlar[date.fromisoformat(str(tarih)).weekday()] += float(deger)
        except ValueError:
            continue
    return list(GUN_ADLARI), [(seriler[0][0], toplamlar)]


def grafik_secimi_ekle(widget, rapor, varsayilan, turler=GRAFIK_TURLERI):
    """Var olan grafik kartına tür seçici ekler ve çizimi ortak grafik_olustur'a bağlar.

    `turler`: kartta sunulacak türler. Kategorileri karşılaştıran grafikte Çizgi (süreklilik ima eder) ve Pasta (iki dönemi
    karşılaştırmaz) anlamsızdır; tek türe indirilince seçici gizlenir."""
    grafik_kartini_bicimlendir(widget)
    turler = tuple(t for t in turler if t in GRAFIK_TURLERI) or GRAFIK_TURLERI
    secici = GrafikTuruSecici(widget, turler=turler, varsayilan=varsayilan if varsayilan in turler else turler[0])
    grafik_karti_baslik_satiri(widget, secici)
    if len(turler) == 1:
        secici.hide()
    widget.grafik_turu = secici

    eski_bos = getattr(widget, "bos", None)
    if eski_bos is not None:
        widget.layout().removeWidget(eski_bos)
        eski_bos.deleteLater()
    widget.bos = bos_etiketi_olustur(widget)
    widget.layout().insertWidget(1, widget.bos)

    son_veri = {"args": None}

    def guncelle(*args):
        son_veri["args"] = args
        tur = secici.currentText()
        kategoriler, seriler = _veriler(rapor, args)

        # Günlük randevu: Çizgi bütün günleri, Sütun yalnızca randevu olan günleri, Pasta haftanın günlerine
        # göre dağılımı gösterir (tarihleri dilim yapmak okunmaz).
        if rapor == "randevu" and tur == "Pasta":
            kategoriler, seriler = haftanin_gunlerine_gore(kategoriler, seriler)
        elif rapor == "randevu" and tur != "Çizgi":
            kayitli = [i for i, deger in enumerate(seriler[0][1]) if deger > 0]
            kategoriler = [kategoriler[i] for i in kayitli]
            seriler = [(ad, [degerler[i] for i in kayitli]) for ad, degerler in seriler]

        pozitif = sum(deger > 0 for _, dizi in seriler for deger in dizi)
        veri_var = bool(kategoriler) and pozitif > 0

        if not kategoriler:
            widget.bos.setText("Seçilen dönemde görüntülenecek kayıt bulunmuyor.")
        elif not veri_var:
            widget.bos.setText("Seçilen dönemde tüm değerler sıfır.")
        widget.bos.setVisible(not veri_var)
        widget.gorunum.setVisible(veri_var)
        if not veri_var:
            return

        widget.gorunum.setFixedHeight(grafik_yuksekligi(tur, len(kategoriler), kategoriler))
        widget.gorunum.setChart(grafik_olustur(kategoriler, seriler, tur))

    widget.guncelle = guncelle

    def secim_degisti(_):
        if son_veri["args"] is not None:
            guncelle(*son_veri["args"])

    secici.currentTextChanged.connect(secim_degisti)
    return secici
