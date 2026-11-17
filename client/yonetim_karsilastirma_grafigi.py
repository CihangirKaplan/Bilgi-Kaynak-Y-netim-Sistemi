
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QSizePolicy
)
from PySide6.QtCharts import (
    QChart, QChartView, QBarSet, QBarSeries,
    QBarCategoryAxis, QValueAxis
)


class YonetimKarsilastirmaGrafigi(QFrame):
    def __init__(
        self, parent=None,
        baslik_metni="Dönem Karşılaştırması",
        aciklama_metni="İşlem sayıları · Seçilen dönem ve önceki dönem"
    ):
        super().__init__(parent)

        self.setObjectName("YonetimKarsilastirma")
        self.setStyleSheet("""
            QFrame#YonetimKarsilastirma {
                background: #FFFFFF;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
            QFrame#YonetimKarsilastirma QLabel {
                border: none;
                background: transparent;
            }
        """)

        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(16, 13, 16, 10)
        duzen.setSpacing(5)

        baslik = QLabel(baslik_metni)
        baslik.setStyleSheet("""
            color: #16294B;
            font-size: 15px;
            font-weight: bold;
        """)
        duzen.addWidget(baslik)

        aciklama = QLabel(
            aciklama_metni
        )
        aciklama.setStyleSheet(
            "color: #7487A3; font-size: 11px;"
        )
        duzen.addWidget(aciklama)

        self.gorunum = QChartView()
        self.gorunum.setRenderHint(QPainter.Antialiasing)
        self.gorunum.setFixedHeight(275)
        self.gorunum.setFrameShape(QFrame.NoFrame)
        self.gorunum.setStyleSheet(
            "background-color: #FFFFFF; border: none;"
        )
        self.gorunum.setBackgroundBrush(QColor("#FFFFFF"))
        self.gorunum.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        duzen.addWidget(self.gorunum)

        self.guncelle(
            ["Randevu", "Kalibrasyon", "Oda etkinliği"],
            [0, 0, 0],
            [0, 0, 0],
        )

    def guncelle(self, kategoriler, secilen, onceki):
        secilen = [max(0, float(x)) for x in secilen]
        onceki = [max(0, float(x)) for x in onceki]

        chart = QChart()
        chart.setBackgroundVisible(True)
        chart.setBackgroundBrush(QColor("#FFFFFF"))
        chart.setPlotAreaBackgroundVisible(False)
        chart.setMargins(
            __import__("PySide6.QtCore", fromlist=["QMargins"])
            .QMargins(4, 4, 4, 4)
        )

        bu_donem = QBarSet("Seçilen Dönem")
        bu_donem.setColor(QColor("#6352B5"))
        bu_donem.append(secilen)

        onceki_donem = QBarSet("Önceki Dönem")
        onceki_donem.setColor(QColor("#B29AE8"))
        onceki_donem.append(onceki)

        seri = QBarSeries()
        seri.append(bu_donem)
        seri.append(onceki_donem)
        seri.setBarWidth(0.60)

        chart.addSeries(seri)

        yatay = QBarCategoryAxis()
        yatay.append(kategoriler)
        yatay.setLabelsColor(QColor("#405976"))
        chart.addAxis(yatay, Qt.AlignBottom)
        seri.attachAxis(yatay)

        dikey = QValueAxis()
        en_yuksek = max(secilen + onceki + [0])
        dikey.setRange(
            0,
            max(4, ((int(en_yuksek * 1.2) + 3) // 4) * 4)
        )
        dikey.setTickCount(5)
        dikey.setLabelFormat("%.0f")
        dikey.setLabelsColor(QColor("#61758E"))
        dikey.setGridLineColor(QColor("#E8EEF7"))

        chart.addAxis(dikey, Qt.AlignLeft)
        seri.attachAxis(dikey)

        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignBottom)
        chart.legend().setLabelColor(QColor("#405976"))

        self.gorunum.setChart(chart)
