"""TKYS - Faaliyet Raporu: dönemdeki faaliyet kayıtlarının tür/birim/öğrenci türü dağılımı, puanlar ve onay durumu."""

from client.rapor_excel import TARIH_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban, sayi_metni

from PySide6.QtWidgets import QComboBox, QLabel

ONAY_DURUMLARI = (("Tümü", None), ("Onaylı", "onayli"), ("Onay bekleyen", "bekleyen"))


class FaaliyetRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "faaliyetRaporu"
    BASLIK = "Faaliyet raporu"
    RAPOR_YOLU = "/api/faaliyet-raporu"
    DOSYA_ONEKI = "faaliyet_raporu"
    KARTLAR = [
        ("kayit", "Faaliyet Kaydı", RaporSayfasiTaban.NAVY),
        ("puan", "Toplam Puan", "#16803C"),
        ("bekleyen", "Onay Bekleyen Kayıt", "#B86B08"),
        ("ogrenci", "Faaliyet Yapan Öğrenci", "#285CE6"),
    ]
    TABLO_DIZILIMI = [
        [
            ("faaliyet", "Faaliyet Türüne Göre", ["Faaliyet", "Kayıt", "Miktar", "Puan", "Onay Bekleyen"], 3),
            ("birim", "Birime Göre", ["Birim", "Kayıt", "Miktar"], 2),
        ],
        [
            ("tur", "Öğrenci Türüne Göre", ["Öğrenci Türü", "Öğrenci", "Kayıt", "Puan"], 2),
            ("bekleyen", "Onay Bekleyen Kayıtlar (en eski önce)", ["Öğrenci", "Faaliyet", "Tarih", "Bekleme (gün)"], 3),
        ],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Faaliyet:"))
        self.faaliyet_sec = QComboBox()
        self.faaliyet_sec.addItem("Tüm Faaliyetler", None)
        self.faaliyet_sec.setMinimumWidth(190)
        satir.addWidget(self.faaliyet_sec)
        satir.addWidget(QLabel("Onay:"))
        self.onay_sec = QComboBox()
        for ad, kod in ONAY_DURUMLARI:
            self.onay_sec.addItem(ad, kod)
        satir.addWidget(self.onay_sec)
        self.faaliyet_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self.onay_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self._faaliyet_listesi_dolu = False

    def ek_parametreler(self):
        params = {}
        if self.faaliyet_sec.currentData() is not None:
            params["faaliyet_id"] = int(self.faaliyet_sec.currentData())
        if self.onay_sec.currentData() is not None:
            params["onay"] = self.onay_sec.currentData()
        return params

    def ek_filtre_ozeti(self):
        return [("Faaliyet", self.faaliyet_sec.currentText()), ("Onay Durumu", self.onay_sec.currentText())]

    def goster(self, veri):
        if not self._faaliyet_listesi_dolu:
            self.faaliyet_sec.blockSignals(True)
            for f in veri.get("faaliyet_secenekleri", []):
                self.faaliyet_sec.addItem(str(f["faaliyet_adi"]), f["faaliyet_id"])
            self.faaliyet_sec.blockSignals(False)
            self._faaliyet_listesi_dolu = True
        ozet = veri.get("ozet", {})
        self.kart_yaz("kayit", ozet.get("kayit_sayisi", 0), f"Toplam miktar: {ozet.get('faaliyet_miktari', 0)}")
        self.kart_yaz("puan", sayi_metni(ozet.get("toplam_puan", 0)), f"Onaylı: {sayi_metni(ozet.get('onayli_puan', 0))} · Bekleyen: {sayi_metni(ozet.get('onay_bekleyen_puan', 0))}")
        eski = ozet.get("en_eski_bekleyen_gun")
        self.kart_yaz("bekleyen", ozet.get("onay_bekleyen_kayit", 0), f"En eski {eski} gündür bekliyor" if eski is not None else "Bekleyen kayıt yok")
        ort = ozet.get("ortalama_puan_kayit")
        self.kart_yaz("ogrenci", ozet.get("faaliyet_yapan_ogrenci", 0), f"Kayıt başına ort. {sayi_metni(ort)} puan" if ort is not None else "")
        self.doldur("faaliyet", [[f["faaliyet"], f["kayit_sayisi"], f["miktar"], sayi_metni(f["puan"]), f["onay_bekleyen"]] for f in veri.get("faaliyetler", [])])
        self.doldur("birim", [[b["birim"], b["kayit_sayisi"], b["miktar"]] for b in veri.get("birimler", [])])
        self.doldur("tur", [[t["etiket"], t["ogrenci_sayisi"], t["kayit_sayisi"], sayi_metni(t["puan"])] for t in veri.get("ogrenci_turleri", [])])
        self.doldur("bekleyen", [
            [b["ogrenci"], b["faaliyet"], ".".join(reversed(b["tarih"].split("-"))), b["bekleme_gun"]] for b in veri.get("onay_bekleyenler", [])
        ])
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
                ("Toplam puan", ozet.get("toplam_puan", 0), "Onaylı ve onay bekleyen kayıtların puanları dahil."),
                ("Onaylı puan", ozet.get("onayli_puan", 0), "Yalnızca onaylanan kayıtların puanı."),
                ("Onay bekleyen kayıt / puan", f"{ozet.get('onay_bekleyen_kayit', 0)} / {ozet.get('onay_bekleyen_puan', 0)}", "Henüz onaylanmamış kayıtlar."),
                ("En eski bekleyen (gün)", ozet.get("en_eski_bekleyen_gun"), "Onay bekleyen en eski kaydın yaşı."),
                ("Faaliyet yapan öğrenci", ozet.get("faaliyet_yapan_ogrenci", 0), "Dönemde en az bir kaydı olan öğrenci sayısı."),
                ("Kayıt başına ortalama puan", ozet.get("ortalama_puan_kayit"), "Toplam puan / kayıt sayısı."),
            ],
            [
                ("Faaliyet Türü", [("Faaliyet", None), ("Kayıt", None), ("Miktar", None), ("Puan", None), ("Onay Bekleyen", None)],
                 [[f["faaliyet"], f["kayit_sayisi"], f["miktar"], f["puan"], f["onay_bekleyen"]] for f in veri.get("faaliyetler", [])],
                 "Faaliyet türüne göre kayıt, miktar ve puan."),
                ("Birim", [("Birim", None), ("Kayıt", None), ("Miktar", None)],
                 [[b["birim"], b["kayit_sayisi"], b["miktar"]] for b in veri.get("birimler", [])], "Faaliyet birimine göre dağılım."),
                ("Öğrenci Türü", [("Öğrenci Türü", None), ("Öğrenci", None), ("Kayıt", None), ("Puan", None)],
                 [[t["etiket"], t["ogrenci_sayisi"], t["kayit_sayisi"], t["puan"]] for t in veri.get("ogrenci_turleri", [])],
                 "Öğrenci türüne göre dağılım."),
                ("Onay Bekleyenler", [("Öğrenci", None), ("Faaliyet", None), ("Tarih", TARIH_BICIMI), ("Bekleme (gün)", None), ("Adet", None), ("Puan", None)],
                 [[b["ogrenci"], b["faaliyet"], _tarih_degeri(b["tarih"]), b["bekleme_gun"], b["adet"], b["puan"]] for b in veri.get("onay_bekleyenler", [])],
                 "Onay bekleyen en eski kayıtlar (ilk 20)."),
                ("Faaliyet Detayı", [("Kayıt ID", None), ("Öğrenci", None), ("Öğrenci No", None), ("Öğrenci Türü", None), ("Faaliyet", None), ("Birim", None),
                                     ("Adet", None), ("Birim Puan", None), ("Toplam Puan", None), ("Tarih", TARIH_BICIMI), ("Durum", None)],
                 [[k["takip_id"], k["ogrenci"], k["ogrenci_numarasi"], k["tur"], k["faaliyet"], k["birim"], k["adet"], k["birim_puan"],
                   k["toplam_puan"], _tarih_degeri(k["tarih"]), k["durum"]] for k in veri.get("kayitlar", [])],
                 "Tek tek faaliyet kayıtları."),
            ],
        )
