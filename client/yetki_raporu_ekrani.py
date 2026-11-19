"""TKYS - Yetki Raporu: kullanıcılar, rolleri, son giriş zamanları, kilit/pasiflik durumu ve rol-izin matrisi (güvenlik denetimi)."""

from client.cihaz_rezervasyon_raporu_ekrani import tarih_saat_metni
from client.rapor_excel import TARIH_SAAT_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban

from PySide6.QtWidgets import QComboBox, QLabel


class YetkiRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "yetkiRaporu"
    BASLIK = "Yetki raporu"
    RAPOR_YOLU = "/api/yetki-raporu"
    DOSYA_ONEKI = "yetki_raporu"
    DONEM_VAR = False
    KARTLAR = [
        ("kullanici", "Kullanıcı", RaporSayfasiTaban.NAVY),
        ("kilitli", "Kilitli Hesap", "#BE185D"),
        ("giris_yok", "Hiç Giriş Yapmamış", "#B86B08"),
        ("basarisiz", "Başarısız Giriş (30 gün)", "#64748B"),
    ]
    TABLO_DIZILIMI = [
        [
            ("kullanici", "Kullanıcılar", ["Kullanıcı", "Rol", "Durum", "Son Giriş", "Uyarı"], 3),
            ("rol", "Roller", ["Rol", "Kullanıcı", "İzin"], 2),
        ],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Rol:"))
        self.rol_sec = QComboBox()
        self.rol_sec.addItem("Tüm Roller", None)
        satir.addWidget(self.rol_sec)
        satir.addWidget(QLabel("Durum:"))
        self.durum_sec = QComboBox()
        for ad, kod in (("Tümü", None), ("Aktif", "aktif"), ("Pasif", "pasif")):
            self.durum_sec.addItem(ad, kod)
        satir.addWidget(self.durum_sec)
        self.rol_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self.durum_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self._rol_listesi_dolu = False

    def ek_parametreler(self):
        params = {}
        if self.rol_sec.currentData() is not None:
            params["rol_id"] = int(self.rol_sec.currentData())
        if self.durum_sec.currentData() is not None:
            params["durum"] = self.durum_sec.currentData()
        return params

    def ek_filtre_ozeti(self):
        return [("Rol", self.rol_sec.currentText()), ("Durum", self.durum_sec.currentText())]

    @staticmethod
    def _uyari(k):
        uyarilar = []
        if k["kilitli_mi"]:
            uyarilar.append("Kilitli")
        if k["aktif_mi"] and k["son_giris"] is None:
            uyarilar.append("Hiç giriş yok")
        if k["gecici_parola_mi"]:
            uyarilar.append("Geçici parola")
        return ", ".join(uyarilar) or "—"

    def goster(self, veri):
        if not self._rol_listesi_dolu:
            self.rol_sec.blockSignals(True)
            for rol in veri.get("roller", []):
                self.rol_sec.addItem(str(rol["rol_adi"]), rol["rol_id"])
            self.rol_sec.blockSignals(False)
            self._rol_listesi_dolu = True
        ozet = veri.get("ozet", {})
        self.kart_yaz("kullanici", ozet.get("kullanici_sayisi", 0), f"{ozet.get('aktif_kullanici', 0)} aktif · {ozet.get('pasif_kullanici', 0)} pasif")
        self.kart_yaz("kilitli", ozet.get("kilitli_kullanici", 0), "Şu an geçici olarak kilitli")
        self.kart_yaz("giris_yok", ozet.get("hic_giris_yapmamis", 0), "Aktif ama hiç giriş kaydı yok")
        self.kart_yaz("basarisiz", ozet.get("son_30_gun_basarisiz_giris", 0), f"{ozet.get('rol_sayisi', 0)} rol · {ozet.get('izin_sayisi', 0)} izin tanımlı")
        self.doldur("kullanici", [
            [k["kullanici_adi"], k["rol_adi"], "Aktif" if k["aktif_mi"] else "Pasif", tarih_saat_metni(k["son_giris"]), self._uyari(k)]
            for k in veri.get("kullanicilar", [])
        ])
        self.doldur("rol", [[r["rol_adi"], f"{r['aktif_kullanici_sayisi']} / {r['kullanici_sayisi']}", r["izin_sayisi"]] for r in veri.get("roller", [])])
        self.durum_etiketi.setText("Parola ve parola özeti raporda yer almaz. Kullanıcı sütunu: aktif / toplam. Rol-izin matrisi Excel çıktısındadır.")

    def excel_yaz(self, veri, filtre, dosya_yolu):
        ozet = veri.get("ozet", {})
        matris = veri.get("matris", {"roller": [], "izinler": []})
        roller = matris["roller"]
        excel_olustur(
            dosya_yolu, "YETKİ RAPORU",
            "Bu rapor, sistemdeki kullanıcıları, rollerini ve rollere tanımlı izinleri listeler. Parola ve parola özeti raporda yer almaz.",
            filtre,
            [
                ("Kullanıcı", ozet.get("kullanici_sayisi", 0), "Süzgeçle listelenen kullanıcı sayısı."),
                ("Aktif / pasif", f"{ozet.get('aktif_kullanici', 0)} / {ozet.get('pasif_kullanici', 0)}", "Hesap durumu."),
                ("Kilitli hesap", ozet.get("kilitli_kullanici", 0), "Hatalı giriş nedeniyle şu an geçici olarak kilitli hesaplar."),
                ("Hiç giriş yapmamış", ozet.get("hic_giris_yapmamis", 0), "Aktif ama hiç giriş kaydı olmayan hesaplar."),
                ("Geçici parolalı", ozet.get("gecici_parolali", 0), "İlk girişte parolasını değiştirmesi beklenen hesaplar."),
                ("Başarısız giriş (son 30 gün)", ozet.get("son_30_gun_basarisiz_giris", 0), "Tüm sistemdeki başarısız giriş denemeleri."),
                ("Rol / izin sayısı", f"{ozet.get('rol_sayisi', 0)} / {ozet.get('izin_sayisi', 0)}", "Tanımlı rol ve izin sayısı."),
            ],
            [
                ("Kullanıcılar", [("Kullanıcı Adı", None), ("Rol", None), ("Durum", None), ("Personel Kodu", None), ("Son Giriş", TARIH_SAAT_BICIMI),
                                  ("Hatalı Giriş Sayısı", None), ("Kilitli", None), ("Geçici Parola", None)],
                 [[k["kullanici_adi"], k["rol_adi"], "Aktif" if k["aktif_mi"] else "Pasif", k["personel_kodu"], _tarih_degeri(k["son_giris"]),
                   k["basarisiz_giris_sayisi"], "Evet" if k["kilitli_mi"] else "Hayır", "Evet" if k["gecici_parola_mi"] else "Hayır"]
                  for k in veri.get("kullanicilar", [])],
                 "Her kullanıcının rolü, durumu, son giriş zamanı ve güvenlik göstergeleri."),
                ("Roller", [("Rol", None), ("Kullanıcı", None), ("Aktif Kullanıcı", None), ("İzin Sayısı", None)],
                 [[r["rol_adi"], r["kullanici_sayisi"], r["aktif_kullanici_sayisi"], r["izin_sayisi"]] for r in veri.get("roller", [])],
                 "Her rolün kullanıcı sayısı ve sahip olduğu izin sayısı."),
                ("Rol-İzin Matrisi", [("İzin", None), ("Açıklama", None)] + [(r, None) for r in roller],
                 [[i["izin_adi"], i["aciklama"]] + ["Evet" if i["roller"].get(r) else "—" for r in roller] for i in matris["izinler"]],
                 "Hangi rolün hangi izne sahip olduğu."),
            ],
        )
