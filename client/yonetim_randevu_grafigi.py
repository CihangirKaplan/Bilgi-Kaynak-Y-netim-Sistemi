
import math

from PySide6.QtCore import Qt, QDate, QDateTime, QTime
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QSizePolicy
)
from PySide6.QtCharts import (
    QChart, QChartView, QLineSeries,
    QDateTimeAxis, QValueAxis
)


class YonetimRandevuGrafigi(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("YonetimRandevuGrafik")
        self.setStyleSheet("""
            QFrame#YonetimRandevuGrafik {
                background: #FFFFFF;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
            QFrame#YonetimRandevuGrafik QLabel {
                background: transparent;
                border: none;
            }
        """)

        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(16, 13, 16, 12)
        duzen.setSpacing(5)

        baslik = QLabel("Günlük Randevu Eğilimi")
        baslik.setStyleSheet(
            "color: #16294B;"
            "font-size: 15px;"
            "font-weight: bold;"
        )
        duzen.addWidget(baslik)

        aciklama = QLabel(
            "Seçilen tarih aralığındaki günlük randevu sayıları"
        )
        aciklama.setStyleSheet(
            "color: #7487A3; font-size: 11px;"
        )
        duzen.addWidget(aciklama)

        self.bos = QLabel(
            "Seçilen dönemde görüntülenecek günlük veri yok."
        )
        self.bos.setAlignment(Qt.AlignCenter)
        self.bos.setStyleSheet(
            "color: #8191A6; font-size: 12px;"
        )
        self.bos.setMinimumHeight(100)
        duzen.addWidget(self.bos)

        self.gorunum = QChartView()
        self.gorunum.setRenderHint(QPainter.Antialiasing)
        self.gorunum.setFixedHeight(265)
        self.gorunum.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        self.gorunum.setFrameShape(QFrame.NoFrame)
        self.gorunum.setBackgroundBrush(QColor("#FFFFFF"))
        self.gorunum.setStyleSheet(
            "background: #FFFFFF; border: none;"
        )

        duzen.addWidget(self.gorunum)
        self.gorunum.hide()

    def guncelle(self, gunluk):
        veriler = []

        for kayit in gunluk or []:
            tarih = QDate.fromString(
                str(kayit["tarih"]), "yyyy-MM-dd"
            )
            if not tarih.isValid():
                continue

            sayi = max(0, int(kayit["sayi"]))
            veriler.append((tarih, sayi))

        veriler.sort(key=lambda oge: oge[0].toJulianDay())

        if not veriler:
            self.gorunum.hide()
            self.bos.show()
            return

        self.bos.hide()
        self.gorunum.show()

        chart = QChart()
        chart.setBackgroundVisible(True)
        chart.setBackgroundBrush(QColor("#FFFFFF"))
        chart.setPlotAreaBackgroundVisible(False)

        seri = QLineSeries()
        seri.setName("Randevu Sayısı")
        seri.setPen(QPen(QColor("#6352B5"), 3))
        seri.setPointsVisible(True)
        seri.setPointLabelsVisible(False)

        for tarih, sayi in veriler:
            zaman = QDateTime(tarih, QTime(12, 0))
            seri.append(zaman.toMSecsSinceEpoch(), sayi)

        chart.addSeries(seri)

        x = QDateTimeAxis()
        x.setFormat("dd.MM")
        x.setTickCount(min(6, max(2, len(veriler))))
        x.setLabelsColor(QColor("#61758E"))
        x.setGridLineColor(QColor("#EEF2F8"))

        ilk = veriler[0][0]
        son = veriler[-1][0]

        if ilk == son:
            ilk = ilk.addDays(-1)
            son = son.addDays(1)

        x.setRange(
            QDateTime(ilk, QTime(12, 0)),
            QDateTime(son, QTime(12, 0)),
        )

        chart.addAxis(x, Qt.AlignBottom)
        seri.attachAxis(x)

        y = QValueAxis()
        en_buyuk = max(sayi for _, sayi in veriler)
        ust = max(4, math.ceil(en_buyuk / 4) * 4)

        y.setRange(0, ust)
        y.setTickCount(5)
        y.setLabelFormat("%.0f")
        y.setLabelsColor(QColor("#61758E"))
        y.setGridLineColor(QColor("#E8EEF7"))

        chart.addAxis(y, Qt.AlignLeft)
        seri.attachAxis(y)

        chart.legend().setVisible(False)

        self.gorunum.setChart(chart)
