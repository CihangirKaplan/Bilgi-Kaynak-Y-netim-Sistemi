"""Tablo ağırlıklı yönetim raporları için grafik bileşeni."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCharts import QChartView

from client.yonetim_grafik_turleri import (
    grafik_olustur, GRAFIK_TURLERI,
    uygun_grafik_turleri,
    grafik_yuksekligi,
)
from PySide6.QtWidgets import QComboBox


def grafik_verisi(rapor, veriler):
    """Rapor verilerini grafik kategorilerine ve sayılara dönüştür."""
    kaynaklar = {
        "Oda Kullanımı": (
            "oda", "odalar", "oda_adi", "toplam_saat"
        ),
        "Cihaz Kullanımı": (
            "cihaz_rez", "cihazlar", "cihaz_adi", "rezervasyon_sayisi"
        ),
        "Yetkiler": (
            "yetki", "roller", "rol_adi", "kullanici_sayisi"
        ),
        "Öğrenci Mevcudu": (
            "ogrenci_rapor", "tur_dagilimi", "etiket", "toplam"
        ),
        "Faaliyet Onayları": (
            "faaliyet_rapor", "faaliyetler", "faaliyet", "kayit_sayisi"
        ),
        "Bakım Gecikmeleri": (
            "bakim_plani", "cihaz_ozeti", "cihaz", "geciken"
        ),
    }

    if rapor not in kaynaklar:
        return [], []

    kaynak, liste, ad, sayi = kaynaklar[rapor]
    veri = veriler.get(kaynak)

    if not veri:
        return [], []

    satirlar = veri.get(liste, [])[:10]
    kategoriler = [str(k.get(ad) or "Belirtilmemiş") for k in satirlar]
    sayilar = [max(0, float(k.get(sayi) or 0)) for k in satirlar]

    if rapor == "Cihaz Kullanımı":
        kategoriler = [
            (
                f"{k.get('envanter_kodu')} - {k.get('cihaz_adi')}"
                if k.get("envanter_kodu")
                else str(k.get("cihaz_adi") or "Belirtilmemiş")
            )
            for k in satirlar
        ]

    return kategoriler, sayilar


class EkRaporGrafigi(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setStyleSheet("""
            EkRaporGrafigi {
                background: white;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
            EkRaporGrafigi QLabel {
                border: none;
                background: transparent;
            }
        """)

        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(16, 13, 16, 12)
        duzen.setSpacing(8)

        self.baslik = QLabel("Rapor Grafiği")
        self.baslik.setStyleSheet(
            "font-weight: bold; font-size: 15px; color: #16294B;"
        )
        duzen.addWidget(self.baslik)

        self.grafik_turu = QComboBox()
        self.grafik_turu.addItems(GRAFIK_TURLERI)
        self.grafik_turu.setCurrentText("Sütun")
        self.grafik_turu.setMaximumWidth(190)
        duzen.addWidget(self.grafik_turu)

        self.bos = QLabel("Bu rapor için görüntülenecek veri yok.")
        self.bos.setAlignment(Qt.AlignCenter)
        self.bos.setMinimumHeight(90)
        duzen.addWidget(self.bos)

        self.gorunum = QChartView()
        self.gorunum.setRenderHint(QPainter.Antialiasing)
        self.gorunum.setMinimumHeight(280)
        duzen.addWidget(self.gorunum)

        self._kategoriler = []
        self._sayilar = []

        self.grafik_turu.currentTextChanged.connect(
            self.grafigi_ciz
        )
        self.gorunum.hide()

    def guncelle(self, rapor, veriler):
        self._rapor = rapor
        self.baslik.setText(rapor + " Grafiği")

        secenekler = uygun_grafik_turleri(rapor)

        self.grafik_turu.blockSignals(True)
        try:
            mevcut = self.grafik_turu.currentText()
            self.grafik_turu.clear()
            self.grafik_turu.addItems(secenekler)
            self.grafik_turu.setCurrentText(
                mevcut if mevcut in secenekler
                else secenekler[0]
            )
        finally:
            self.grafik_turu.blockSignals(False)
        self._kategoriler, self._sayilar = grafik_verisi(
            rapor, veriler
        )

        secenekler = uygun_grafik_turleri(rapor)
        if sum(v > 0 for v in self._sayilar) <= 1:
            secenekler = tuple(
                tur for tur in secenekler if tur != "Pasta"
            )

        mevcut = self.grafik_turu.currentText()
        self.grafik_turu.blockSignals(True)
        try:
            self.grafik_turu.clear()
            self.grafik_turu.addItems(secenekler)
            self.grafik_turu.setCurrentText(
                mevcut if mevcut in secenekler
                else (
                    "Yatay Çubuk"
                    if "Yatay Çubuk" in secenekler
                    else secenekler[0]
                )
            )
        finally:
            self.grafik_turu.blockSignals(False)

        self.grafigi_ciz()

    def grafigi_ciz(self, *_):
        var_mi = bool(self._kategoriler) and any(
            v > 0 for v in self._sayilar
        )

        self.bos.setText(
            "Seçilen dönemde tüm değerler sıfır."
            if self._kategoriler
            else "Seçilen dönemde görüntülenecek kayıt bulunmuyor."
        )
        self.bos.setVisible(not var_mi)
        self.gorunum.setVisible(var_mi)

        if not var_mi:
            return

        olculer = {
            "Oda Kullanımı": "Planlanan Süre (Saat)",
            "Cihaz Kullanımı": "Rezervasyon Sayısı",
            "Yetkiler": "Toplam Kullanıcı",
            "Öğrenci Mevcudu": "Öğrenci Sayısı",
            "Faaliyet Onayları": "Faaliyet Kayıt Sayısı",
            "Bakım Gecikmeleri": "Geciken Plan Sayısı",
        }

        self.gorunum.setFixedHeight(
            grafik_yuksekligi(
                self.grafik_turu.currentText(),
                len(self._kategoriler),
            )
        )

        chart = grafik_olustur(
            self._kategoriler,
            [(olculer.get(self._rapor, "Sayı"), self._sayilar)],
            self.grafik_turu.currentText(),
        )
        self.gorunum.setChart(chart)
