"""TKYS - Faaliyet Raporu: dönemdeki faaliyet kayıtlarının tür/birim/öğrenci türü dağılımı ve puanlar."""

from client.rapor_excel import TARIH_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban, sayi_metni

from PySide6.QtWidgets import QComboBox, QLabel


class FaaliyetRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "faaliyetRaporu"
    BASLIK = "Faaliyet raporu"
    RAPOR_YOLU = "/api/faaliyet-raporu"
    DOSYA_ONEKI = "faaliyet_raporu"
    KARTLAR = [
        ("kayit", "Faaliyet Kaydı", RaporSayfasiTaban.NAVY),
        ("puan", "Toplam Puan", "#16803C"),
        ("ogrenci", "Faaliyet Yapan Öğrenci", "#285CE6"),
    ]
    TABLO_DIZILIMI = [
        [
            ("faaliyet", "Faaliyet Türüne Göre", ["Faaliyet", "Kayıt", "Miktar", "Puan"], 3),
            ("birim", "Birime Göre", ["Birim", "Kayıt", "Miktar"], 2),
        ],
        [
            ("tur", "Öğrenci Türüne Göre", ["Öğrenci Türü", "Öğrenci", "Kayıt", "Puan"], 1),
        ],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Faaliyet:"))
        self.faaliyet_sec = QComboBox()
        self.faaliyet_sec.addItem("Tüm Faaliyetler", None)
        self.faaliyet_sec.setMinimumWidth(190)
        satir.addWidget(self.faaliyet_sec)
        self.faaliyet_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self._faaliyet_listesi_dolu = False

    def ek_parametreler(self):
        params = {}
        if self.faaliyet_sec.currentData() is not None:
            params["faaliyet_id"] = int(self.faaliyet_sec.currentData())
        return params

    def ek_filtre_ozeti(self):
        return [("Faaliyet", self.faaliyet_sec.currentText())]

    def goster(self, veri):
        if not self._faaliyet_listesi_dolu:
            self.faaliyet_sec.blockSignals(True)
            for f in veri.get("faaliyet_secenekleri", []):
                self.faaliyet_sec.addItem(str(f["faaliyet_adi"]), f["faaliyet_id"])
            self.faaliyet_sec.blockSignals(False)
            self._faaliyet_listesi_dolu = True
        ozet = veri.get("ozet", {})
        self.kart_yaz("kayit", ozet.get("kayit_sayisi", 0), f"Toplam miktar: {ozet.get('faaliyet_miktari', 0)}")
        self.kart_yaz("puan", sayi_metni(ozet.get("toplam_puan", 0)), "Adet × kayıt puanı")
        ort = ozet.get("ortalama_puan_kayit")
        self.kart_yaz("ogrenci", ozet.get("faaliyet_yapan_ogrenci", 0), f"Kayıt başına ort. {sayi_metni(ort)} puan" if ort is not None else "")
        self.doldur("faaliyet", [[f["faaliyet"], f["kayit_sayisi"], f["miktar"], sayi_metni(f["puan"])] for f in veri.get("faaliyetler", [])])
        self.doldur("birim", [[b["birim"], b["kayit_sayisi"], b["miktar"]] for b in veri.get("birimler", [])])
        self.doldur("tur", [[t["etiket"], t["ogrenci_sayisi"], t["kayit_sayisi"], sayi_metni(t["puan"])] for t in veri.get("ogrenci_turleri", [])])
        donem = dict(self._son_filtre).get("Dönem", "")
        self.durum_etiketi.setText(f"Puan = adet × kaydın girildiği andaki faaliyet puanı (Puan Raporu ile aynı).  ·  Dönem: {donem}")

    def excel_yaz(self, veri, filtre, dosya_yolu):
        ozet = veri.get("ozet", {})
        excel_olustur(
            dosya_yolu, "FAALİYET RAPORU",
            "Bu rapor, öğrencilerin seçilen dönemde (faaliyet tarihi) girilen faaliyet kayıtlarından oluşturulmuştur. "
            "Puan = adet × kaydın girildiği andaki faaliyet puanı (Puan Raporu ile aynıdır).",
            filtre,
            [
                ("Faaliyet kaydı", ozet.get("kayit_sayisi", 0), "Süzgece uyan faaliyet kaydı sayısı."),
                ("Faaliyet miktarı", ozet.get("faaliyet_miktari", 0), "Kayıtlardaki adetlerin toplamı."),
                ("Toplam puan", ozet.get("toplam_puan", 0), "Süzgece uyan kayıtların puanlarının toplamı."),
                ("Faaliyet yapan öğrenci", ozet.get("faaliyet_yapan_ogrenci", 0), "Dönemde en az bir kaydı olan öğrenci sayısı."),
                ("Kayıt başına ortalama puan", ozet.get("ortalama_puan_kayit"), "Toplam puan / kayıt sayısı."),
            ],
            [
                ("Faaliyet Türü", [("Faaliyet", None), ("Kayıt", None), ("Miktar", None), ("Puan", None)],
                 [[f["faaliyet"], f["kayit_sayisi"], f["miktar"], f["puan"]] for f in veri.get("faaliyetler", [])],
                 "Faaliyet türüne göre kayıt, miktar ve puan."),
                ("Birim", [("Birim", None), ("Kayıt", None), ("Miktar", None)],
                 [[b["birim"], b["kayit_sayisi"], b["miktar"]] for b in veri.get("birimler", [])], "Faaliyet birimine göre dağılım."),
                ("Öğrenci Türü", [("Öğrenci Türü", None), ("Öğrenci", None), ("Kayıt", None), ("Puan", None)],
                 [[t["etiket"], t["ogrenci_sayisi"], t["kayit_sayisi"], t["puan"]] for t in veri.get("ogrenci_turleri", [])],
                 "Öğrenci türüne göre dağılım."),
                ("Faaliyet Detayı", [("Kayıt ID", None), ("Öğrenci", None), ("Öğrenci No", None), ("Öğrenci Türü", None), ("Faaliyet", None), ("Birim", None),
                                     ("Adet", None), ("Birim Puan", None), ("Toplam Puan", None), ("Tarih", TARIH_BICIMI)],
                 [[k["takip_id"], k["ogrenci"], k["ogrenci_numarasi"], k["tur"], k["faaliyet"], k["birim"], k["adet"], k["birim_puan"],
                   k["toplam_puan"], _tarih_degeri(k["tarih"])] for k in veri.get("kayitlar", [])],
                 "Tek tek faaliyet kayıtları."),
            ],
        )
