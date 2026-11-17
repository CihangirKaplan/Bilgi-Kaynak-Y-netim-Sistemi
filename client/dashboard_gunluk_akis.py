"""Ana Kontrol Paneli için günlük faaliyet akışı."""

from datetime import datetime

import requests
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QScrollArea,
)

from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    api_hata_mesaji,
)

RENKLER = {
    "randevu": ("#267FC5", "#EDF5FE", "Randevu"),
    "danisma": ("#139B78", "#EAF8F2", "Danışma Masası"),
    "ogrenci": ("#8B64C6", "#F3EEFB", "Öğrenci"),
    "ariza": ("#D65360", "#FFF0F2", "Cihaz Arızası"),
    "bakim": ("#C5892C", "#FFF6E8", "Cihaz Bakımı"),
    "kalibrasyon": ("#8B64C6", "#F3EEFB", "Kalibrasyon"),
}


def yazı(metin, boyut=12, renk="#405976", kalin=False):
    etiket = QLabel(str(metin))
    etiket.setWordWrap(True)
    etiket.setStyleSheet(
        f"font-size: {boyut}px;"
        f"color: {renk};"
        f"font-weight: {800 if kalin else 400};"
        "background: transparent; border: none;"
    )
    return etiket



def tek_satir_baslik(metin):
    baslik = yazı(metin, 16, "#0A1F5C", True)
    baslik.setWordWrap(False)
    baslik.setMinimumWidth(225)
    baslik.setSizePolicy(
        QSizePolicy.MinimumExpanding,
        QSizePolicy.Preferred
    )
    return baslik



class TiklanabilirOlay(QFrame):
    tiklandi = Signal(str)

    def __init__(self, hedef=None):
        super().__init__()
        self.hedef = hedef
        self.setCursor(
            Qt.PointingHandCursor if hedef else Qt.ArrowCursor
        )

    def mouseReleaseEvent(self, olay):
        if (
            self.hedef
            and olay.button() == Qt.LeftButton
            and self.rect().contains(olay.position().toPoint())
        ):
            self.tiklandi.emit(self.hedef)
        super().mouseReleaseEvent(olay)



