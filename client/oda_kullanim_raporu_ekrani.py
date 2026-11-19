"""TKYS - Oda Kullanım Raporu: oda bazlı randevu, cihaz rezervasyonu ve etkinlik saatleri, mesai doluluk oranı, gün dağılımı."""

from client.rapor_excel import TARIH_SAAT_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban, sayi_metni, yuzde_metni

from PySide6.QtWidgets import QComboBox, QLabel


class OdaKullanimRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "odaKullanimRaporu"
    BASLIK = "Oda kullanım raporu"
    RAPOR_YOLU = "/api/oda-kullanim-raporu"
    DOSYA_ONEKI = "oda_kullanim_raporu"
    KARTLAR = [
        ("toplam", "Toplam Kullanım (saat)", RaporSayfasiTaban.NAVY),
        ("randevu", "Randevu Saati", "#16803C"),
        ("diger", "Cihaz Rez. + Etkinlik (saat)", "#285CE6"),
        ("doluluk", "Mesai Doluluk Oranı", "#B86B08"),
    ]
    TABLO_DIZILIMI = [
        [
            ("oda", "Oda Bazlı Kullanım", ["Oda", "Randevu (sa)", "Cihaz Rez. (sa)", "Etkinlik (sa)", "Toplam (sa)", "Doluluk"], 3),
            ("gun", "Haftanın Günlerine Göre", ["Gün", "Kayıt", "Saat"], 2),
        ],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Oda:"))
        self.oda_sec = QComboBox()
        self.oda_sec.addItem("Tüm Odalar", None)
        self.oda_sec.setMinimumWidth(200)
        satir.addWidget(self.oda_sec)
        self.oda_sec.currentIndexChanged.connect(self.suzgec_degisti)
        self._oda_listesi_dolu = False

    def ek_parametreler(self):
        oda_id = self.oda_sec.currentData()
        return {"oda_id": int(oda_id)} if oda_id is not None else {}

    def ek_filtre_ozeti(self):
        return [("Oda", self.oda_sec.currentText())]

    def _oda_listesini_doldur(self, secenekler):
        """Oda listesi ilk yanıttan (tüm aktif odalar) bir kez doldurulur; süzgeç değişince listeyi bozmamak için."""
        if self._oda_listesi_dolu:
            return
        self.oda_sec.blockSignals(True)
        for oda in secenekler:
            self.oda_sec.addItem(str(oda["oda_adi"]), oda["oda_id"])
        self.oda_sec.blockSignals(False)
        self._oda_listesi_dolu = True

    def goster(self, veri):
        self._oda_listesini_doldur(veri.get("oda_secenekleri", []))
        ozet = veri.get("ozet", {})
        varsayim = veri.get("varsayim", {})
        self.kart_yaz("toplam", sayi_metni(ozet.get("toplam_saat", 0)),
                      f"{ozet.get('kullanilan_oda_sayisi', 0)} oda kullanıldı · {ozet.get('kullanilmayan_oda_sayisi', 0)} oda boş kaldı")
        self.kart_yaz("randevu", sayi_metni(ozet.get("randevu_saati", 0)), "İptal edilenler hariç")
        self.kart_yaz("diger", sayi_metni(ozet.get("cihaz_rezervasyon_saati", 0) + ozet.get("etkinlik_saati", 0)),
                      f"Cihaz: {sayi_metni(ozet.get('cihaz_rezervasyon_saati', 0))} · Etkinlik: {sayi_metni(ozet.get('etkinlik_saati', 0))}")
        self.kart_yaz("doluluk", yuzde_metni(ozet.get("mesai_doluluk_orani")),
                      f"Hafta içi {varsayim.get('is_gunu_sayisi', 0)} gün × {varsayim.get('gunluk_mesai_saati', 8)} saat varsayımı")

        self.doldur("oda", [
            [o["oda_adi"] + ("" if o["aktif_mi"] else " (pasif)"), sayi_metni(o["randevu_saati"]), sayi_metni(o["cihaz_rezervasyon_saati"]),
             sayi_metni(o["etkinlik_saati"]), sayi_metni(o["toplam_saat"]), yuzde_metni(o.get("mesai_doluluk_orani"))]
            for o in veri.get("odalar", [])
        ])
        self.doldur("gun", [[g["gun"], g["kayit_sayisi"], sayi_metni(g["saat"])] for g in veri.get("gun_dagilimi", [])])
        donem = dict(self._son_filtre).get("Dönem", "")
        self.durum_etiketi.setText(f"{veri.get('aciklama', '')}  ·  Dönem: {donem}")

    def excel_yaz(self, veri, filtre, dosya_yolu):
        ozet = veri.get("ozet", {})
        varsayim = veri.get("varsayim", {})
        excel_olustur(
            dosya_yolu, "ODA KULLANIM RAPORU",
            "Bu rapor, randevu, cihaz rezervasyonu ve oda etkinliği kayıtlarından oluşturulmuştur. Saatler planlanan süreyi gösterir; "
            "iptal edilen kayıtlar sayılmaz.",
            filtre,
            [
                ("Toplam kullanım (saat)", ozet.get("toplam_saat", 0), "Randevu + cihaz rezervasyonu + etkinlik saatleri toplamı."),
                ("Randevu (saat)", ozet.get("randevu_saati", 0), "İptal edilmeyen randevuların planlanan süresi."),
                ("Cihaz rezervasyonu (saat)", ozet.get("cihaz_rezervasyon_saati", 0), "Odası seçilmiş, iptal edilmeyen rezervasyonlar."),
                ("Etkinlik (saat)", ozet.get("etkinlik_saati", 0), "İptal edilmeyen oda etkinlikleri."),
                ("Kullanılan oda", ozet.get("kullanilan_oda_sayisi", 0), "Dönemde en az bir kaydı olan oda sayısı."),
                ("Hiç kullanılmayan aktif oda", ozet.get("kullanilmayan_oda_sayisi", 0), "Dönemde hiç kaydı olmayan aktif oda sayısı."),
                ("Mesai doluluk oranı", ozet.get("mesai_doluluk_orani"),
                 f"Toplam saat / (hafta içi {varsayim.get('is_gunu_sayisi', 0)} gün × {varsayim.get('gunluk_mesai_saati', 8)} saat × oda sayısı). "
                 "Hafta sonu kullanımı oranı %100'ün üzerine çıkarabilir.", "0.0%"),
            ],
            [
                ("Oda Bazlı", [("Oda", None), ("Durum", None), ("Randevu", None), ("Randevu (saat)", None), ("Cihaz Rez.", None),
                               ("Cihaz Rez. (saat)", None), ("Etkinlik", None), ("Etkinlik (saat)", None), ("Toplam (saat)", None),
                               ("Mesai Doluluk", "0.0%")],
                 [[o["oda_adi"], "Aktif" if o["aktif_mi"] else "Pasif", o["randevu_sayisi"], o["randevu_saati"],
                   o["cihaz_rezervasyon_sayisi"], o["cihaz_rezervasyon_saati"], o["etkinlik_sayisi"], o["etkinlik_saati"],
                   o["toplam_saat"], o.get("mesai_doluluk_orani")] for o in veri.get("odalar", [])],
                 "Her oda için kullanım sayı ve saatleri ile mesai doluluk oranı."),
                ("Gün Dağılımı", [("Gün", None), ("Kayıt", None), ("Saat", None)],
                 [[g["gun"], g["kayit_sayisi"], g["saat"]] for g in veri.get("gun_dagilimi", [])],
                 "Kullanımın haftanın günlerine dağılımı (kayıt başladığı güne yazılır)."),
                ("Kullanım Kayıtları", [("Oda", None), ("Tür", None), ("Başlangıç", TARIH_SAAT_BICIMI), ("Bitiş", TARIH_SAAT_BICIMI),
                                        ("Süre (saat)", None), ("Açıklama", None)],
                 [[k["oda_adi"], k["tur"], _tarih_degeri(k["baslangic_zamani"]), _tarih_degeri(k["bitis_zamani"]), k["sure_saat"],
                   k["aciklama"]] for k in veri.get("kayitlar", [])],
                 "Odayı kullanan tek tek kayıtlar (süre dönem sınırlarına kırpılmıştır; danışan bilgisi yoktur)."),
            ],
        )
