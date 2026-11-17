"""TKYS Yönetim Raporları - bütünleşik raporlama paneli."""

import requests

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QDateEdit, QFileDialog, QMessageBox, QScrollArea,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy,
)

from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    api_hata_mesaji,
)
from client.yonetim_genel_bakis import KAYNAKLAR
from client.yonetim_bugun_merkezde import BugunMerkezdeWidget
from client.yonetim_raporlari_pdf import pdf_olustur


RAPOR_TURLERI = (
    "Genel Bakış", "Randevular", "Cihazlar",
    "Öğrenciler", "Proje / Deney",
)


def metin(deger):
    return "—" if deger is None else str(deger)


class YonetimRaporlariEkrani(QWidget):

    def __init__(self, api_url, token, parent=None):
        super().__init__(parent)
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.veriler = None
        self.yuklenen_donem = None
        self.arayuzu_olustur()

    def arayuzu_olustur(self):
        from client.yonetim_proje_grafigi import YonetimProjeGrafigi
        from client.yonetim_ogrenci_puan_grafigi import (
            YonetimOgrenciPuanGrafigi
        )
        from client.yonetim_randevu_grafigi import (
            YonetimRandevuGrafigi
        )
        from client.yonetim_karsilastirma_grafigi import (
            YonetimKarsilastirmaGrafigi
        )
        self.setObjectName("YonetimRaporPaneli")
        self.setStyleSheet("""
            QWidget#YonetimRaporPaneli {
                background: #EAF0FA;
            }
            QFrame#YonetimAnaPanel {
                background: white;
                border: none;
                border-radius: 17px;
            }
            QFrame#YonetimKpiKarti {
                background: #FFFFFF;
                border: 1px solid #DCE6F3;
                border-radius: 10px;
            }
            QFrame#YonetimKpiKarti QLabel {
                border: none;
                background: transparent;
            }
            QComboBox, QDateEdit {
                background: white;
                border: 1px solid #CBDCF0;
                border-radius: 6px;
                padding: 6px 9px;
                color: #243653;
                min-height: 17px;
            }
            QPushButton#YonetimYenile {
                background: #E7F0FB;
                color: #123E72;
                border: 1px solid #CBDEF4;
                border-radius: 7px;
                padding: 9px 12px;
                font-weight: bold;
            }
            QPushButton#YonetimPdf {
                background: #087C54;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 9px 15px;
                font-weight: bold;
            }
            QTableWidget {
                background: white;
                color: #243653;
                gridline-color: #E3EAF5;
                border: 1px solid #DCE6F3;
                border-radius: 8px;
            }
            QTableWidget::item {
                padding: 5px 8px;
            }
            QHeaderView::section {
                background: #E5EFFD;
                color: #193657;
                border: none;
                border-right: 1px solid #D3E1F2;
                padding: 8px 5px;
                font-weight: bold;
            }
        """)

        dis = QVBoxLayout(self)
        dis.setContentsMargins(12, 10, 12, 10)

        kaydir = QScrollArea()
        kaydir.setWidgetResizable(True)
        kaydir.setFrameShape(QFrame.NoFrame)
        kaydir.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        dis.addWidget(kaydir)

        govde = QWidget()
        govde.setObjectName("YonetimRaporGovdesi")
        govde.setStyleSheet("""
            QWidget#YonetimRaporGovdesi {
                background: transparent;
            }
        """)
        govde_lay = QVBoxLayout(govde)
        govde_lay.setContentsMargins(5, 5, 5, 5)

        panel = QFrame()
        panel.setObjectName("YonetimAnaPanel")
        panel.setStyleSheet("""
            QFrame#YonetimAnaPanel {
                background-color: #FFFFFF;
                border: none;
                border-radius: 17px;
            }
        """)
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(26, 23, 26, 23)
        panel_lay.setSpacing(15)

        self.filtreleri_olustur(panel_lay)

        self.bugun_panel = BugunMerkezdeWidget()
        panel_lay.addWidget(self.bugun_panel)

        self.analiz_alani = QWidget()
        self.analiz_layout = QVBoxLayout(self.analiz_alani)
        self.analiz_layout.setContentsMargins(0, 0, 0, 0)
        self.analiz_layout.setSpacing(15)

        self.kartlari_olustur(self.analiz_layout)

        self.karsilastirma_grafigi = YonetimKarsilastirmaGrafigi(
            baslik_metni="Operasyonel Faaliyetler",
            aciklama_metni="İşlem sayıları · Seçilen ve önceki dönem"
        )
        self.analiz_layout.addWidget(
            self.karsilastirma_grafigi
        )

        self.ogrenci_donem_grafigi = YonetimKarsilastirmaGrafigi(
            baslik_metni="Öğrenci Faaliyet Puanları",
            aciklama_metni=(
                "Toplam puan · Onaysız kayıtlar dahil"
            )
        )
        self.analiz_layout.addWidget(
            self.ogrenci_donem_grafigi
        )

        from client.yonetim_genel_bakis_ozet_widget import (
            OperasyonelOzet, OgrenciFaaliyetOzeti
        )

        self.operasyon_ozeti = OperasyonelOzet()
        self.ogrenci_ozeti = OgrenciFaaliyetOzeti()

        self.analiz_layout.insertWidget(
            1, self.operasyon_ozeti
        )
        self.analiz_layout.insertWidget(
            2, self.ogrenci_ozeti
        )

        self.randevu_grafigi = YonetimRandevuGrafigi()
        self.analiz_layout.addWidget(self.randevu_grafigi)

        self.cihaz_grafigi = YonetimKarsilastirmaGrafigi()
        self.analiz_layout.addWidget(self.cihaz_grafigi)

        self.ogrenci_puan_grafigi = YonetimOgrenciPuanGrafigi()
        self.analiz_layout.addWidget(self.ogrenci_puan_grafigi)

        self.proje_grafigi = YonetimProjeGrafigi()
        self.analiz_layout.addWidget(self.proje_grafigi)

        self.tablolari_olustur(self.analiz_layout)
        panel_lay.addWidget(self.analiz_alani)

        self.durum = QLabel(
            "Rapor verilerini görmek için Raporu Yenile'ye basın."
        )
        self.durum.setWordWrap(True)
        self.durum.setStyleSheet(
            "color: #697993; font-size: 11px;"
            "background: transparent; border: none;"
        )
        panel_lay.addWidget(self.durum)

        govde_lay.addWidget(panel)
        kaydir.setWidget(govde)

        self.rapor_turu.setCurrentText("Genel Bakış")
        self.gorunumu_guncelle()



    def filtreleri_olustur(self, panel_lay):
        filtre = QHBoxLayout()
        filtre.setSpacing(7)

        def kucuk_etiket(yazi):
            lbl = QLabel(yazi)
            lbl.setStyleSheet(
                "color: #344963; font-size: 11px;"
                "background: transparent; border: none;"
            )
            return lbl

        self.donem_etiketi = kucuk_etiket("Dönem")
        filtre.addWidget(self.donem_etiketi)

        self.donem = QComboBox()
        self.donem.addItems([
            "Bugün", "Bu Hafta", "Bu Ay",
            "Geçen Ay", "Tarih Aralığı"
        ])
        self.donem.setCurrentText("Bu Ay")
        self.donem.setFixedWidth(120)
        filtre.addWidget(self.donem)

        filtre.addWidget(kucuk_etiket("Rapor"))

        self.rapor_turu = QComboBox()
        self.rapor_turu.addItems(RAPOR_TURLERI)
        self.rapor_turu.setFixedWidth(145)
        filtre.addWidget(self.rapor_turu)

        self.baslangic = QDateEdit()
        self.bitis = QDateEdit()

        for alan in (self.baslangic, self.bitis):
            alan.setCalendarPopup(True)
            alan.setDisplayFormat("dd.MM.yyyy")
            alan.setDate(QDate.currentDate())
            alan.setFixedWidth(112)
            alan.setEnabled(False)

        self.baslangic_etiketi = kucuk_etiket("Başlangıç")
        filtre.addWidget(self.baslangic_etiketi)
        filtre.addWidget(self.baslangic)
        self.bitis_etiketi = kucuk_etiket("Bitiş")
        filtre.addWidget(self.bitis_etiketi)
        filtre.addWidget(self.bitis)

        filtre.addStretch(1)

        self.yenile_btn = QPushButton("Yenile")
        self.yenile_btn.setObjectName("YonetimYenile")
        self.yenile_btn.setFixedWidth(78)
        filtre.addWidget(self.yenile_btn)

        self.pdf_btn = QPushButton("PDF Kaydet")
        self.pdf_btn.setObjectName("YonetimPdf")
        self.pdf_btn.setFixedWidth(105)
        filtre.addWidget(self.pdf_btn)
        self.pdf_btn.hide()  # PDF özelliği şimdilik gizli

        panel_lay.addLayout(filtre)

        # Seçilen hazır dönemin gerçek tarihlerini de göster.
        self.donem.currentTextChanged.connect(
            self.tarih_alanlarini_guncelle
        )
        self.rapor_turu.currentTextChanged.connect(
            self.gorunumu_guncelle
        )
        self.yenile_btn.clicked.connect(self.raporu_yukle)
        self.pdf_btn.clicked.connect(self.pdf_kaydet)

        self.tarih_alanlarini_guncelle(
            self.donem.currentText()
        )

    def kartlari_olustur(self, panel_lay):
        satir = QHBoxLayout()
        satir.setSpacing(12)
        self.kartlar = []

        for _ in range(4):
            kart = QFrame()
            kart.setObjectName("YonetimKpiKarti")
            kl = QVBoxLayout(kart)
            kl.setContentsMargins(16, 12, 16, 12)
            kl.setSpacing(5)

            baslik = QLabel("—")
            baslik.setStyleSheet(
                "color: #697993; font-size: 12px;"
            )

            deger = QLabel("—")
            deger.setStyleSheet(
                "color: #203B61; font-size: 25px;"
                "font-weight: bold;"
            )

            alt = QLabel("")
            alt.setWordWrap(True)
            alt.setStyleSheet(
                "color: #8A98B0; font-size: 11px;"
            )

            kl.addWidget(baslik)
            kl.addWidget(deger)
            kl.addWidget(alt)

            satir.addWidget(kart, 1)
            self.kartlar.append((baslik, deger, alt))

        panel_lay.addLayout(satir)

    def tablo_olustur(self, yukseklik):
        bolum = QWidget()
        lay = QVBoxLayout(bolum)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)

        baslik = QLabel("—")
        baslik.setStyleSheet(
            "color: #16294B; font-size: 13px;"
            "font-weight: bold;"
        )
        lay.addWidget(baslik)

        tablo = QTableWidget()
        tablo.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                color: #243653;
                border: 1px solid #DCE6F3;
                border-radius: 8px;
                gridline-color: #E3EAF5;
            }
            QHeaderView::section {
                background-color: #E5EFFD;
                color: #193657;
                border: none;
                border-right: 1px solid #D3E1F2;
                padding: 7px;
                font-weight: bold;
            }
        """)
        tablo.setMinimumHeight(yukseklik)
        tablo.setMaximumHeight(yukseklik)
        tablo.verticalHeader().setVisible(False)
        tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tablo.setSelectionMode(QTableWidget.NoSelection)
        lay.addWidget(tablo)

        return bolum, baslik, tablo

    def tablolari_olustur(self, panel_lay):
        self.tablolar = []

        ust = QHBoxLayout()
        ust.setSpacing(14)

        for i in range(2):
            bolum, baslik, tablo = self.tablo_olustur(200)
            ust.addWidget(bolum, 3 if i == 0 else 2)
            self.tablolar.append((baslik, tablo))

        panel_lay.addLayout(ust)

        alt = QHBoxLayout()
        alt.setSpacing(14)

        for _ in range(3):
            bolum, baslik, tablo = self.tablo_olustur(180)
            alt.addWidget(bolum, 1)
            self.tablolar.append((baslik, tablo))

        panel_lay.addLayout(alt)

    def tarih_alanlarini_guncelle(self, secim):
        ozel = secim == "Tarih Aralığı"
        self.baslangic.setEnabled(ozel)
        self.bitis.setEnabled(ozel)

        if not ozel:
            ilk, son = self.secili_tarihler()
            self.baslangic.setDate(ilk)
            self.bitis.setDate(son)

    def secili_tarihler(self):
        bugun = QDate.currentDate()
        secim = self.donem.currentText()

        if secim == "Bugün":
            return bugun, bugun
        if secim == "Bu Hafta":
            return bugun.addDays(1 - bugun.dayOfWeek()), bugun
        if secim == "Bu Ay":
            return QDate(bugun.year(), bugun.month(), 1), bugun
        if secim == "Geçen Ay":
            son = QDate(
                bugun.year(), bugun.month(), 1
            ).addDays(-1)
            return QDate(son.year(), son.month(), 1), son

        return self.baslangic.date(), self.bitis.date()

    def tarih_parametreleri(self):
        ilk, son = self.secili_tarihler()

        if ilk > son or ilk.daysTo(son) >= 366:
            raise ValueError(
                "Geçerli ve en fazla 366 günlük bir tarih aralığı seçin."
            )

        return {
            "baslangic": ilk.toString("yyyy-MM-dd"),
            "bitis": son.toString("yyyy-MM-dd"),
        }

    def verileri_getir(self, params):
        sonuc = {}

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
                raise RuntimeError(
                    f"{ad.title()} raporu: "
                    + api_hata_mesaji(yanit=yanit)
                )

            sonuc[ad] = yanit.json()

        return sonuc

    def raporu_yukle(self):
        if self.rapor_turu.currentText() == "Bugün Merkezde":
            self.yenile_btn.setEnabled(False)
            try:
                self.bugun_panel.yukle(self.api_url, self.token)
            finally:
                self.yenile_btn.setEnabled(True)
            return

        try:
            params = self.tarih_parametreleri()
        except ValueError as hata:
            self.durum.setText(str(hata))
            return

        self.yenile_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)
        self.veriler = None
        self.yuklenen_donem = None
        self.gorunumu_guncelle()

        try:
            veriler = self.verileri_getir(params)
            self.verileri_goster(veriler)
            self.yuklenen_donem = params.copy()
            onceki = veriler["randevu"]["onceki_donem"]

            self.durum.setText(
                "Seçilen dönem: "
                f"{params['baslangic']} – {params['bitis']}   |   "
                "Önceki dönem: "
                f"{onceki['baslangic']} – {onceki['bitis']}"
            )
        except (requests.RequestException, RuntimeError) as hata:
            if isinstance(hata, requests.RequestException):
                self.durum.setText(api_hata_mesaji(hata=hata))
            else:
                self.durum.setText(str(hata))
        except (KeyError, ValueError, TypeError):
            self.durum.setText(
                "Rapor verileri beklenen biçimde alınamadı."
            )
        finally:
            self.yenile_btn.setEnabled(True)
            self.pdf_btn.setEnabled(True)

    def tabloyu_doldur(self, tablo, baslik, sutunlar, satirlar):
        baslik_lbl, widget = tablo
        baslik_lbl.setText(baslik)
        widget.clear()
        widget.setColumnCount(len(sutunlar))
        widget.setHorizontalHeaderLabels(sutunlar)
        widget.setRowCount(len(satirlar))

        for i, satir in enumerate(satirlar):
            for j, deger in enumerate(satir):
                oge = QTableWidgetItem(metin(deger))
                widget.setItem(i, j, oge)

        widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

    def verileri_goster(self, veriler):
        self.veriler = veriler
        self.gorunumu_guncelle()

    def gorunumu_guncelle(self, *_):
        gunluk = (
            self.rapor_turu.currentText() == "Bugün Merkezde"
        )

        self.bugun_panel.setVisible(gunluk)
        self.analiz_alani.setVisible(not gunluk)
        self.durum.setVisible(not gunluk)

        self.donem.setEnabled(not gunluk)
        self.baslangic.setEnabled(
            not gunluk
            and self.donem.currentText() == "Tarih Aralığı"
        )
        self.bitis.setEnabled(
            not gunluk
            and self.donem.currentText() == "Tarih Aralığı"
        )
        self.pdf_btn.setEnabled(not gunluk)

        for kontrol in (
            self.donem_etiketi,
            self.donem,
            self.baslangic_etiketi,
            self.baslangic,
            self.bitis_etiketi,
            self.bitis,
        ):
            kontrol.setVisible(not gunluk)

        if gunluk:
            return

        genel_bakis = (
            self.rapor_turu.currentText() == "Genel Bakış"
        )
        self.operasyon_ozeti.setVisible(genel_bakis)
        self.ogrenci_ozeti.setVisible(genel_bakis)

        self.karsilastirma_grafigi.setVisible(False)

        self.ogrenci_donem_grafigi.setVisible(False)

        self.randevu_grafigi.setVisible(
            self.rapor_turu.currentText() == "Randevular"
        )

        self.cihaz_grafigi.setVisible(
            self.rapor_turu.currentText() == "Cihazlar"
        )

        self.ogrenci_puan_grafigi.setVisible(
            self.rapor_turu.currentText() == "Öğrenciler"
        )

        self.proje_grafigi.setVisible(
            self.rapor_turu.currentText() == "Proje / Deney"
        )

        if self.veriler is None:
            for baslik, deger, alt in self.kartlar:
                baslik.setText("—")
                deger.setText("—")
                alt.setText("")

            for tablo in self.tablolar:
                self.tabloyu_doldur(
                    tablo, "Rapor henüz yüklenmedi",
                    ["Bilgi"], []
                )
            return

        r = self.veriler["randevu"]
        c = self.veriler["cihaz"]
        o = self.veriler["ogrenci"]
        p = self.veriler["proje"]

        ro, co, oo, po = (
            r["ozet"], c["ozet"], o["ozet"], p["ozet"]
        )
        rr, cr, ore, pr = (
            r["onceki_ozet"], c["onceki_ozet"],
            o["onceki_ozet"], p["onceki_ozet"]
        )

        tur = self.rapor_turu.currentText()

        if tur == "Genel Bakış":
            self.operasyon_ozeti.tarihleri_guncelle(
                r["donem"],
                r["onceki_donem"],
            )

            self.operasyon_ozeti.guncelle(
                [
                    ro["toplam"],
                    co["bakim"],
                    co["kalibrasyon"],
                    co["ariza"],
                    co["rezervasyon"],
                    po["etkinlik_toplam"],
                ],
                [
                    rr["toplam"],
                    cr["bakim"],
                    cr["kalibrasyon"],
                    cr["ariza"],
                    cr["rezervasyon"],
                    pr["etkinlik_toplam"],
                ],
            )

            self.ogrenci_ozeti.guncelle(
                o["guncel_ogrenci"]["toplam"],
                oo["kayit_sayisi"],
                oo["faaliyet_yapan_ogrenci"],
            )

            self.karsilastirma_grafigi.guncelle(
                [
                    "Randevu", "Bakım", "Kalibrasyon",
                    "Arıza", "Cihaz rezervasyonu",
                    "Oda etkinliği",
                ],
                [
                    ro["toplam"], co["bakim"],
                    co["kalibrasyon"], co["ariza"],
                    co["rezervasyon"], po["etkinlik_toplam"],
                ],
                [
                    rr["toplam"], cr["bakim"],
                    cr["kalibrasyon"], cr["ariza"],
                    cr["rezervasyon"], pr["etkinlik_toplam"],
                ],
            )

            self.ogrenci_donem_grafigi.guncelle(
                ["Faaliyet puanı"],
                [oo["toplam_puan"]],
                [ore["toplam_puan"]],
            )
            kartlar = [
                ("Toplam Randevu", ro["toplam"], "Seçilen dönem"),
                ("Aktif Öğrenci", o["guncel_ogrenci"]["aktif"],
                 "Güncel durum"),
                ("Faaliyet Puanı", oo["toplam_puan"],
                 f"{oo['kayit_sayisi']} faaliyet kaydı"),
                ("Kalibrasyon Kaydı", co["kalibrasyon"],
                 "Seçilen dönem"),
            ]
            tablolar = [
                ("Randevu Durumu", ["Durum", "Seçilen Dönem", "Önceki Dönem"],
                 [
                     ("Toplam", ro["toplam"], rr["toplam"]),
                     ("Planlandı", ro["planlandi"], rr["planlandi"]),
                     ("Tamamlandı", ro["tamamlandi"], rr["tamamlandi"]),
                     ("Gelmedi", ro["gelmedi"], rr["gelmedi"]),
                     ("İptal", ro["iptal_edildi"], rr["iptal_edildi"]),
                 ]),
                ("Öğrenci Faaliyetleri", ["Faaliyet", "Kayıt", "Puan"],
                 [
                     (f["faaliyet"], f["kayit_sayisi"], f["toplam_puan"])
                     for f in o["faaliyet_dagilimi"]
                 ]),
                ("Cihaz İşlemleri", ["İşlem", "Sayı"], [
                    ("Bakım", co["bakim"]),
                    ("Kalibrasyon", co["kalibrasyon"]),
                    ("Arıza", co["ariza"]),
                    ("Rezervasyon", co["rezervasyon"]),
                ]),
                ("Proje / Etkinlik", ["Gösterge", "Sayı"], [
                    ("Rezervasyon", po["rezervasyon_toplam"]),
                    ("Oda etkinliği", po["etkinlik_toplam"]),
                    ("Kayıtlı katılımcı",
                     po["kayitli_katilimci_toplami"]),
                ]),
                ("Dönem Karşılaştırması",
                 ["Gösterge", "Seçilen Dönem", "Önceki Dönem"], [
                     ("Randevu", ro["toplam"], rr["toplam"]),
                     ("Faaliyet puanı",
                      oo["toplam_puan"], ore["toplam_puan"]),
                     ("Kalibrasyon",
                      co["kalibrasyon"], cr["kalibrasyon"]),
                     ("Oda etkinliği",
                      po["etkinlik_toplam"], pr["etkinlik_toplam"]),
                 ]),
            ]

        elif tur == "Randevular":
            self.randevu_grafigi.guncelle(r["gunluk"])
            kartlar = [
                ("Toplam Randevu", ro["toplam"], "Seçilen dönem"),
                ("Planlanan", ro["planlandi"], "Seçilen dönem"),
                ("Tamamlanan", ro["tamamlandi"], "Seçilen dönem"),
                ("İptal Edilen", ro["iptal_edildi"], "Seçilen dönem"),
            ]
            tablolar = [
                ("Randevu Durumları",
                 ["Durum", "Seçilen Dönem", "Önceki Dönem"], [
                     (ad, ro[kod], rr[kod])
                     for ad, kod in [
                         ("Planlandı", "planlandi"),
                         ("Tamamlandı", "tamamlandi"),
                         ("Gelmedi", "gelmedi"),
                         ("İptal", "iptal_edildi"),
                     ]
                 ]),
                ("Günlük Randevu Sayıları", ["Tarih", "Sayı"], [
                    (g["tarih"], g["sayi"]) for g in r["gunluk"]
                ]),
                ("Toplam Karşılaştırma", ["Dönem", "Randevu"], [
                    ("Seçilen", ro["toplam"]),
                    ("Önceki", rr["toplam"]),
                ]),
                ("Durum Özeti", ["Gösterge", "Sayı"], [
                    ("Tamamlanan", ro["tamamlandi"]),
                    ("Gelmedi", ro["gelmedi"]),
                    ("İptal", ro["iptal_edildi"]),
                ]),
                ("Kapsam", ["Bilgi", "Değer"], [
                    ("Başlangıç", r["donem"]["baslangic"]),
                    ("Bitiş", r["donem"]["bitis"]),
                    ("Önceki toplam", rr["toplam"]),
                ]),
            ]

        elif tur == "Cihazlar":
            self.cihaz_grafigi.guncelle(
                ["Bakım", "Kalibrasyon", "Arıza", "Rezervasyon"],
                [
                    co["bakim"],
                    co["kalibrasyon"],
                    co["ariza"],
                    co["rezervasyon"],
                ],
                [
                    cr["bakim"],
                    cr["kalibrasyon"],
                    cr["ariza"],
                    cr["rezervasyon"],
                ],
            )
            kodlar = [
                ("Bakım", "bakim"),
                ("Kalibrasyon", "kalibrasyon"),
                ("Arıza", "ariza"),
                ("Rezervasyon", "rezervasyon"),
            ]
            kartlar = [
                (ad + " Kaydı", co[kod], "Seçilen dönem")
                for ad, kod in kodlar
            ]
            tablolar = [
                ("Cihaz İşlem Karşılaştırması",
                 ["İşlem", "Seçilen Dönem", "Önceki Dönem"], [
                     (ad, co[kod], cr[kod]) for ad, kod in kodlar
                 ]),
                ("Sayısal Değişim", ["İşlem", "Fark"], [
                    (ad, co[kod] - cr[kod]) for ad, kod in kodlar
                ]),
                ("Bu Dönem", ["İşlem", "Kayıt"], [
                    (ad, co[kod]) for ad, kod in kodlar
                ]),
                ("Önceki Dönem", ["İşlem", "Kayıt"], [
                    (ad, cr[kod]) for ad, kod in kodlar
                ]),
                ("Veri Açıklaması", ["Bilgi"], [
                    ("Bunlar işlem kayıtlarının sayılarıdır.",),
                    ("Anlık cihaz durumu değildir.",),
                    ("Gerçek kullanım süresi değildir.",),
                ]),
            ]

        elif tur == "Öğrenciler":
            self.ogrenci_puan_grafigi.guncelle(
                o["faaliyet_dagilimi"]
            )
            kartlar = [
                ("Toplam Öğrenci", o["guncel_ogrenci"]["toplam"],
                 "Güncel durum"),
                ("Aktif Öğrenci", o["guncel_ogrenci"]["aktif"],
                 "Güncel durum"),
                ("Toplam Puan", oo["toplam_puan"],
                 "Onaysız kayıtlar dahil"),
                ("Onaylı Puan", oo["onayli_puan"],
                 "Yalnızca onaylanan kayıtlar"),
            ]
            alanlar = [
                ("Faaliyet kaydı", "kayit_sayisi"),
                ("Faaliyet miktarı", "faaliyet_miktari"),
                ("Toplam puan", "toplam_puan"),
                ("Onaylı puan", "onayli_puan"),
                ("Faaliyet yapan öğrenci",
                 "faaliyet_yapan_ogrenci"),
            ]
            tablolar = [
                ("Faaliyet Türlerine Göre Puanlar",
                 ["Faaliyet", "Kayıt", "Puan"], [
                     (f["faaliyet"], f["kayit_sayisi"], f["toplam_puan"])
                     for f in o["faaliyet_dagilimi"]
                 ]),
                ("Önceki Dönem Karşılaştırması",
                 ["Gösterge", "Seçilen Dönem", "Önceki Dönem"], [
                     (ad, oo[kod], ore[kod]) for ad, kod in alanlar
                 ]),
                ("Faaliyet Özeti", ["Gösterge", "Değer"], [
                    ("Kayıt sayısı", oo["kayit_sayisi"]),
                    ("Faaliyet miktarı", oo["faaliyet_miktari"]),
                    ("Faaliyet yapan", oo["faaliyet_yapan_ogrenci"]),
                ]),
                ("Onay Durumu", ["Gösterge", "Değer"], [
                    ("Onaylanan kayıt", oo["onayli_kayit"]),
                    ("Onaylanan puan", oo["onayli_puan"]),
                ]),
                ("Öğrenci Mevcudu", ["Durum", "Sayı"], [
                    ("Toplam (güncel)",
                     o["guncel_ogrenci"]["toplam"]),
                    ("Aktif (güncel)",
                     o["guncel_ogrenci"]["aktif"]),
                ]),
            ]

        else:
            self.proje_grafigi.guncelle(
                p["proje_turu_dagilimi"]
            )
            kartlar = [
                ("Rezervasyon", po["rezervasyon_toplam"],
                 "Cihaz rezervasyonu"),
                ("İptal Edilmeyen",
                 po["rezervasyon_iptal_edilmemis"],
                 "Cihaz rezervasyonu"),
                ("Oda Etkinliği", po["etkinlik_toplam"],
                 "Kayıtlı etkinlik"),
                ("Katılımcı Toplamı",
                 po["kayitli_katilimci_toplami"],
                 "Girilen sayıların toplamı"),
            ]
            alanlar = [
                ("Rezervasyon", "rezervasyon_toplam"),
                ("İptal edilmeyen",
                 "rezervasyon_iptal_edilmemis"),
                ("Oda etkinliği", "etkinlik_toplam"),
                ("Kayıtlı katılımcı",
                 "kayitli_katilimci_toplami"),
            ]
            tablolar = [
                ("Proje Türleri", ["Tür", "Rezervasyon"], [
                    (f["tur"], f["rezervasyon_sayisi"])
                    for f in p["proje_turu_dagilimi"]
                ]),
                ("Dönem Karşılaştırması",
                 ["Gösterge", "Seçilen Dönem", "Önceki Dönem"], [
                     (ad, po[kod], pr[kod]) for ad, kod in alanlar
                 ]),
                ("Rezervasyon Durumu", ["Durum", "Sayı"], [
                    ("Toplam", po["rezervasyon_toplam"]),
                    ("İptal edilmeyen",
                     po["rezervasyon_iptal_edilmemis"]),
                    ("İptal", po["rezervasyon_iptal"]),
                ]),
                ("Oda Etkinlikleri", ["Gösterge", "Sayı"], [
                    ("Toplam", po["etkinlik_toplam"]),
                    ("İptal edilmeyen",
                     po["etkinlik_iptal_edilmemis"]),
                ]),
                ("Önemli Açıklamalar", ["Bilgi"], [
                    ("Rezervasyon tamamlanmış deney değildir.",),
                    ("Katılımcı toplamı benzersiz kişi sayısı değildir.",),
                ]),
            ]

        for widgetlar, (ad, deger, alt) in zip(
            self.kartlar, kartlar
        ):
            baslik_lbl, deger_lbl, alt_lbl = widgetlar
            baslik_lbl.setText(ad)
            deger_lbl.setText(metin(deger))
            alt_lbl.setText(alt)

        for widgetlar, (ad, sutunlar, satirlar) in zip(
            self.tablolar, tablolar
        ):
            self.tabloyu_doldur(
                widgetlar, ad, sutunlar, satirlar
            )

        if self.yuklenen_donem is not None:
            try:
                secili = self.tarih_parametreleri()
                if secili != self.yuklenen_donem:
                    self.durum.setText(
                        "Tarih filtresi değişti. "
                        "Yeni dönem için Raporu Yenile'ye basın."
                    )
            except ValueError:
                self.durum.setText("Geçersiz tarih aralığı.")

    def pdf_kaydet(self):
        try:
            params = self.tarih_parametreleri()
        except ValueError as hata:
            QMessageBox.warning(self, "Tarih Hatası", str(hata))
            return

        ad = (
            "TKYS_Yonetim_Raporu_"
            + params["baslangic"].replace("-", "")
            + "_"
            + params["bitis"].replace("-", "")
            + ".pdf"
        )
        dosya, _ = QFileDialog.getSaveFileName(
            self, "Yönetim Raporunu Kaydet",
            ad, "PDF Dosyası (*.pdf)"
        )
        if not dosya:
            return
        if not dosya.lower().endswith(".pdf"):
            dosya += ".pdf"

        self.yenile_btn.setEnabled(False)
        self.pdf_btn.setEnabled(False)

        try:
            # PDF her zaman seçilen tarih için güncel API
            # yanıtlarından oluşturulur.
            veriler = self.verileri_getir(params)
            pdf_olustur(
                dosya, params["baslangic"],
                params["bitis"], veriler
            )
            QMessageBox.information(
                self, "PDF Kaydedildi",
                "Rapor kaydedildi:\n" + dosya
            )
        except requests.RequestException as hata:
            QMessageBox.warning(
                self, "Bağlantı Hatası",
                api_hata_mesaji(hata=hata)
            )
        except (RuntimeError, OSError, ValueError, KeyError, TypeError):
            QMessageBox.warning(
                self, "PDF Hatası",
                "PDF oluşturulamadı. Rapor verilerini "
                "ve dosya konumunu kontrol edin."
            )
        finally:
            self.yenile_btn.setEnabled(True)
            self.pdf_btn.setEnabled(True)
