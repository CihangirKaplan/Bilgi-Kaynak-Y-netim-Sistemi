"""TKYS yönetim istatistiklerini çok sayfalı PDF olarak kaydeder."""

import os
import tempfile
from pathlib import Path

from client.rapor_sayfasi_taban import yuzde_metni
from client.yonetim_rapor_hesaplari import gelmeme_orani, gerceklesen_randevu, tamamlanma_orani
from PySide6.QtCore import Qt, QRect, QDateTime
from PySide6.QtGui import (
    QPdfWriter, QPainter, QPageSize, QFont,
    QColor, QPen,
)


MAVI = QColor("#24559B")
GRI = QColor("#A3B1C5")
KOYU = QColor("#243653")
ACIK = QColor("#E3EAF5")


class RaporCizici:
    def __init__(self, painter, writer):
        self.p = painter
        self.writer = writer
        self.w = writer.width()
        self.h = writer.height()
        self.sayfa = 0

    def metin(self, x, y, icerik, boyut=12, kalin=False):
        font = QFont("Arial", boyut)
        font.setBold(kalin)
        self.p.setFont(font)
        self.p.setPen(KOYU)
        self.p.drawText(int(x), int(y), str(icerik))

    def yeni_sayfa(self, baslik, baslangic, bitis):
        if self.sayfa:
            if not self.writer.newPage():
                raise RuntimeError("PDF'de yeni sayfa oluşturulamadı.")
        self.sayfa += 1

        self.p.fillRect(
            QRect(0, 0, self.w, 80), MAVI
        )
        self.p.setPen(Qt.white)
        self.p.setFont(QFont("Arial", 18, QFont.Bold))
        self.p.drawText(48, 47, "TKYS - Yönetim Raporları")

        self.metin(48, 120, baslik, 17, True)
        self.metin(
            48, 148,
            f"Dönem: {baslangic} / {bitis}",
            10
        )
        self.metin(
            48, 170,
            "Oluşturulma: "
            + QDateTime.currentDateTime().toString("dd.MM.yyyy HH:mm"),
            9,
        )

        self.p.setPen(QPen(ACIK, 1))
        self.p.drawLine(48, 185, self.w - 48, 185)
        self.metin(
            48, self.h - 38,
            f"TKYS | Yönetim Raporları | Sayfa {self.sayfa}/5",
            9,
        )

    def satirlar(self, satirlar):
        y = 218
        for ad, deger in satirlar:
            self.metin(52, y, ad, 11)
            self.metin(
                self.w - 205, y, deger, 11, True
            )
            self.p.setPen(QPen(ACIK, 1))
            self.p.drawLine(
                50, y + 8, self.w - 50, y + 8
            )
            y += 35
        return y

    def bar_grafik(self, baslik, veriler, y):
        """Etiket, sayı çiftlerinden yatay sütunlar oluşturur."""
        y = max(y + 28, 470)
        self.metin(50, y, baslik, 13, True)
        y += 27

        veriler = list(veriler)[:8]

        if not veriler or not any(
            float(sayi) > 0 for _, sayi in veriler
        ):
            self.metin(
                52, y + 30,
                "Seçilen dönemde grafik için kayıt bulunamadı.",
                11,
            )
            return

        en_buyuk = max(
            [float(sayi) for _, sayi in veriler] + [1.0]
        )

        for ad, sayi in veriler:
            sayi = max(0, float(sayi))
            self.metin(52, y + 17, str(ad)[:30], 9)

            uzunluk = int(335 * sayi / en_buyuk)
            if uzunluk > 0:
                self.p.fillRect(
                    QRect(300, y + 2, uzunluk, 20),
                    MAVI,
                )

            self.metin(655, y + 18, f"{sayi:g}", 10, True)
            y += 43

    def karsilastirma(self, baslik, veriler, y):
        """Etiket, seçilen dönem, önceki dönem üçlülerini çizer."""
        y = max(y + 25, 455)
        self.metin(50, y, baslik, 13, True)
        y += 28

        veriler = list(veriler)[:6]

        if not veriler or not any(
            float(deger) > 0
            for _, a, b in veriler
            for deger in (a, b)
        ):
            self.metin(
                52, y + 30,
                "Karşılaştırılan dönemlerde kayıt bulunamadı.",
                11,
            )
            return

        en_buyuk = max(
            [float(deger) for _, a, b in veriler for deger in (a, b)]
            + [1.0]
        )

        for ad, simdi, onceki in veriler:
            self.metin(52, y + 20, str(ad)[:28], 9)
            simdi = max(0, float(simdi))
            onceki = max(0, float(onceki))

            a = int(330 * simdi / en_buyuk)
            b = int(330 * onceki / en_buyuk)

            if a:
                self.p.fillRect(QRect(300, y, a, 13), MAVI)
            if b:
                self.p.fillRect(QRect(300, y + 16, b, 13), GRI)

            self.metin(
                655, y + 13, f"{simdi:g}", 9, True
            )
            self.metin(655, y + 29, f"{onceki:g}", 9)
            y += 60

        self.metin(
            50, y + 15,
            "Mavi: seçilen dönem  |  Gri: önceki dönem",
            9,
        )

    def not_ekle(self, metin):
        alan = QRect(
            50, self.h - 135, self.w - 100, 75
        )
        self.p.setPen(KOYU)
        self.p.setFont(QFont("Arial", 10))
        self.p.drawText(
            alan, Qt.TextWordWrap, metin
        )


