"""TKYS - Öğrenci Raporu: tür/bölüm dağılımı, aktif/pasif, kayıt saklama süresi (10 yıl) durumu ve öğrenci listesi (telefon yok)."""

from client.rapor_excel import TARIH_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox, QLabel

TURLER = (("Tümü", None), ("Gönüllü Öğrenci", "GONULLU"), ("Danışma Masası Öğrencisi", "DANISMA_MASASI"), ("Asistan Öğrenci", "ASISTAN"))
DURUMLAR = (("Tümü", None), ("Aktif", "aktif"), ("Pasif", "pasif"))


def gun_metni(iso):
    if not iso:
        return "—"
    tarih = QDate.fromString(str(iso)[:10], "yyyy-MM-dd")
    return tarih.toString("dd.MM.yyyy") if tarih.isValid() else str(iso)


class OgrenciRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "ogrenciRaporu"
    BASLIK = "Öğrenci raporu"
    RAPOR_YOLU = "/api/ogrenci-raporu"
    DOSYA_ONEKI = "ogrenci_raporu"
    DONEM_VAR = False
    KARTLAR = [
        ("toplam", "Toplam Öğrenci", RaporSayfasiTaban.NAVY),
        ("yeni", "Yeni Kayıt (30 gün)", "#16803C"),
        ("saklama", "Saklama Süresi Dolmuş", "#BE185D"),
        ("faaliyetsiz", "Faaliyetsiz Aktif Öğrenci", "#B86B08"),
    ]
    TABLO_DIZILIMI = [
        [
            ("tur", "Öğrenci Türüne Göre", ["Tür", "Toplam", "Aktif", "Pasif"], 3),
            ("bolum", "Bölüme Göre", ["Bölüm", "Öğrenci"], 2),
        ],
        [("liste", "Öğrenci Listesi", ["Öğrenci", "Tür", "Durum", "Kayıt Tarihi", "Son Faaliyet", "Saklama Süresi"], 1)],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Tür:"))
        self.tur_sec = QComboBox()
        for ad, kod in TURLER:
            self.tur_sec.addItem(ad, kod)
        self.tur_sec.setMinimumWidth(190)
        satir.addWidget(self.tur_sec)
        satir.addWidget(QLabel("Durum:"))
        self.durum_sec = QComboBox()
        for ad, kod in DURUMLAR:
            self.durum_sec.addItem(ad, kod)
        satir.addWidget(self.durum_sec)
        self.tur_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self.durum_sec.currentIndexChanged.connect(self.suzgec_degisti)

    def ek_parametreler(self):
        params = {}
        if self.tur_sec.currentData() is not None:
            params["tur"] = self.tur_sec.currentData()
        if self.durum_sec.currentData() is not None:
            params["durum"] = self.durum_sec.currentData()
        return params

    def ek_filtre_ozeti(self):
        return [("Öğrenci Türü", self.tur_sec.currentText()), ("Durum", self.durum_sec.currentText())]

    def goster(self, veri):
        ozet = veri.get("ozet", {})
        kural = veri.get("kurallar", {})
        self.kart_yaz("toplam", ozet.get("toplam", 0), f"{ozet.get('aktif', 0)} aktif · {ozet.get('pasif', 0)} pasif")
        self.kart_yaz("yeni", ozet.get("son_30_gun_yeni", 0), "Son 30 günde kaydedilen")
        self.kart_yaz("saklama", ozet.get("saklama_suresi_dolmus", 0),
                      f"{ozet.get('saklama_ertelenen', 0)} ertelendi · {ozet.get('saklama_yaklasan', 0)} yaklaşıyor ({kural.get('saklama_yil', 10)} yıl, Gönüllü)")
        self.kart_yaz("faaliyetsiz", ozet.get("faaliyetsiz_aktif", 0), f"Son {kural.get('faaliyetsiz_gun', 90)} günde faaliyeti yok")
        self.doldur("tur", [[g["etiket"], g["toplam"], g["aktif"], g["pasif"]] for g in veri.get("tur_dagilimi", [])])
        self.doldur("bolum", [[b["bolum"], b["ogrenci"]] for b in veri.get("bolum_dagilimi", [])])
        self.doldur("liste", [
            [o["ad_soyad"], o["tur_etiketi"], "Aktif" if o["aktif_mi"] else "Pasif", gun_metni(o["olusturulma_tarihi"]),
             gun_metni(o["son_faaliyet_tarihi"]), o["saklama_durumu"] or "—"]
            for o in veri.get("ogrenciler", [])
        ])
        self.durum_etiketi.setText("Telefon raporda yer almaz. Saklama süresi yalnızca Gönüllü Öğrenciler için geçerlidir (10 yıl; ertelenebilir).")

    def excel_yaz(self, veri, filtre, dosya_yolu):
        ozet = veri.get("ozet", {})
        ogrenciler = veri.get("ogrenciler", [])
        saklamalilar = [o for o in ogrenciler if o["saklama_durumu"]]
        excel_olustur(
            dosya_yolu, "ÖĞRENCİ RAPORU",
            "Bu rapor, sistemdeki öğrenci kayıtlarının güncel durumunu gösterir. Telefon bilgisi raporda yer almaz. "
            "Kayıt saklama süresi yalnızca Gönüllü Öğrenciler için geçerlidir (10 yıl; ertelenebilir).",
            filtre,
            [
                ("Toplam öğrenci", ozet.get("toplam", 0), "Süzgece uyan öğrenci sayısı."),
                ("Aktif / pasif", f"{ozet.get('aktif', 0)} / {ozet.get('pasif', 0)}", "Hesap durumu."),
                ("Yeni kayıt (son 30 gün)", ozet.get("son_30_gun_yeni", 0), "Son 30 günde kaydedilen öğrenciler."),
                ("Saklama süresi dolmuş", ozet.get("saklama_suresi_dolmus", 0), "Kayıt süresi dolan, ertelenmemiş Gönüllü öğrenciler."),
                ("Saklama süresi ertelenen", ozet.get("saklama_ertelenen", 0), "Süresi dolmuş ama ileri bir tarihe ertelenmiş kayıtlar."),
                ("Saklama süresi yaklaşan", ozet.get("saklama_yaklasan", 0), "Önümüzdeki 12 ay içinde süresi dolacak Gönüllü öğrenciler."),
                ("Faaliyetsiz aktif öğrenci", ozet.get("faaliyetsiz_aktif", 0), "Aktif ama son 90 günde faaliyet kaydı olmayan öğrenciler."),
            ],
            [
                ("Öğrenci Listesi",
                 [("Ad Soyad", None), ("Öğrenci No", None), ("Tür", None), ("Durum", None), ("Bölüm", None), ("Sınıf", None),
                  ("Kayıt Tarihi", TARIH_BICIMI), ("Faaliyet Sayısı", None), ("Toplam Puan", None), ("Son Faaliyet", TARIH_BICIMI),
                  ("Saklama Durumu", None), ("Saklama Bitiş", TARIH_BICIMI), ("Erteleme Tarihi", TARIH_BICIMI)],
                 [[o["ad_soyad"], o["ogrenci_numarasi"], o["tur_etiketi"], "Aktif" if o["aktif_mi"] else "Pasif", o["bolum"], o["sinif"],
                   _tarih_degeri(o["olusturulma_tarihi"]), o["faaliyet_sayisi"], o["toplam_puan"], _tarih_degeri(o["son_faaliyet_tarihi"]),
                   o["saklama_durumu"], _tarih_degeri(o["saklama_bitis"]), _tarih_degeri(o["erteleme_tarihi"])] for o in ogrenciler],
                 "Her öğrencinin türü, durumu, kayıt tarihi, toplam faaliyet/puanı ve saklama süresi durumu."),
                ("Tür Dağılımı", [("Tür", None), ("Toplam", None), ("Aktif", None), ("Pasif", None)],
                 [[g["etiket"], g["toplam"], g["aktif"], g["pasif"]] for g in veri.get("tur_dagilimi", [])],
                 "Öğrenci türüne göre sayılar."),
                ("Bölüm Dağılımı", [("Bölüm", None), ("Öğrenci", None)],
                 [[b["bolum"], b["ogrenci"]] for b in veri.get("bolum_dagilimi", [])], "Bölümü girilmiş öğrencilerin dağılımı."),
                ("Saklama Süresi", [("Ad Soyad", None), ("Öğrenci No", None), ("Kayıt Tarihi", TARIH_BICIMI), ("Saklama Bitiş", TARIH_BICIMI),
                                    ("Durum", None), ("Erteleme Tarihi", TARIH_BICIMI)],
                 [[o["ad_soyad"], o["ogrenci_numarasi"], _tarih_degeri(o["olusturulma_tarihi"]), _tarih_degeri(o["saklama_bitis"]),
                   o["saklama_durumu"], _tarih_degeri(o["erteleme_tarihi"])] for o in saklamalilar],
                 "Süresi dolmuş, ertelenmiş ya da 12 ay içinde dolacak Gönüllü öğrenciler (KVKK takibi)."),
            ],
        )
