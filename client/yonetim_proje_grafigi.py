
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCharts import (
    QChart, QChartView, QBarSet, QHorizontalBarSeries,
    QBarCategoryAxis, QValueAxis
)


class YonetimProjeGrafigi(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("YonetimProjeGrafik")
        self.setStyleSheet("""
            QFrame#YonetimProjeGrafik {
                background: #FFFFFF;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
            QFrame#YonetimProjeGrafik QLabel {
                background: transparent;
                border: none;
            }
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 13, 16, 12)
        lay.setSpacing(6)

        baslik = QLabel("Proje Türlerine Göre Rezervasyonlar")
        baslik.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #16294B;"
        )
        lay.addWidget(baslik)

        aciklama = QLabel(
            "Seçilen dönemde proje türlerine bağlı cihaz rezervasyonları"
        )
        aciklama.setStyleSheet(
            "color: #7487A3; font-size: 11px;"
        )
        lay.addWidget(aciklama)

        self.bos = QLabel(
            "Seçilen dönemde proje türlerine ait "
            "cihaz rezervasyonu bulunmuyor."
        )
        self.bos.setAlignment(Qt.AlignCenter)
        self.bos.setMinimumHeight(95)
        self.bos.setStyleSheet(
            "color: #8191A6; font-size: 12px;"
        )
        lay.addWidget(self.bos)

        self.gorunum = QChartView()
        self.gorunum.setRenderHint(QPainter.Antialiasing)
        self.gorunum.setFrameShape(QFrame.NoFrame)
        self.gorunum.setBackgroundBrush(QColor("#FFFFFF"))
        self.gorunum.setStyleSheet(
            "background: #FFFFFF; border: none;"
        )
        lay.addWidget(self.gorunum)
        self.gorunum.hide()

    def guncelle(self, dagilim):
        veriler = [
            (
                str(kayit.get("tur") or "Belirtilmemiş"),
                max(0, int(kayit.get("rezervasyon_sayisi") or 0))
            )
            for kayit in (dagilim or [])
        ]

        # Hiç kayıt yoksa büyük ve boş bir grafik oluşturma.
        if not veriler or not any(sayi for _, sayi in veriler):
            self.gorunum.hide()
            self.bos.show()
            return

        # QtCharts ilk yatay kategoriyi altta gösterir.
        veriler.sort(key=lambda item: item[1])

        self.bos.hide()
        self.gorunum.show()
        self.gorunum.setFixedHeight(
            max(245, 55 * len(veriler) + 80)
        )

        chart = QChart()
        chart.setBackgroundVisible(True)
        chart.setBackgroundBrush(QColor("#FFFFFF"))
        chart.setPlotAreaBackgroundVisible(False)

        cubuk = QBarSet("Rezervasyon")
        cubuk.setColor(QColor("#6352B5"))
        cubuk.append([sayi for _, sayi in veriler])

        seri = QHorizontalBarSeries()
        seri.append(cubuk)
        seri.setBarWidth(0.60)
        chart.addSeries(seri)

        kategoriler = QBarCategoryAxis()
        kategoriler.append([ad for ad, _ in veriler])
        kategoriler.setLabelsColor(QColor("#405976"))
        chart.addAxis(kategoriler, Qt.AlignLeft)
        seri.attachAxis(kategoriler)

        eksen = QValueAxis()
        en_buyuk = max(sayi for _, sayi in veriler)
        ust = max(4, ((en_buyuk + 3) // 4) * 4)
        eksen.setRange(0, ust)
        eksen.setTickCount(5)
        eksen.setLabelFormat("%.0f")
        eksen.setLabelsColor(QColor("#61758E"))
        eksen.setGridLineColor(QColor("#E8EEF7"))
        chart.addAxis(eksen, Qt.AlignBottom)
        seri.attachAxis(eksen)

        chart.legend().setVisible(False)
        self.gorunum.setChart(chart)
