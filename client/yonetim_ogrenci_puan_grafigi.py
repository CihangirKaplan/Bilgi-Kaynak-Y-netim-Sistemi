
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QSizePolicy
)
from PySide6.QtCharts import (
    QChart, QChartView, QBarSet,
    QHorizontalBarSeries, QBarCategoryAxis, QValueAxis
)


class YonetimOgrenciPuanGrafigi(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("YonetimOgrenciPuanGrafik")
        self.setStyleSheet("""
            QFrame#YonetimOgrenciPuanGrafik {
                background: #FFFFFF;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
            QFrame#YonetimOgrenciPuanGrafik QLabel {
                background: transparent;
                border: none;
            }
        """)

        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(16, 13, 16, 12)
        duzen.setSpacing(6)

        baslik = QLabel("Faaliyet Türlerine Göre Puan Dağılımı")
        baslik.setStyleSheet(
            "color: #16294B; font-size: 15px;"
            "font-weight: bold;"
        )
        duzen.addWidget(baslik)

        aciklama = QLabel(
            "Seçilen dönemde faaliyet türlerinin toplam puanları"
        )
        aciklama.setStyleSheet(
            "color: #7487A3; font-size: 11px;"
        )
        duzen.addWidget(aciklama)

        self.bos = QLabel(
            "Seçilen dönemde öğrenci faaliyeti bulunmuyor."
        )
        self.bos.setAlignment(Qt.AlignCenter)
        self.bos.setMinimumHeight(100)
        self.bos.setStyleSheet(
            "color: #8191A6; font-size: 12px;"
        )
        duzen.addWidget(self.bos)

        self.gorunum = QChartView()
        self.gorunum.setRenderHint(QPainter.Antialiasing)
        self.gorunum.setFrameShape(QFrame.NoFrame)
        self.gorunum.setBackgroundBrush(QColor("#FFFFFF"))
        self.gorunum.setStyleSheet(
            "background: #FFFFFF; border: none;"
        )
        self.gorunum.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        duzen.addWidget(self.gorunum)
        self.gorunum.hide()

    def guncelle(self, faaliyetler):
        veriler = []

        for faaliyet in faaliyetler or []:
            ad = str(faaliyet.get("faaliyet") or "Bilinmeyen")
            puan = max(
                0, float(faaliyet.get("toplam_puan") or 0)
            )
            veriler.append((ad, puan))

        veriler.sort(key=lambda x: x[1])

        if not veriler:
            self.bos.show()
            self.gorunum.hide()
            return

        self.bos.hide()
        self.gorunum.show()

        self.gorunum.setFixedHeight(
            max(270, 65 * len(veriler) + 85)
        )

        chart = QChart()
        chart.setBackgroundVisible(True)
        chart.setBackgroundBrush(QColor("#FFFFFF"))
        chart.setPlotAreaBackgroundVisible(False)

        puanlar = QBarSet("Toplam Puan")
        puanlar.setColor(QColor("#6352B5"))
        puanlar.append([puan for _, puan in veriler])

        seri = QHorizontalBarSeries()
        seri.append(puanlar)
        seri.setBarWidth(0.58)
        chart.addSeries(seri)

        kategoriler = QBarCategoryAxis()
        kategoriler.append([ad for ad, _ in veriler])
        kategoriler.setLabelsColor(QColor("#405976"))

        chart.addAxis(kategoriler, Qt.AlignLeft)
        seri.attachAxis(kategoriler)

        deger = QValueAxis()
        en_buyuk = max(p for _, p in veriler)
        ust = max(4, int(en_buyuk * 1.15) + 1)

        deger.setRange(0, ust)
        deger.setTickCount(5)
        deger.setLabelFormat("%.0f")
        deger.setLabelsColor(QColor("#61758E"))
        deger.setGridLineColor(QColor("#E8EEF7"))

        chart.addAxis(deger, Qt.AlignBottom)
        seri.attachAxis(deger)

        chart.legend().setVisible(False)

        self.gorunum.setChart(chart)
