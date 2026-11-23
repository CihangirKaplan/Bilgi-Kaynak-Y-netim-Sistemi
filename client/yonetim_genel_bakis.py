"""TKYS - Yönetim Raporları / Genel Bakış."""

import requests

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea,
)

from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    api_hata_mesaji,
)


KAYNAKLAR = {
    "randevu": "randevu-ozet",
    "cihaz": "cihaz-ozet",
    "ogrenci": "ogrenci-ozet",
    "proje": "proje-etkinlik-ozet",
}


class YonetimGenelBakis(QWidget):

    def __init__(self, api_url, token, tarih_saglayici, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.tarih_saglayici = tarih_saglayici
        self.arayuzu_olustur()

    def etiket(self, metin, boyut=12, renk="#64748B", kalin=False):
        lbl = QLabel(str(metin))
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {renk}; font-size: {boyut}px;"
            f"font-weight: {'700' if kalin else '400'};"
            "border: none; background: transparent;"
        )
        return lbl

    def kart_olustur(self, kod, baslik, aciklama):
        kart = QFrame()
        kart.setObjectName("OzetKarti")
        kart.setMinimumHeight(100)
        kart.setStyleSheet("""
            QFrame#OzetKarti {
                background: #FFFFFF;
                border: 1px solid #DFE7F2;
                border-radius: 13px;
            }
        """)

        icerik = QVBoxLayout(kart)
        icerik.setContentsMargins(19, 16, 19, 15)
        icerik.setSpacing(6)

        baslik_lbl = self.etiket(baslik, 12, "#64748B")
        deger = self.etiket("—", 29, "#193A63", True)
        aciklama_lbl = self.etiket(aciklama, 11, "#8190A5")

        icerik.addWidget(baslik_lbl)
        icerik.addWidget(deger)
        icerik.addWidget(aciklama_lbl)

        self.kartlar[kod] = deger
        self.kart_aciklamalari[kod] = aciklama_lbl

        return kart

    def bolum_olustur(self, baslik, aciklama=""):
        bolum = QFrame()
        bolum.setObjectName("OzetBolumu")
        bolum.setStyleSheet("""
            QFrame#OzetBolumu {
                background: #FFFFFF;
                border: 1px solid #DFE7F2;
                border-radius: 13px;
            }
        """)

        icerik = QVBoxLayout(bolum)
        icerik.setContentsMargins(20, 18, 20, 18)
        icerik.setSpacing(12)

        icerik.addWidget(
            self.etiket(baslik, 15, "#243653", True)
        )

        if aciklama:
            icerik.addWidget(
                self.etiket(aciklama, 11, "#64748B")
            )

        return bolum, icerik

    def bilgi_satiri(self, yerlesim, kod, baslik):
        satir = QHBoxLayout()
        satir.setSpacing(12)

        ad = self.etiket(baslik, 12, "#526780")
        deger = self.etiket("—", 14, "#243653", True)
        deger.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        satir.addWidget(ad, 1)
        satir.addWidget(deger)

        yerlesim.addLayout(satir)
        self.detaylar[kod] = deger

    def arayuzu_olustur(self):
        ana = QVBoxLayout(self)
        ana.setContentsMargins(0, 0, 0, 0)

        kaydir = QScrollArea()
        kaydir.setObjectName("YonetimOzetKaydir")
        kaydir.setWidgetResizable(True)
        kaydir.setFrameShape(QFrame.NoFrame)
        kaydir.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        kaydir.setStyleSheet("""
            QScrollArea#YonetimOzetKaydir {
                background: transparent;
                border: none;
            }
        """)

        govde = QWidget()
        govde.setObjectName("YonetimOzetGovde")
        govde.setStyleSheet("""
            QWidget#YonetimOzetGovde {
                background: #F6F8FC;
            }
        """)

        lay = QVBoxLayout(govde)
        lay.setContentsMargins(20, 20, 20, 28)
        lay.setSpacing(20)

        # Sayfa başlığı
        ust = QHBoxLayout()
        basliklar = QVBoxLayout()
        basliklar.setSpacing(5)

        ana_baslik = self.etiket(
            "Merkez Performans Özeti",
            19, "#243653", True
        )
        ana_baslik.setWordWrap(False)
        basliklar.addWidget(ana_baslik)

        self.bilgi = self.etiket(
            "Seçilen dönemin istatistiklerini "
            "görüntülemek için Raporu Yenile'ye basın.",
            12, "#64748B"
        )

        basliklar.addWidget(self.bilgi)
        ust.addLayout(basliklar)
        ust.addStretch()
        lay.addLayout(ust)

        # Ana performans göstergeleri
        self.kartlar = {}
        self.kart_aciklamalari = {}
        self.detaylar = {}

        kartlar = QGridLayout()
        kartlar.setSpacing(14)

        tanimlar = (
            ("randevu", "Toplam Randevu",
             "Seçilen dönemin randevu sayısı"),
            ("aktif_ogrenci", "Aktif Öğrenci",
             "Güncel öğrenci mevcudu"),
            ("faaliyet_puani", "Faaliyet Puanı",
             "Seçilen dönemdeki toplam puan"),
            ("kalibrasyon", "Kalibrasyon Kaydı",
             "Dönemde kaydedilen işlemler"),
        )

        for i, (kod, baslik, aciklama) in enumerate(tanimlar):
            kartlar.addWidget(
                self.kart_olustur(kod, baslik, aciklama),
                i // 4, i % 4
            )

        lay.addLayout(kartlar)

        # Alt bölümler
        alt = QGridLayout()
        alt.setSpacing(14)

        randevu, randevu_lay = self.bolum_olustur(
            "Randevu Durumu",
            "Seçilen döneme ait randevu kayıtları"
        )
        self.bilgi_satiri(
            randevu_lay, "tamamlandi", "Tamamlanan"
        )
        self.bilgi_satiri(
            randevu_lay, "iptal", "İptal edilen"
        )
        self.bilgi_satiri(
            randevu_lay, "gelmedi", "Gelmedi"
        )
        alt.addWidget(randevu, 0, 0)

        faaliyet, faaliyet_lay = self.bolum_olustur(
            "Öğrenci Faaliyetleri",
            "Seçilen dönemde girilen faaliyet kayıtları"
        )
        self.bilgi_satiri(
            faaliyet_lay, "faaliyet_kaydi", "Faaliyet kaydı"
        )
        self.bilgi_satiri(
            faaliyet_lay, "toplam_puan", "Toplam puan"
        )
        self.bilgi_satiri(
            faaliyet_lay, "faaliyet_ogrencisi",
            "Faaliyet yapan öğrenci"
        )
        alt.addWidget(faaliyet, 0, 1)

        cihaz, cihaz_lay = self.bolum_olustur(
            "Cihaz İşlemleri",
            "İşlem kayıtları, anlık cihaz durumu değildir"
        )
        self.bilgi_satiri(
            cihaz_lay, "ariza", "Arıza bildirimi"
        )
        self.bilgi_satiri(
            cihaz_lay, "bakim", "Bakım kaydı"
        )
        self.bilgi_satiri(
            cihaz_lay, "cihaz_rezervasyonu",
            "Cihaz rezervasyonu"
        )
        alt.addWidget(cihaz, 1, 0)

        etkinlik, etkinlik_lay = self.bolum_olustur(
            "Proje ve Etkinlik Kayıtları",
            "Rezervasyonlar gerçekleşmiş deney sayısı değildir"
        )
        self.bilgi_satiri(
            etkinlik_lay, "etkinlik", "Oda etkinliği"
        )
        self.bilgi_satiri(
            etkinlik_lay, "katilimci",
            "Kayıtlı katılımcı toplamı"
        )
        self.bilgi_satiri(
            etkinlik_lay, "iptalsiz_rezervasyon",
            "İptal edilmeyen rezervasyon"
        )
        alt.addWidget(etkinlik, 1, 1)

        lay.addLayout(alt)

        dipnot = self.etiket(
            "Bilgilendirme: Öğrenci mevcudu günceldir. "
            "Katılımcı toplamı benzersiz kişi sayısı değildir.",
            11, "#64748B"
        )
        lay.addWidget(dipnot)
        lay.addStretch()

        kaydir.setWidget(govde)
        ana.addWidget(kaydir)

    def verileri_goster(self, veriler):
        r = veriler["randevu"]["ozet"]
        c = veriler["cihaz"]["ozet"]
        o = veriler["ogrenci"]
        p = veriler["proje"]["ozet"]

        ana_degerler = {
            "randevu": r["toplam"],
            "aktif_ogrenci": o["guncel_ogrenci"]["aktif"],
            "faaliyet_puani": o["ozet"]["toplam_puan"],
            "kalibrasyon": c["kalibrasyon"],
        }

        for kod, deger in ana_degerler.items():
            self.kartlar[kod].setText(str(deger))

        self.kart_aciklamalari["faaliyet_puani"].setText(
            f"{o['ozet']['kayit_sayisi']} faaliyet kaydı"
        )

        detaylar = {
            "tamamlandi": r["tamamlandi"],
            "iptal": r["iptal_edildi"],
            "gelmedi": r["gelmedi"],
            "faaliyet_kaydi": o["ozet"]["kayit_sayisi"],
            "toplam_puan": o["ozet"]["toplam_puan"],
            "faaliyet_ogrencisi":
                o["ozet"]["faaliyet_yapan_ogrenci"],
            "ariza": c["ariza"],
            "bakim": c["bakim"],
            "cihaz_rezervasyonu": c["rezervasyon"],
            "etkinlik": p["etkinlik_toplam"],
            "katilimci": p["kayitli_katilimci_toplami"],
            "iptalsiz_rezervasyon":
                p["rezervasyon_iptal_edilmemis"],
        }

        for kod, deger in detaylar.items():
            self.detaylar[kod].setText(str(deger))

    def raporu_yukle(self):
        ilk, son = self.tarih_saglayici()

        if ilk > son:
            self.bilgi.setText(
                "Başlangıç tarihi bitiş tarihinden sonra olamaz."
            )
            return

        if ilk.daysTo(son) >= 366:
            self.bilgi.setText(
                "Tarih aralığı en fazla 366 gün olabilir."
            )
            return

        for etiket in list(self.kartlar.values()) + \
                       list(self.detaylar.values()):
            etiket.setText("—")

        params = {
            "baslangic": ilk.toString("yyyy-MM-dd"),
            "bitis": son.toString("yyyy-MM-dd"),
        }

        veriler = {}

        try:
            for ad, yol in KAYNAKLAR.items():
                yanit = oturum_kontrollu_istek(
                    "GET",
                    f"{self.api_url}/api/yonetim-raporlari/{yol}",
                    headers={
                        "Authorization": f"Bearer {self.token}"
                    },
                    params=params,
                    timeout=15,
                )

                if yanit.status_code != 200:
                    self.bilgi.setText(
                        f"{ad.title()} raporu alınamadı: "
                        + api_hata_mesaji(yanit=yanit)
                    )
                    return

                veriler[ad] = yanit.json()

            self.verileri_goster(veriler)

            self.bilgi.setText(
                f"Rapor dönemi: "
                f"{params['baslangic']} – {params['bitis']}"
            )

        except requests.RequestException as hata:
            self.bilgi.setText(api_hata_mesaji(hata=hata))
        except (ValueError, KeyError, TypeError):
            self.bilgi.setText(
                "Yönetim raporları beklenen biçimde alınamadı."
            )