class OzetTiklamaSatiri(QFrame):
    tiklandi = Signal(str)

    def __init__(self, anahtar, parent=None):
        super().__init__(parent)
        self.anahtar = anahtar
        self.setObjectName("OzetTiklamaSatiri")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame#OzetTiklamaSatiri {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 8px;
            }
            QFrame#OzetTiklamaSatiri:hover {
                background: #E8F1FD;
                border: 1px solid #C9DDF6;
            }
        """)

    def mouseReleaseEvent(self, olay):
        if (
            olay.button() == Qt.LeftButton
            and self.rect().contains(
                olay.position().toPoint()
            )
        ):
            self.tiklandi.emit(self.anahtar)
            olay.accept()
            return
        super().mouseReleaseEvent(olay)


class DashboardGunlukAkis(QFrame):
    """Yönetim yetkisine sahip kullanıcılar için salt okunur bölüm."""

    def __init__(
        self, api_url, token, parent=None,
        sayfa_ac=None, sayfa_izinli_mi=None,
    ):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.sayfa_ac = sayfa_ac
        self.sayfa_izinli_mi = sayfa_izinli_mi
        self.setObjectName("DashboardGunlukAkis")
        self.setStyleSheet("""
            QFrame#DashboardGunlukAkis {
                background: #FFFFFF;
                border: 1px solid #DCE7F5;
                border-radius: 15px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)

        ana = QVBoxLayout(self)
        ana.setContentsMargins(20, 18, 20, 18)
        ana.setSpacing(14)

        baslik_satiri = QHBoxLayout()

        metinler = QVBoxLayout()
        metinler.setSpacing(2)
        metinler.addWidget(
            tek_satir_baslik("Günlük Faaliyet Akışı")
        )

        baslik_satiri.addLayout(metinler)
        baslik_satiri.addStretch()

        self.yenile_btn = QPushButton("Yenile")
        self.yenile_btn.setStyleSheet("""
            QPushButton {
                background: #EAF2FD;
                color: #236AAA;
                border: 1px solid #D1E2F7;
                border-radius: 8px;
                padding: 8px 17px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #DCEBFD;
            }
        """)
        self.yenile_btn.clicked.connect(self.verileri_yukle)
        baslik_satiri.addWidget(self.yenile_btn)
        ana.addLayout(baslik_satiri)

        # Sol: olaylar, sağ: günlük özet
        govde = QHBoxLayout()
        govde.setSpacing(15)

        sol = QFrame()
        sol.setObjectName("GunlukAkisSol")
        sol.setStyleSheet("""
            QFrame#GunlukAkisSol {
                background: #F8FAFE;
                border: 1px solid #E7EDF6;
                border-radius: 11px;
            }
        """)
        sol_lay = QVBoxLayout(sol)
        sol_lay.setContentsMargins(13, 13, 13, 13)
        sol_lay.setSpacing(8)

        self.akis_alan = QScrollArea()
        self.akis_alan.setWidgetResizable(True)
        self.akis_alan.setMinimumHeight(220)
        self.akis_alan.setMaximumHeight(350)
        self.akis_alan.setFrameShape(QFrame.NoFrame)

        self.akis_widget = QWidget()
        self.akis_widget.setStyleSheet(
            "background: transparent;"
        )
        self.akis_lay = QVBoxLayout(self.akis_widget)
        self.akis_lay.setContentsMargins(2, 2, 7, 2)
        self.akis_lay.setSpacing(8)

        self.akis_alan.setWidget(self.akis_widget)
        sol_lay.addWidget(self.akis_alan)
        govde.addWidget(sol, 7)

        sag = QFrame()
        sag.setObjectName("GunlukAkisSag")
        sag.setStyleSheet("""
            QFrame#GunlukAkisSag {
                background: #F8FAFE;
                border: 1px solid #E7EDF6;
                border-radius: 11px;
            }
        """)
        sag_lay = QVBoxLayout(sag)
        sag_lay.setContentsMargins(15, 15, 15, 15)
        sag_lay.setSpacing(13)
        sag_lay.addWidget(
            yazı("Günlük Özet ve Bekleyen İşlemler", 16, "#0A1F5C", True)
        )


        self.sayilar = {}
        self.ozet_satirlari = {}

        ozet_alanlari = [
            ("planlanan_randevu",
             "Bugüne planlanan randevular", "#267FC5"),
            ("baslayan_danisma_gorevi",
             "Bugün başlayan danışma görevleri", "#139B78"),
            ("girilen_ogrenci_faaliyeti",
             "Öğrenci faaliyetleri", "#8B64C6"),
            ("bildirilen_ariza",
             "Arıza bildirimleri", "#D65360"),
            ("planlanan_oda_etkinligi",
             "Oda etkinlikleri", "#C5892C"),
            ("aktif_danisma_gorevi",
             "Aktif danışma görevi", "#139B78"),
            ("tamamlanan_danisma_gorevi",
             "Bugün biten görevler", "#139B78"),
            ("onay_bekleyen_danisma",
             "Toplam onay bekleyen görevler", "#C5892C"),
            ("bugunku_cihaz_rezervasyonu",
             "Bugünkü cihaz rezervasyonları", "#267FC5"),
        ]

        for anahtar, baslik, renk in ozet_alanlari:
            kart = OzetTiklamaSatiri(anahtar)

            satir = QHBoxLayout(kart)
            satir.setContentsMargins(9, 7, 9, 7)
            satir.setSpacing(10)

            ad = yazı(baslik, 12, "#405976")
            ad.setAttribute(
                Qt.WA_TransparentForMouseEvents, True
            )
            satir.addWidget(ad, 1)

            deger = yazı("—", 16, renk, True)
            deger.setAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
            deger.setMinimumWidth(30)
            deger.setAttribute(
                Qt.WA_TransparentForMouseEvents, True
            )
            satir.addWidget(deger)

            kart.tiklandi.connect(self.detay_ac)
            sag_lay.addWidget(kart)

            self.sayilar[anahtar] = deger
            self.ozet_satirlari[anahtar] = kart

        self.ozet_bos_mesaj = yazı(
            "Bu kapsamda gösterilecek kayıt bulunmuyor.",
            12,
            "#8191A6"
        )
        self.ozet_bos_mesaj.setWordWrap(True)
        self.ozet_bos_mesaj.hide()
        sag_lay.addWidget(self.ozet_bos_mesaj)

        # Sağ panel, yalnızca görünür kayıtlar kadar yer kaplar.
        sag.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Maximum
        )
        govde.addWidget(sag, 3, Qt.AlignTop)
        ana.addLayout(govde)

        self.durum = yazı(
            "Günlük faaliyetler henüz yüklenmedi.",
            11, "#8191A6"
        )
        ana.addWidget(self.durum)
        self.bos_mesaj("Veriler yükleniyor...")

    def temizle(self):
        while self.akis_lay.count():
            oge = self.akis_lay.takeAt(0)
            if oge.widget():
                oge.widget().deleteLater()

    def bos_mesaj(self, mesaj):
        self.temizle()
        etiket = yazı(mesaj, 12, "#8091A6")
        etiket.setAlignment(Qt.AlignCenter)
        etiket.setMinimumHeight(130)
        self.akis_lay.addWidget(etiket)
        self.akis_lay.addStretch()

    def olay_ekle(self, olay):
        renk, zemin, kategori = RENKLER.get(
            olay.get("tur"),
            ("#267FC5", "#EDF5FE", "Diğer")
        )

        if olay.get("saat_belirsiz"):
            saat = "Günlük özet"
        else:
            try:
                saat = datetime.fromisoformat(
                    olay["zaman"]
                ).strftime("%H:%M")
            except (TypeError, ValueError, KeyError):
                saat = "—"

        hedefler = {
            "randevu": "Randevu Yönetimi",
            "danisma": "Danışma Masası Yönetimi",
            "ogrenci": "Faaliyet Kayıtları",
            "ariza": "Arıza Kayıtları",
            "bakim": "Bakım Kayıtları",
            "kalibrasyon": "Kalibrasyon",
        }

        hedef = hedefler.get(olay.get("tur"))

        if (
            not self.sayfa_ac
            or not hedef
            or (
                self.sayfa_izinli_mi is not None
                and not self.sayfa_izinli_mi(hedef)
            )
        ):
            hedef = None

        kart = TiklanabilirOlay(hedef)
        if hedef:
            kart.tiklandi.connect(self.sayfa_ac)

        kart.setObjectName("GunlukOlay")
        kart.setStyleSheet("""
            QFrame#GunlukOlay {
                background: #FFFFFF;
                border: 1px solid #E1EAF6;
                border-radius: 9px;
            }
            QFrame#GunlukOlay:hover {
                background: #F0F6FF;
                border: 1px solid #B9D3F6;
            }
        """)
        lay = QHBoxLayout(kart)
        lay.setContentsMargins(11, 8, 11, 8)
        lay.setSpacing(11)

        nokta = yazı("●", 17, renk)
        nokta.setFixedWidth(18)
        lay.addWidget(nokta)

        metinler = QVBoxLayout()
        metinler.setSpacing(4)
        metinler.addWidget(
            yazı(olay.get("baslik", "İşlem"), 13, "#0F2552", True)
        )
        alt_bilgi = olay.get("alt_bilgi") or kategori
        metinler.addWidget(
            yazı(alt_bilgi, 11, "#6B7FA8")
        )
        lay.addLayout(metinler, 1)

        lay.addWidget(
            yazı(saat, 12, "#778BA4", True),
            0, Qt.AlignTop
        )
        self.akis_lay.addWidget(kart)

    def detay_ac(self, anahtar):
        from client.dashboard_gunluk_detay import GunlukDetayPenceresi

        pencere = GunlukDetayPenceresi(
            api_url=self.api_url,
            token=self.token,
            tur=anahtar,
            gun=getattr(self, "rapor_gunu", None),
            parent=self,
        )
        pencere.exec()

    def verileri_goster(self, veri):
        self.rapor_gunu = veri["gun"]
        ozet = veri["ozet"]
        olaylar = veri["olaylar"]

        # TKYS_OZET_SIFIR_GIZLE_V1
        gorunen_sayisi = 0

        for anahtar, etiket in self.sayilar.items():
            adet = int(ozet[anahtar])
            etiket.setText(str(adet))

            gorunsun = adet > 0
            self.ozet_satirlari[anahtar].setVisible(gorunsun)

            if gorunsun:
                gorunen_sayisi += 1

        self.ozet_bos_mesaj.setVisible(
            gorunen_sayisi == 0
        )

        self.temizle()

        if olaylar:
            for olay in olaylar:
                self.olay_ekle(olay)
            self.akis_lay.addStretch()
        else:
            self.bos_mesaj(
                "Bugün için kayıtlı faaliyet bulunmuyor."
            )

        self.akis_alan.verticalScrollBar().setValue(0)

        sinir = " (son 40 kayıt)" if len(olaylar) >= 40 else ""
        self.durum.setText(
            f"{veri['gun']} • {len(olaylar)} olay listelendi"
            f"{sinir}. Bugün kaydedilen işlemler ve "
            "planlanan faaliyetler ayrı gösterilir. "
            "Bekleyen görevler geçmiş günleri de kapsayabilir."
        )

    def verileri_yukle(self):
        self.yenile_btn.setEnabled(False)

        try:
            yanit = oturum_kontrollu_istek(
                "GET",
                f"{self.api_url}/api/yonetim-raporlari/bugun-merkezde",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=15,
            )

            if yanit.status_code != 200:
                self.durum.setText(
                    api_hata_mesaji(yanit=yanit)
                )
                return

            self.verileri_goster(yanit.json())

        except requests.RequestException as hata:
            self.durum.setText(api_hata_mesaji(hata=hata))
        except (KeyError, TypeError, ValueError):
            self.durum.setText(
                "Günlük faaliyet verileri beklenen biçimde değil."
            )
        finally:
            self.yenile_btn.setEnabled(True)
