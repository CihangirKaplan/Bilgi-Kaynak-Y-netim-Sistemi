
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout
)

ANA = "#6352B5"
ONCEKI = "#8A72C5"


def yazi(metin, boyut=12, renk="#243653", kalin=False):
    etiket = QLabel(str(metin))
    etiket.setStyleSheet(
        f"color: {renk}; font-size: {boyut}px;"
        + ("font-weight: bold;" if kalin else "")
        + "background: transparent; border: none;"
    )
    return etiket


class OzetPanel(QFrame):
    def __init__(self, baslik, aciklama):
        super().__init__()

        self.setObjectName("GenelBakisOzetPanel")
        self.setStyleSheet("""
            QFrame#GenelBakisOzetPanel {
                background: #FFFFFF;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
        """)

        self.duzen = QVBoxLayout(self)
        self.duzen.setContentsMargins(16, 13, 16, 14)
        self.duzen.setSpacing(8)

        self.duzen.addWidget(
            yazi(baslik, 15, "#16294B", True)
        )
        self.duzen.addWidget(
            yazi(aciklama, 11, "#7487A3")
        )


class OperasyonelOzet(OzetPanel):
    def __init__(self):
        super().__init__(
            "Operasyonel Faaliyetler",
            "İşlem sayıları · Dönem karşılaştırması"
        )

        self.donem_tarihleri = yazi(
            "Tarih aralıkları yükleniyor...",
            11, "#61758E"
        )
        self.duzen.addWidget(self.donem_tarihleri)

        grid = QGridLayout()
        grid.setSpacing(10)
        self.duzen.addLayout(grid)

        adlar = [
            "Randevu", "Bakım", "Kalibrasyon",
            "Arıza", "Cihaz Rezervasyonu", "Oda Etkinliği"
        ]

        self.degerler = []

        for i, ad in enumerate(adlar):
            kart = QFrame()
            kart.setStyleSheet("""
                QFrame {
                    background: #F8FAFE;
                    border: 1px solid #E4EAF5;
                    border-radius: 8px;
                }
            """)

            lay = QVBoxLayout(kart)
            lay.setContentsMargins(12, 10, 12, 10)
            lay.setSpacing(7)

            lay.addWidget(
                yazi(ad, 12, "#263A59", True)
            )

            sayilar = QHBoxLayout()
            sayilar.setSpacing(12)

            bu = yazi("0", 20, ANA, True)
            gecmis = yazi("0", 17, ONCEKI, True)

            sol = QVBoxLayout()
            sol.addWidget(
                yazi("Bu Dönem", 10, "#7788A2")
            )
            sol.addWidget(bu)

            sag = QVBoxLayout()
            sag.addWidget(
                yazi("Önceki Dönem", 10, "#7788A2")
            )
            sag.addWidget(gecmis)

            sayilar.addLayout(sol, 1)
            sayilar.addLayout(sag, 1)

            lay.addLayout(sayilar)

            # İki sütun, üç satır.
            grid.addWidget(kart, i // 2, i % 2)
            self.degerler.append((bu, gecmis))

    def tarihleri_guncelle(self, secilen, onceki):
        from datetime import date

        def bicimlendir(donem):
            ilk = date.fromisoformat(donem["baslangic"])
            son = date.fromisoformat(donem["bitis"])
            return (
                f"{ilk:%d.%m.%Y} – {son:%d.%m.%Y}"
            )

        self.donem_tarihleri.setText(
            f"Bu Dönem: {bicimlendir(secilen)}"
            f"    |    "
            f"Önceki Dönem: {bicimlendir(onceki)}"
        )

    def guncelle(self, secilen, onceki):
        for (bu, gecmis), a, b in zip(
            self.degerler, secilen, onceki
        ):
            bu.setText(str(a))
            gecmis.setText(str(b))


class OgrenciFaaliyetOzeti(OzetPanel):
    def __init__(self):
        super().__init__(
            "Öğrenci Faaliyet Özeti",
            "Öğrenci mevcudu güncel, faaliyetler seçilen döneme aittir"
        )

        grid = QGridLayout()
        grid.setSpacing(10)
        self.duzen.addLayout(grid)

        alanlar = [
            ("Toplam Öğrenci", "Güncel durum"),
            ("Faaliyet Kaydı", "Seçilen dönem"),
            ("Faaliyet Yapan Öğrenci", "Seçilen dönem"),
        ]

        self.degerler = []

        for i, (baslik, alt) in enumerate(alanlar):
            kart = QFrame()
            kart.setStyleSheet("""
                QFrame {
                    background: #F8FAFE;
                    border: 1px solid #E4EAF5;
                    border-radius: 8px;
                }
            """)

            lay = QVBoxLayout(kart)
            lay.setContentsMargins(13, 11, 13, 11)
            lay.setSpacing(5)

            lay.addWidget(
                yazi(baslik, 12, "#405976")
            )

            deger = yazi("—", 23, ANA, True)
            lay.addWidget(deger)

            lay.addWidget(
                yazi(alt, 10, "#8191A6")
            )

            grid.addWidget(kart, 0, i)
            self.degerler.append(deger)

    def guncelle(self, toplam, kayit, faaliyet_yapan):
        for etiket, deger in zip(
            self.degerler,
            (toplam, kayit, faaliyet_yapan)
        ):
            etiket.setText(str(deger))
