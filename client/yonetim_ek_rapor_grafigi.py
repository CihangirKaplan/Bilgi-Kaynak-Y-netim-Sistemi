"""Tablo ağırlıklı yönetim raporları için grafik bileşeni."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCharts import QChartView

from client.yonetim_grafik_turleri import (
    GrafikTuruSecici, bos_etiketi_olustur, grafik_karti_baslik_satiri, grafik_kartini_bicimlendir,
    grafik_olustur, grafik_yuksekligi,
)


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


# Rapor -> (grafik başlığı, açıklama, ölçünün adı)
GRAFIK_METINLERI = {
    "Oda Kullanımı": ("Odalara Göre Kullanım", "Planlanan kullanım süresi (saat) · en çok kullanılan 10 oda", "Planlanan Süre (Saat)"),
    "Cihaz Kullanımı": ("Cihazlara Göre Rezervasyon", "Rezervasyon sayısı · en çok kullanılan 10 cihaz", "Rezervasyon Sayısı"),
    "Yetkiler": ("Rollere Göre Kullanıcı Sayısı", "Güncel durum · dönemden bağımsız", "Toplam Kullanıcı"),
    "Öğrenci Mevcudu": ("Öğrenci Türlerine Göre Mevcut", "Güncel durum · dönemden bağımsız", "Öğrenci Sayısı"),
    "Faaliyet Onayları": ("Faaliyet Türlerine Göre Kayıt", "Seçilen dönemdeki faaliyet kayıtları", "Faaliyet Kayıt Sayısı"),
    "Bakım Gecikmeleri": ("Cihazlara Göre Geciken Planlar", "Bugünkü durum · dönemden bağımsız", "Geciken Plan Sayısı"),
}


class EkRaporGrafigi(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EkRaporGrafigi")

        duzen = QVBoxLayout(self)
        self.baslik = QLabel("Rapor Grafiği")
        duzen.addWidget(self.baslik)
        self.aciklama = QLabel("")
        duzen.addWidget(self.aciklama)

        self.gorunum = QChartView()
        self.gorunum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        duzen.addWidget(self.gorunum)

        grafik_kartini_bicimlendir(self)
        self.grafik_turu = GrafikTuruSecici(self, varsayilan="Sütun")
        grafik_karti_baslik_satiri(self, self.grafik_turu)
        self.bos = bos_etiketi_olustur(self)
        duzen.insertWidget(1, self.bos)

        self._rapor = None
        self._kategoriler = []
        self._sayilar = []

        self.grafik_turu.currentTextChanged.connect(self.grafigi_ciz)
        self.gorunum.hide()

    def guncelle(self, rapor, veriler):
        self._rapor = rapor
        baslik, aciklama, _ = GRAFIK_METINLERI.get(rapor, (rapor + " Grafiği", "", "Sayı"))
        self.baslik.setText(baslik)
        self.aciklama.setText(aciklama)
        self.aciklama.setVisible(bool(aciklama))
        self._kategoriler, self._sayilar = grafik_verisi(rapor, veriler)
        self.grafigi_ciz()

    def grafigi_ciz(self, *_):
        var_mi = bool(self._kategoriler) and any(v > 0 for v in self._sayilar)

        self.bos.setText(
            "Seçilen dönemde tüm değerler sıfır."
            if self._kategoriler
            else "Seçilen dönemde görüntülenecek kayıt bulunmuyor."
        )
        self.bos.setVisible(not var_mi)
        self.gorunum.setVisible(var_mi)
        if not var_mi:
            return

        tur = self.grafik_turu.currentText()
        olcu = GRAFIK_METINLERI.get(self._rapor, ("", "", "Sayı"))[2]
        self.gorunum.setFixedHeight(grafik_yuksekligi(tur, len(self._kategoriler), self._kategoriler))
        self.gorunum.setChart(grafik_olustur(self._kategoriler, [(olcu, self._sayilar)], tur))
