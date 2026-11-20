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