def pdf_olustur(dosya_yolu, baslangic, bitis, veriler):
    """Tamamen alınmış API yanıtlarından PDF oluşturur.

    Önce geçici dosyaya yazar, başarılıysa hedefe taşır.
    """
    hedef = Path(dosya_yolu)
    gecici = None

    try:
        fd, gecici = tempfile.mkstemp(
            prefix=".tkys_rapor_",
            suffix=".pdf",
            dir=str(hedef.parent),
        )
        os.close(fd)

        writer = QPdfWriter(gecici)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(96)
        writer.setTitle("TKYS Yönetim Raporları")

        painter = QPainter()
        if not painter.begin(writer):
            raise RuntimeError("PDF yazıcısı başlatılamadı.")

        try:
            c = RaporCizici(painter, writer)

            r = veriler["randevu"]["ozet"]
            r_once = veriler["randevu"]["onceki_ozet"]
            d = veriler["cihaz"]["ozet"]
            o = veriler["ogrenci"]
            p = veriler["proje"]["ozet"]

            # Ekrandaki kural: yapılan iş sayılarında iptal edilenler hariçtir, iptaller ayrıca yazılır.
            # 1. Genel Bakış
            c.yeni_sayfa("Genel Bakış", baslangic, bitis)
            c.satirlar([
                ("Randevu (iptal hariç)", gerceklesen_randevu(r)),
                ("Gelmeme oranı", yuzde_metni(gelmeme_orani(r))),
                ("Sonucu girilmemiş randevu", r.get("sonucu_girilmemis", 0)),
                ("Arıza bildirimi", d["ariza"]),
                ("Kalibrasyon kaydı", d["kalibrasyon"]),
                ("Aktif öğrenci (güncel)", o["guncel_ogrenci"]["aktif"]),
                ("Faaliyet puanı", o["ozet"]["toplam_puan"]),
                ("Cihaz rezervasyonu (iptal hariç)", p["rezervasyon_iptal_edilmemis"]),
                ("Oda etkinliği (iptal hariç)", p["etkinlik_iptal_edilmemis"]),
            ])
            c.not_ekle(
                "Öğrenci mevcudu günceldir. Diğer sayılar seçilen "
                "döneme aittir. "
                "İptal edilenler sayılara dahil değildir."
            )

            # 2. Randevular
            c.yeni_sayfa("Randevu İstatistikleri", baslangic, bitis)
            y = c.satirlar([
                ("Gerçekleşen randevu (iptal hariç)", gerceklesen_randevu(r)),
                ("Önceki dönem (iptal hariç)", gerceklesen_randevu(r_once)),
                ("Tamamlanan", r["tamamlandi"]),
                ("Gelmedi", r["gelmedi"]),
                ("Tamamlanma oranı", yuzde_metni(tamamlanma_orani(r))),
                ("Gelmeme oranı", yuzde_metni(gelmeme_orani(r))),
                ("Sonucu girilmemiş", r.get("sonucu_girilmemis", 0)),
                ("İptal edilen", r["iptal_edildi"]),
            ])
            c.bar_grafik(
                "Randevu Durumları",
                [
                    ("Planlandı", r["planlandi"]),
                    ("Tamamlandı", r["tamamlandi"]),
                    ("İptal", r["iptal_edildi"]),
                    ("Gelmedi", r["gelmedi"]),
                ],
                y,
            )

            # 3. Cihazlar
            c.yeni_sayfa("Cihaz İstatistikleri", baslangic, bitis)
            alanlar = [
                ("bakim", "Bakım"),
                ("kalibrasyon", "Kalibrasyon"),
                ("ariza", "Arıza"),
                ("rezervasyon", "Rezervasyon (iptal hariç)"),
            ]
            y = c.satirlar([
                (ad, d[kod]) for kod, ad in alanlar
            ])
            c.karsilastirma(
                "Dönem Karşılaştırması",
                [
                    (ad, d[kod], veriler["cihaz"]["onceki_ozet"][kod])
                    for kod, ad in alanlar
                ],
                y,
            )
            c.not_ekle(
                "Bunlar işlem kayıtlarıdır; cihazların anlık "
                "durumları veya kesin kullanım süreleri değildir."
            )

            # 4. Öğrenciler
            c.yeni_sayfa("Öğrenci İstatistikleri", baslangic, bitis)
            s = o["ozet"]
            y = c.satirlar([
                ("Toplam öğrenci (güncel)", o["guncel_ogrenci"]["toplam"]),
                ("Aktif öğrenci (güncel)", o["guncel_ogrenci"]["aktif"]),
                ("Faaliyet kaydı", s["kayit_sayisi"]),
                ("Faaliyet yapan öğrenci", s["faaliyet_yapan_ogrenci"]),
                ("Toplam puan", s["toplam_puan"]),
                (
                    "Önceki dönem faaliyet kaydı",
                    o["onceki_ozet"]["kayit_sayisi"],
                ),
                (
                    "Önceki dönem toplam puanı",
                    o["onceki_ozet"]["toplam_puan"],
                ),
            ])
            c.bar_grafik(
                "Faaliyetlere Göre Puanlar",
                [
                    (f["faaliyet"], f["toplam_puan"])
                    for f in o["faaliyet_dagilimi"]
                ],
                y,
            )
            c.not_ekle(
                "Toplam puan, seçilen dönemdeki bütün faaliyet kayıtlarının puanlarının toplamıdır."
            )

            # 5. Proje / Etkinlik
            c.yeni_sayfa("Proje ve Etkinlik Kayıtları", baslangic, bitis)
            y = c.satirlar([
                ("Cihaz rezervasyonu (iptal hariç)", p["rezervasyon_iptal_edilmemis"]),
                ("İptal edilen rezervasyon", p["rezervasyon_iptal"]),
                ("Oda etkinliği (iptal hariç)", p["etkinlik_iptal_edilmemis"]),
                ("İptal edilen etkinlik", max(0, p["etkinlik_toplam"] - p["etkinlik_iptal_edilmemis"])),
                ("Kayıtlı katılımcı toplamı", p["kayitli_katilimci_toplami"]),
                (
                    "Önceki dönem rezervasyonu (iptal hariç)",
                    veriler["proje"]["onceki_ozet"]["rezervasyon_iptal_edilmemis"],
                ),
                (
                    "Önceki dönem etkinliği (iptal hariç)",
                    veriler["proje"]["onceki_ozet"]["etkinlik_iptal_edilmemis"],
                ),
                (
                    "Önceki dönem katılımcı toplamı",
                    veriler["proje"]["onceki_ozet"]["kayitli_katilimci_toplami"],
                ),
            ])
            c.bar_grafik(
                "Proje Türlerine Göre Rezervasyonlar",
                [
                    (k["tur"], k["rezervasyon_sayisi"])
                    for k in veriler["proje"]["proje_turu_dagilimi"]
                ],
                y,
            )
            c.not_ekle(
                "Rezervasyonlar gerçekleşmiş deney sayısı değildir. "
                "Katılımcı toplamı benzersiz kişi sayısı değildir."
            )

        finally:
            painter.end()

        del painter
        del writer

        if Path(gecici).stat().st_size == 0:
            raise RuntimeError("Oluşturulan PDF boş.")

        os.replace(gecici, hedef)
        gecici = None

    finally:
        if gecici and os.path.exists(gecici):
            os.unlink(gecici)
