"""Yönetim raporlarında ortak grafik türü seçimi."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QComboBox, QLabel
from PySide6.QtCharts import (
    QChart, QLineSeries, QAreaSeries, QBarSeries,
    QHorizontalBarSeries, QBarSet, QBarCategoryAxis,
    QCategoryAxis, QValueAxis, QPieSeries,
)

GRAFIK_TURLERI = (
    "Çizgi", "Sütun", "Alan", "Yatay Çubuk", "Pasta"
)
RENKLER = ("#6352B5", "#2596BE")


RAPORA_GORE_TURLER = {
    "randevu": ("Çizgi", "Sütun", "Alan"),
    "karsilastirma": ("Sütun", "Yatay Çubuk"),
    "cihaz": ("Sütun", "Yatay Çubuk"),
    "ogrenci": ("Sütun", "Yatay Çubuk", "Pasta"),
    "proje": ("Sütun", "Yatay Çubuk", "Pasta"),

    "Oda Kullanımı": ("Sütun", "Yatay Çubuk"),
    "Cihaz Kullanımı": ("Sütun", "Yatay Çubuk"),
    "Yetkiler": ("Sütun", "Yatay Çubuk", "Pasta"),
    "Öğrenci Mevcudu": ("Sütun", "Yatay Çubuk", "Pasta"),
    "Faaliyet Onayları": ("Sütun", "Yatay Çubuk", "Pasta"),
    "Bakım Gecikmeleri": ("Sütun", "Yatay Çubuk", "Pasta"),
}


def uygun_grafik_turleri(rapor):
    return RAPORA_GORE_TURLER.get(rapor, GRAFIK_TURLERI)


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
            [("Toplam Puan", [
                float(x["toplam_puan"] or 0) for x in args[0]
            ])],
        )

    if rapor == "proje":
        return (
            [str(x.get("tur") or "Belirtilmemiş") for x in args[0]],
            [("Rezervasyon", [
                float(x.get("rezervasyon_sayisi") or 0)
                for x in args[0]
            ])],
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
        tarih = date.fromisoformat(ad)
        return tarih.strftime("%d.%m")
    except ValueError:
        return ad


def sayisal_eksen(eksen, maksimum, tam_sayi=True):
    """Adetler için tam sayı, süreler için ondalıklı eksen."""
    import math

    if tam_sayi:
        ust = max(4, math.ceil(maksimum * 1.15))

        if ust <= 8:
            eksen.setRange(0, ust)
            eksen.setTickCount(ust + 1)
        else:
            ust = math.ceil(ust / 4) * 4
            eksen.setRange(0, ust)
            eksen.setTickCount(5)

        eksen.setLabelFormat("%.0f")
    else:
        ust = max(0.5, math.ceil(maksimum * 1.2 * 2) / 2)
        eksen.setRange(0, ust)
        eksen.setTickCount(5)
        eksen.setLabelFormat("%.1f")


def grafik_olustur(kategoriler, seriler, tur):
    """Aynı sayısal verilerden seçilen QtCharts grafiğini üret."""
    chart = QChart()
    chart.setBackgroundBrush(QColor("white"))
    chart.setPlotAreaBackgroundVisible(False)

    if not kategoriler:
        return chart

    if tur == "Pasta":
        pie = QPieSeries()
        # İki dönemli raporlarda pastaya yalnızca seçilen dönem girer.
        toplam = sum(max(0, v) for v in seriler[0][1])

        for ad, deger in zip(kategoriler, seriler[0][1]):
            if deger > 0:
                oran = 100 * deger / toplam if toplam else 0
                etiket = (
                    f"{kisa_etiket(ad)}: {deger:g} "
                    f"(%{oran:.1f})"
                )
                pie.append(etiket, deger)

        chart.addSeries(pie)
        if len(seriler) > 1:
            chart.setTitle("Dağılım: yalnızca seçilen dönem")
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignRight)
        return chart

    if tur in ("Sütun", "Yatay Çubuk"):
        seri = (
            QBarSeries()
            if tur == "Sütun"
            else QHorizontalBarSeries()
        )

        for i, (ad, sayilar) in enumerate(seriler):
            bar = QBarSet(ad)
            bar.setColor(QColor(RENKLER[i % len(RENKLER)]))
            bar.append(sayilar)
            seri.append(bar)

        chart.addSeries(seri)

        # Çubukların sayısal değerlerini görünür yap.
        seri.setLabelsVisible(True)
        seri.setLabelsFormat("@value")
        seri.setLabelsPrecision(6)

        kategori_ekseni = QBarCategoryAxis()
        etiketler = [kisa_etiket(k) for k in kategoriler]

        # Kategori sayisi fazla olsa bile isimleri silme.
        # Ozellikle yatay cubuklarda tum kategoriler korunur.
        if tur == "Sütun":
            uzun_isim = any(len(ad) > 13 for ad in etiketler)
            if len(etiketler) > 6 or uzun_isim:
                kategori_ekseni.setLabelsAngle(-45)

        kategori_ekseni.append(etiketler)

        deger_ekseni = QValueAxis()
        maksimum = max(
            [0] + [v for _, dizi in seriler for v in dizi]
        )
        tam_sayi = all(
            float(v).is_integer()
            for _, dizi in seriler for v in dizi
        )
        sayisal_eksen(deger_ekseni, maksimum, tam_sayi)

        if tur == "Sütun":
            yonler = (
                (kategori_ekseni, Qt.AlignBottom),
                (deger_ekseni, Qt.AlignLeft),
            )
        else:
            yonler = (
                (kategori_ekseni, Qt.AlignLeft),
                (deger_ekseni, Qt.AlignBottom),
            )

        for eksen, yon in yonler:
            chart.addAxis(eksen, yon)
            seri.attachAxis(eksen)

        if tur == "Yatay Çubuk":
            kategori_ekseni.setLabelsAngle(0)

    else:
        # QAreaSeries ust sinir cizgisinin sahipligini almaz.
        # Sinir cizgilerini grafik yasadigi surece koru.
        chart._alan_sinir_serileri = []
        x = QCategoryAxis()
        x.setLabelsPosition(QCategoryAxis.AxisLabelsPositionOnValue)

        import math

        adim = max(1, math.ceil(len(kategoriler) / 6))

        for i, ad in enumerate(kategoriler):
            if (
                i % adim == 0
                or i == len(kategoriler) - 1
            ):
                x.append(kisa_etiket(ad), float(i))

        x.setRange(0, float(max(1, len(kategoriler) - 1)))

        y = QValueAxis()
        maksimum = max(
            [0] + [v for _, dizi in seriler for v in dizi]
        )
        tam_sayi = all(
            float(v).is_integer()
            for _, dizi in seriler for v in dizi
        )
        sayisal_eksen(y, maksimum, tam_sayi)

        chart.addAxis(x, Qt.AlignBottom)
        chart.addAxis(y, Qt.AlignLeft)

        for i, (ad, sayilar) in enumerate(seriler):
            ust = QLineSeries()
            ust.setName(ad)

            renk = QColor(RENKLER[i % len(RENKLER)])
            ust.setPen(QPen(renk, 3))

            for j, deger in enumerate(sayilar):
                ust.append(float(j), deger)

            if tur == "Alan":
                chart._alan_sinir_serileri.append(ust)
                seri = QAreaSeries(ust)
                dolgu = QColor(renk)
                dolgu.setAlpha(65)
                seri.setColor(dolgu)
                seri.setPen(QPen(renk, 2))
            else:
                seri = ust
                ust.setPointsVisible(True)

            chart.addSeries(seri)
            seri.attachAxis(x)
            seri.attachAxis(y)

    chart.legend().setVisible(len(seriler) > 1)
    if len(seriler) > 1:
        chart.legend().setAlignment(Qt.AlignBottom)
    return chart


def grafik_yuksekligi(tur, kategori_sayisi):
    """Az kategoride kompakt, cok kategoride okunabilir grafik."""
    if tur == "Yatay Çubuk":
        return max(215, min(750, 155 + kategori_sayisi * 43))

    if tur == "Pasta":
        return 285

    if kategori_sayisi <= 2:
        return 245

    if tur == "Sütun" and kategori_sayisi > 10:
        return 330

    return 285


def grafik_secimi_ekle(widget, rapor, varsayilan):
    """Var olan grafik bileşenine seçici ekler; API'yi değiştirmez."""
    secici = QComboBox(widget)
    secenekler = uygun_grafik_turleri(rapor)
    secici.addItems(secenekler)
    secici.setCurrentText(
        varsayilan if varsayilan in secenekler
        else secenekler[0]
    )
    secici.setMaximumWidth(190)
    secici.setToolTip(
        "Pasta grafiklerinde karşılaştırma varsa "
        "yalnızca seçilen dönem gösterilir."
    )

    widget.layout().insertWidget(2, secici)
    widget.grafik_turu = secici

    if not hasattr(widget, "bos"):
        bos = QLabel(
            "Seçilen dönemde görüntülenecek kayıt bulunmuyor.",
            widget,
        )
        bos.setAlignment(Qt.AlignCenter)
        bos.setMinimumHeight(85)
        bos.setStyleSheet("color: #8191A6; font-size: 12px;")
        widget.layout().insertWidget(3, bos)
        widget.bos = bos
        bos.hide()

    son_veri = {"args": None}

    def guncelle(*args):
        son_veri["args"] = args

        kategoriler, seriler = _veriler(rapor, args)

        # Günlük eğilim Çizgi/Alan'da bütün günleri korur.
        # Sütun görünümü yalnızca randevu bulunan günleri gösterir.
        if rapor == "randevu" and secici.currentText() == "Sütun":
            kayitli_gunler = [
                i for i, deger in enumerate(seriler[0][1])
                if deger > 0
            ]
            kategoriler = [kategoriler[i] for i in kayitli_gunler]
            seriler = [
                (
                    ad,
                    [degerler[i] for i in kayitli_gunler],
                )
                for ad, degerler in seriler
            ]

        pozitif_sayisi = sum(
            deger > 0
            for _, dizi in seriler
            for deger in dizi
        )

        veri_var = bool(kategoriler) and (
            rapor == "randevu" or pozitif_sayisi > 0
        )

        secenekler = uygun_grafik_turleri(rapor)
        if seriler and sum(v > 0 for v in seriler[0][1]) <= 1:
            secenekler = tuple(
                tur for tur in secenekler if tur != "Pasta"
            )

        mevcut = secici.currentText()
        gorunen = tuple(
            secici.itemText(i) for i in range(secici.count())
        )

        if gorunen != secenekler:
            secici.blockSignals(True)
            try:
                secici.clear()
                secici.addItems(secenekler)
                secici.setCurrentText(
                    mevcut if mevcut in secenekler
                    else (
                        "Yatay Çubuk"
                        if "Yatay Çubuk" in secenekler
                        else secenekler[0]
                    )
                )
            finally:
                secici.blockSignals(False)

        if hasattr(widget, "bos"):
            if not kategoriler:
                widget.bos.setText(
                    "Seçilen dönemde görüntülenecek kayıt bulunmuyor."
                )
            elif not veri_var:
                widget.bos.setText(
                    "Seçilen dönemde tüm değerler sıfır."
                )
            widget.bos.setVisible(not veri_var)

        widget.gorunum.setVisible(veri_var)

        if not veri_var:
            return

        widget.gorunum.setFixedHeight(
            grafik_yuksekligi(
                secici.currentText(),
                len(kategoriler),
            )
        )

        chart = grafik_olustur(
            kategoriler, seriler, secici.currentText()
        )
        widget.gorunum.setChart(chart)

    widget.guncelle = guncelle

    def secim_degisti(_):
        if son_veri["args"] is not None:
            guncelle(*son_veri["args"])

    secici.currentTextChanged.connect(secim_degisti)
    return secici
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
            dugme.toggled.connect(lambda secili, t=tur: self._degisti(t, secili))
            self._grup.addButton(dugme)
            self._duzen.addWidget(dugme)
            self._dugmeler[tur] = dugme
        if self._dugmeler and self._grup.checkedButton() is None:
            gecmis = self.blockSignals(True)
            next(iter(self._dugmeler.values())).setChecked(True)
            self.blockSignals(gecmis)

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
    border: 1px solid #E1E8F2;
    border-radius: 12px;
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


def grafik_secimi_ekle(widget, rapor, varsayilan):
    """Var olan grafik kartına üç düğmeli seçici ekler ve çizimi ortak grafik_olustur'a bağlar."""
    grafik_kartini_bicimlendir(widget)
    secici = GrafikTuruSecici(widget, varsayilan=varsayilan if varsayilan in GRAFIK_TURLERI else "Sütun")
    grafik_karti_baslik_satiri(widget, secici)
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
