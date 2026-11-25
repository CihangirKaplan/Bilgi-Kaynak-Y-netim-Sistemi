from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QSizePolicy
)

from client.sayfa_tema import golge
from client.yonetim_grafik_turleri import RENKLER
from client.yonetim_rapor_hesaplari import ROZET_RENKLERI, degisim, rozet_turu

# Sayılar metin rengindedir; dönemi, yanındaki renkli nokta söyler (grafikteki gibi: seçilen mavi, önceki turuncu).
ANA = "#0F2552"
ONCEKI = "#52627A"
SECILEN_NOKTA, ONCEKI_NOKTA = RENKLER


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
                border: none;
                border-radius: 16px;
            }
        """)
        golge(self)

        self.duzen = QVBoxLayout(self)
        self.duzen.setContentsMargins(20, 16, 20, 16)
        self.duzen.setSpacing(8)

        self.duzen.addWidget(
            yazi(baslik, 16, "#0A1F5C", True)
        )
        self.duzen.addWidget(
            yazi(aciklama, 12, "#6B7FA8")
        )


class OperasyonelOzet(OzetPanel):
    """Altı işlem türünün bu dönem / önceki dönem sayıları ve değişimi: tek, sade bir liste (kartlar yerine)."""

    ADLAR = ["Randevu", "Bakım", "Kalibrasyon", "Arıza", "Cihaz Rezervasyonu", "Oda Etkinliği"]
    YONLER = [0, 0, 0, -1, 0, 0]            # arızada artış kötüdür; diğerlerinde yalnızca değişim gösterilir

    def __init__(self):
        super().__init__(
            "Operasyonel Faaliyetler",
            "İşlem sayıları · önceki dönemle karşılaştırma · iptal edilenler hariç"
        )

        self.donem_tarihleri = yazi(
            "Tarih aralıkları yükleniyor...",
            11, "#6B7FA8"
        )
        self.donem_tarihleri.hide()          # aynı bilgi sayfanın süzgeç kartında yazılıdır; burada tekrarlanmaz
        self.duzen.addWidget(self.donem_tarihleri)

        izgara = QGridLayout()
        izgara.setHorizontalSpacing(14)
        izgara.setVerticalSpacing(0)
        izgara.setColumnStretch(0, 1)
        self.duzen.addLayout(izgara)

        basliklar = (
            ("", Qt.AlignLeft),
            (f"<span style='color:{SECILEN_NOKTA}'>●</span>&nbsp;BU DÖNEM", Qt.AlignRight),
            (f"<span style='color:{ONCEKI_NOKTA}'>●</span>&nbsp;ÖNCEKİ", Qt.AlignRight),
            ("DEĞİŞİM", Qt.AlignLeft),
        )
        for sutun, (metin, hiza) in enumerate(basliklar):
            etiket = yazi(metin, 10, "#6B7FA8", True)
            etiket.setAlignment(hiza | Qt.AlignVCenter)
            izgara.addWidget(etiket, 0, sutun)

        self.degerler = []
        self.rozetler = []

        for sira, ad in enumerate(self.ADLAR, start=1):
            cizgi = QFrame()
            cizgi.setFixedHeight(1)
            cizgi.setStyleSheet("background: #EEF2FA; border: none;")
            izgara.addWidget(cizgi, 2 * sira - 1, 0, 1, 4)

            satir_adi = yazi(ad, 13, "#0F2552", True)
            bu = yazi("0", 18, ANA, True)
            gecmis = yazi("0", 14, ONCEKI)
            bu.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            gecmis.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rozet = QLabel("")
            rozet.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

            for sutun, oge in enumerate((satir_adi, bu, gecmis)):
                oge.setMinimumHeight(38)
                izgara.addWidget(oge, 2 * sira, sutun)
            izgara.addWidget(rozet, 2 * sira, 3, Qt.AlignLeft | Qt.AlignVCenter)
            self.degerler.append((bu, gecmis))
            self.rozetler.append(rozet)

        self.duzen.addStretch(1)            # satır sayısı sabit; kartı yandaki grafiğin yüksekliğine uzatırken boşluk altta toplanır

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
        for (bu, gecmis), rozet, yon, a, b in zip(
            self.degerler, self.rozetler, self.YONLER, secilen, onceki
        ):
            bu.setText(str(a))
            gecmis.setText(str(b))
            ok, metin = degisim(a, b)
            if ok is None and metin == "—":
                rozet.setText("—")
                rozet.setStyleSheet("color: #A3B1CE; font-size: 11px; background: transparent; border: none;")
                continue
            renk, zemin = ROZET_RENKLERI[rozet_turu(ok, yon)]
            rozet.setText(f"{ok} {metin}" if ok else metin)
            rozet.setStyleSheet(
                f"color: {renk}; background: {zemin}; border-radius: 9px; padding: 2px 8px;"
                "font-size: 11px; font-weight: 700;"
            )


class OgrenciFaaliyetOzeti(OzetPanel):
    def __init__(self):
        super().__init__(
            "Öğrenci Faaliyet Özeti",
            "Öğrenci mevcudu güncel, faaliyetler seçilen döneme aittir"
        )

        liste = QVBoxLayout()
        liste.setSpacing(10)
        self.duzen.addLayout(liste, 1)

        alanlar = [
            ("Toplam Öğrenci", "Güncel durum"),
            ("Faaliyet Kaydı", "Seçilen dönem"),
            ("Faaliyet Yapan Öğrenci", "Seçilen dönem"),
        ]

        self.degerler = []

        for baslik, alt in alanlar:
            kart = QFrame()
            kart.setStyleSheet("""
                QFrame {
                    background: #F4F7FD;
                    border: none;
                    border-radius: 12px;
                }
            """)

            satir = QHBoxLayout(kart)
            satir.setContentsMargins(16, 12, 18, 12)
            satir.setSpacing(12)

            metinler = QVBoxLayout()
            metinler.setSpacing(2)
            metinler.addWidget(yazi(baslik, 13, "#0F2552", True))
            metinler.addWidget(yazi(alt, 11, "#8191A6"))
            satir.addLayout(metinler, 1)

            deger = yazi("—", 28, ANA, True)
            deger.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            satir.addWidget(deger)

            liste.addWidget(kart, 1)
            self.degerler.append(deger)

    def guncelle(self, toplam, kayit, faaliyet_yapan):
        for etiket, deger in zip(
            self.degerler,
            (toplam, kayit, faaliyet_yapan)
        ):
            etiket.setText(str(deger))
