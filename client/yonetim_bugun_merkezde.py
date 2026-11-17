"""TKYS - Bugün Merkezde günlük yönetim paneli."""

from datetime import datetime

import requests
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QGridLayout, QScrollArea,
)

from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    api_hata_mesaji,
)

RENKLER = {
    "mavi": ("#2379C5", "#EFF6FD"),
    "yesil": ("#129A77", "#EDF9F5"),
    "mor": ("#8A62C5", "#F5F0FB"),
    "kirmizi": ("#D94E60", "#FFF1F3"),
    "turuncu": ("#CC872B", "#FFF7EB"),
}

OLAY_TURLERI = {
    "randevu": ("Randevu", "mavi", "●"),
    "danisma": ("Danışma Masası", "yesil", "●"),
    "ogrenci": ("Öğrenci Faaliyeti", "mor", "●"),
    "ariza": ("Cihaz Arızası", "kirmizi", "●"),
    "bakim": ("Cihaz Bakımı", "turuncu", "●"),
    "kalibrasyon": ("Kalibrasyon", "mor", "●"),
}


def yazi(metin, boyut=12, renk="#435C78", kalin=False):
    sonuc = QLabel(str(metin))
    sonuc.setWordWrap(True)
    sonuc.setStyleSheet(
        f"font-size:{boyut}px;color:{renk};"
        f"font-weight:{'700' if kalin else '400'};"
        "background:transparent;border:none;"
    )
    return sonuc


def bolum(baslik):
    govde = QFrame()
    govde.setObjectName("GunlukBolum")
    govde.setStyleSheet("""
        QFrame#GunlukBolum {
            background: white;
            border: 1px solid #DFE8F3;
            border-radius: 13px;
        }
    """)
    lay = QVBoxLayout(govde)
    lay.setContentsMargins(17, 15, 17, 15)
    lay.setSpacing(12)
    lay.addWidget(yazi(baslik, 16, "#183A5E", True))
    return govde, lay


class BugunMerkezdeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BugunMerkezde")
        self.setStyleSheet(
            "QWidget#BugunMerkezde {background:transparent;}"
        )

        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 4, 0, 8)
        ana.setSpacing(17)

        bas = QHBoxLayout()
        bas.addWidget(yazi("Bugün Merkezde", 24, "#153C62", True))
        bas.addStretch()
        self.tarih = yazi("", 12, "#73869E")
        bas.addWidget(self.tarih)
        ana.addLayout(bas)

        ana.addWidget(yazi(
            "Gün içindeki işlemler ve merkezin mevcut durumu",
            12, "#7C8EA5"
        ))

        # Hafif renkli dört üst kart
        self.kart_degerleri = {}
        kart_satiri = QGridLayout()
        kart_satiri.setSpacing(12)

        kartlar = [
            ("randevu", "Bugünkü Randevular", "Bugüne planlanan", "mavi"),
            ("danisma", "Danışma Görevleri", "Bugün başlayan", "yesil"),
            ("faaliyet", "Öğrenci Faaliyetleri", "Bugün kaydedilen", "mor"),
            ("ariza", "Arıza Bildirimleri", "Bugün bildirilen", "kirmizi"),
        ]

        for sira, (kod, baslik, alt, renk_adi) in enumerate(kartlar):
            renk, arka = RENKLER[renk_adi]

            kart = QFrame()
            kart.setObjectName(f"GunlukKart{sira}")
            kart.setStyleSheet(
                f"QFrame#GunlukKart{sira} {{"
                f"background:{arka};border:1px solid #E0E8F3;"
                "border-radius:12px;}"
            )

            kl = QVBoxLayout(kart)
            kl.setContentsMargins(17, 13, 15, 13)
            kl.setSpacing(5)

            ust = QHBoxLayout()
            ust.addWidget(yazi(baslik, 12, "#48617E", True))
            ust.addStretch()
            ust.addWidget(yazi("●", 14, renk))
            kl.addLayout(ust)

            sayi = yazi("—", 29, renk, True)
            kl.addWidget(sayi)
            kl.addWidget(yazi(alt, 11, "#7C8DA2"))

            self.kart_degerleri[kod] = sayi
            kart_satiri.addWidget(kart, 0, sira)

        ana.addLayout(kart_satiri)

        # Günlük faaliyet akışı ana içerik
        orta = QHBoxLayout()
        orta.setSpacing(14)

        akis_kart, akis_lay = bolum("Gün İçinde Neler Oldu?")
        akis_lay.addWidget(yazi(
            "En son gerçekleşen işlemler en üstte görünür.",
            11, "#8292A7"
        ))

        self.akis_kaydir = QScrollArea()
        self.akis_kaydir.setWidgetResizable(True)
        self.akis_kaydir.setFrameShape(QFrame.NoFrame)
        self.akis_kaydir.setMinimumHeight(230)
        self.akis_kaydir.setMaximumHeight(390)
        self.akis_kaydir.setStyleSheet("""
            QScrollArea {
                border:none;
                background:transparent;
            }
        """)

        self.akis_govde = QWidget()
        self.akis_govde.setObjectName("AkisGovdesi")
        self.akis_govde.setStyleSheet(
            "QWidget#AkisGovdesi {background:transparent;}"
        )
        self.akis_lay = QVBoxLayout(self.akis_govde)
        self.akis_lay.setContentsMargins(2, 2, 6, 2)
        self.akis_lay.setSpacing(9)

        self.akis_kaydir.setWidget(self.akis_govde)
        akis_lay.addWidget(self.akis_kaydir)

        self.akis_sayisi = yazi("", 11, "#8292A7")
        akis_lay.addWidget(self.akis_sayisi)
        orta.addWidget(akis_kart, 3)

        # Sağdaki küçük operasyon özetleri
        sag = QVBoxLayout()
        sag.setSpacing(12)

        durum_kart, durum_lay = bolum("Şu Anki Durum")
        self.durum_degerleri = {}

        durumlar = [
            ("Kullanıma hazır cihaz", "Kullanima_Hazir", "yesil"),
            ("Kullanımdaki cihaz", "Kullanimda", "mavi"),
            ("Rezerve cihaz", "Rezerve", "mavi"),
        ]

        for baslik, kod, renk_adi in durumlar:
            renk, _ = RENKLER[renk_adi]
            satir = QHBoxLayout()
            satir.addWidget(yazi("●", 12, renk))
            satir.addWidget(yazi(baslik, 12, "#4F6681"))
            satir.addStretch()

            deger = yazi("—", 14, "#203E60", True)
            satir.addWidget(deger)
            durum_lay.addLayout(satir)
            self.durum_degerleri[kod] = deger

        sag.addWidget(durum_kart)

        uyari_kart, uyari_lay = bolum("Dikkat Gerektirenler")
        self.uyari_lay = uyari_lay
        self.uyari_mesajlari = []
        sag.addWidget(uyari_kart)

        diger_kart, diger_lay = bolum("Bugünün Diğer İşlemleri")
        self.etkinlik_degerleri = {}

        for baslik, kod in [
            ("Oda etkinlikleri", "planlanan_oda_etkinligi"),
            ("Öğrenci faaliyet kayıtları", "girilen_ogrenci_faaliyeti"),
        ]:
            satir = QHBoxLayout()
            satir.addWidget(yazi(baslik, 12, "#4F6681"))
            satir.addStretch()
            deger = yazi("—", 14, "#2379C5", True)
            satir.addWidget(deger)
            diger_lay.addLayout(satir)
            self.etkinlik_degerleri[kod] = deger

        sag.addWidget(diger_kart)
        sag.addStretch()

        sag_widget = QWidget()
        sag_widget.setLayout(sag)
        orta.addWidget(sag_widget, 2)

        ana.addLayout(orta)

        self.durum = yazi(
            "Günlük veriler henüz yüklenmedi.",
            11, "#7D8DA4"
        )
        ana.addWidget(self.durum)

        self.bos_akisi_goster(
            "Bugünkü işlemler yükleniyor..."
        )

    def alanlari_temizle(self, layout):
        while layout.count():
            oge = layout.takeAt(0)
            if oge.widget() is not None:
                oge.widget().deleteLater()
            elif oge.layout() is not None:
                self.alanlari_temizle(oge.layout())

    def bos_akisi_goster(self, mesaj):
        self.alanlari_temizle(self.akis_lay)

        bos = QFrame()
        bos.setObjectName("BosAkis")
        bos.setStyleSheet("""
            QFrame#BosAkis {
                background:#F7FAFE;
                border:1px dashed #D7E3F2;
                border-radius:11px;
            }
        """)
        lay = QVBoxLayout(bos)
        lay.setContentsMargins(20, 32, 20, 32)
        lay.setSpacing(12)

        ikon = yazi("◷", 32, "#94A9C0")
        ikon.setAlignment(Qt.AlignCenter)
        lay.addWidget(ikon)

        bilgi = yazi(mesaj, 12, "#7890A8")
        bilgi.setAlignment(Qt.AlignCenter)
        lay.addWidget(bilgi)

        self.akis_lay.addWidget(bos)
        self.akis_lay.addStretch()

    def olay_karti(self, olay):
        kategori, renk_adi, simge = OLAY_TURLERI.get(
            olay.get("tur"), ("Diğer İşlem", "mavi", "●")
        )
        renk, arka = RENKLER[renk_adi]

        try:
            saat = datetime.fromisoformat(
                olay["zaman"]
            ).strftime("%H:%M")
        except (ValueError, TypeError, KeyError):
            saat = "—"

        govde = QFrame()
        govde.setObjectName("OlayKarti")
        govde.setStyleSheet("""
            QFrame#OlayKarti {
                background:#FAFCFF;
                border:1px solid #E5ECF5;
                border-radius:10px;
            }
        """)

        lay = QHBoxLayout(govde)
        lay.setContentsMargins(12, 11, 12, 11)
        lay.setSpacing(11)

        ikon_kutu = QFrame()
        ikon_kutu.setObjectName("OlayIkonu")
        ikon_kutu.setFixedSize(34, 34)
        ikon_kutu.setStyleSheet(
            f"QFrame#OlayIkonu {{background:{arka};"
            "border:none;border-radius:9px;}"
        )
        ikon_lay = QVBoxLayout(ikon_kutu)
        ikon_lay.setContentsMargins(0, 0, 0, 0)

        ikon = yazi(simge, 18, renk, True)
        ikon.setAlignment(Qt.AlignCenter)
        ikon_lay.addWidget(ikon)
        lay.addWidget(ikon_kutu, 0, Qt.AlignTop)

        metin_lay = QVBoxLayout()
        metin_lay.setSpacing(3)
        metin_lay.addWidget(yazi(
            olay.get("baslik", "İşlem kaydı"),
            12, "#203F60", True
        ))
        metin_lay.addWidget(yazi(kategori, 11, renk))
        lay.addLayout(metin_lay, 1)

        lay.addWidget(
            yazi(saat, 12, "#7C8CA2", True),
            0, Qt.AlignTop
        )
        return govde

    def uyari_ekle(self, mesaj, renk_adi):
        renk, arka = RENKLER[renk_adi]
        kutu = QFrame()
        kutu.setObjectName("UyariKutusu")
        kutu.setStyleSheet(
            f"QFrame#UyariKutusu {{background:{arka};"
            "border:none;border-radius:9px;}"
        )
        lay = QHBoxLayout(kutu)
        lay.setContentsMargins(11, 10, 11, 10)
        lay.setSpacing(9)
        lay.addWidget(yazi("●", 15, renk))
        lay.addWidget(yazi(mesaj, 12, "#354F6B"), 1)

        self.uyari_lay.addWidget(kutu)
        self.uyari_mesajlari.append(kutu)

    def verileri_goster(self, veri):
        ozet = veri["ozet"]
        cihazlar = veri["cihaz_durumlari"]
        olaylar = veri["olaylar"]

        self.tarih.setText(
            datetime.strptime(
                veri["gun"], "%Y-%m-%d"
            ).strftime("%d.%m.%Y")
        )

        kart_esleme = {
            "randevu": "planlanan_randevu",
            "danisma": "baslayan_danisma_gorevi",
            "faaliyet": "girilen_ogrenci_faaliyeti",
            "ariza": "bildirilen_ariza",
        }

        for kart, alan in kart_esleme.items():
            self.kart_degerleri[kart].setText(
                str(ozet[alan])
            )

        for kod, etiket in self.durum_degerleri.items():
            etiket.setText(str(cihazlar.get(kod, 0)))

        for kod, etiket in self.etkinlik_degerleri.items():
            etiket.setText(str(ozet[kod]))

        self.alanlari_temizle(self.akis_lay)

        if olaylar:
            for olay in olaylar:
                self.akis_lay.addWidget(
                    self.olay_karti(olay)
                )
            self.akis_lay.addStretch()
        else:
            self.bos_akisi_goster(
                "Bugün henüz kayıtlı bir işlem bulunmuyor."
            )

        self.akis_kaydir.verticalScrollBar().setValue(0)

        self.akis_sayisi.setText(
            f"Son {len(olaylar)} işlem gösteriliyor."
            if len(olaylar) >= 40
            else f"{len(olaylar)} işlem listelendi."
        )

        for kutu in self.uyari_mesajlari:
            self.uyari_lay.removeWidget(kutu)
            kutu.deleteLater()
        self.uyari_mesajlari.clear()

        uyarilar = [
            ("Arızalı cihaz", "Arizali", "kirmizi"),
            ("Bakımda cihaz", "Bakimda", "turuncu"),
            ("Kalibrasyonda cihaz", "Kalibrasyonda", "mor"),
            ("Kullanım dışı cihaz", "Kullanim_Disi", "kirmizi"),
        ]

        uyari_var = False
        for baslik, kod, renk in uyarilar:
            sayi = int(cihazlar.get(kod, 0))
            if sayi:
                self.uyari_ekle(f"{baslik}: {sayi}", renk)
                uyari_var = True

        if not uyari_var:
            self.uyari_ekle(
                "Cihaz durumlarında kritik bir kayıt görünmüyor.",
                "yesil"
            )

        self.durum.setText(
            "Cihaz bilgileri güncel durumu; "
            "faaliyet akışı bugünkü kayıtlı işlemleri gösterir."
        )

    def yukle(self, api_url, token):
        self.durum.setText("Günlük veriler yenileniyor...")

        try:
            yanit = oturum_kontrollu_istek(
                "GET",
                f"{api_url.rstrip('/')}"
                "/api/yonetim-raporlari/bugun-merkezde",
                headers={
                    "Authorization": f"Bearer {token}",
                },
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
        except (KeyError, ValueError, TypeError):
            self.durum.setText(
                "Günlük veriler beklenen biçimde alınamadı."
            )
