"""TKYS - Cihaz Rezervasyon Raporu: cihaz, proje türü ve bölüm bazlı rezervasyon sayısı ve planlanan kullanım saati."""

import requests
from client.api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from client.rapor_excel import TARIH_SAAT_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban, sayi_metni

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import QComboBox, QLabel


def tarih_saat_metni(iso):
    if not iso:
        return "—"
    zaman = QDateTime.fromString(str(iso)[:19], "yyyy-MM-ddTHH:mm:ss")
    return zaman.toString("dd.MM.yyyy HH:mm") if zaman.isValid() else str(iso)


class CihazRezervasyonRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "cihazRezervasyonRaporu"
    BASLIK = "Cihaz rezervasyon raporu"
    RAPOR_YOLU = "/api/cihaz-rezervasyon-raporu"
    DOSYA_ONEKI = "cihaz_rezervasyon_raporu"
    KARTLAR = [
        ("rezervasyon", "Rezervasyon", RaporSayfasiTaban.NAVY),
        ("saat", "Toplam Kullanım (saat)", "#16803C"),
        ("iptal", "İptal Edilen", "#BE185D"),
        ("kullanilmayan", "Hiç Kullanılmayan Cihaz", "#64748B"),
    ]
    TABLO_DIZILIMI = [
        [
            ("cihaz", "Cihaz Bazlı Kullanım", ["Cihaz", "Rezervasyon", "Saat", "İptal", "Son Kullanım"], 3),
            ("proje", "Proje Türüne Göre", ["Proje Türü", "Rezervasyon", "Saat"], 2),
        ],
        [("bolum", "Bölüme Göre", ["Bölüm", "Rezervasyon", "Saat"], 1)],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Cihaz:"))
        self.cihaz_sec = QComboBox()
        self.cihaz_sec.addItem("Tüm Cihazlar", None)
        self.cihaz_sec.setMinimumWidth(220)
        satir.addWidget(self.cihaz_sec)
        self.cihaz_sec.currentIndexChanged.connect(self.suzgec_degisti)

    def ek_listeleri_yukle(self):
        """Cihaz listesini doldurur; hata olursa rapor yine çalışır (yalnızca 'Tüm Cihazlar' kalır)."""
        try:
            yanit = oturum_kontrollu_istek("GET", f"{self.api_url}/api/cihazlar", headers=self._headers(), timeout=15)
            if oturum_hatasi_mi(yanit):
                return
            yanit.raise_for_status()
            self.cihaz_sec.blockSignals(True)
            for cihaz in yanit.json():
                self.cihaz_sec.addItem(f"{cihaz['envanter_kodu']} - {cihaz['cihaz_adi']}", cihaz["cihaz_id"])
            self.cihaz_sec.blockSignals(False)
        except (requests.RequestException, ValueError, KeyError):
            pass

    def ek_parametreler(self):
        cihaz_id = self.cihaz_sec.currentData()
        return {"cihaz_id": int(cihaz_id)} if cihaz_id is not None else {}

    def ek_filtre_ozeti(self):
        return [("Cihaz", self.cihaz_sec.currentText())]

    def goster(self, veri):
        ozet = veri.get("ozet", {})
        self.kart_yaz("rezervasyon", ozet.get("rezervasyon_sayisi", 0),
                      f"Ortalama süre: {sayi_metni(ozet.get('ortalama_sure_saat'))} saat" if ozet.get("ortalama_sure_saat") is not None else "")
        self.kart_yaz("saat", sayi_metni(ozet.get("toplam_saat", 0)), f"{ozet.get('kullanilan_cihaz_sayisi', 0)} cihaz kullanıldı")
        self.kart_yaz("iptal", ozet.get("iptal_edilen_rezervasyon", 0), "Kullanım saatine dahil değil")
        self.kart_yaz("kullanilmayan", ozet.get("kullanilmayan_cihaz_sayisi", 0), "Dönemde hiç rezerve edilmedi")

        self.doldur("cihaz", [
            [f"{c['envanter_kodu']} - {c['cihaz_adi']}", c["rezervasyon_sayisi"], sayi_metni(c["rezervasyon_saati"]),
             c["iptal_edilen_rezervasyon"], tarih_saat_metni(c.get("son_kullanim"))]
            for c in veri.get("cihazlar", [])
        ])
        self.doldur("proje", [[p["ad"], p["rezervasyon_sayisi"], sayi_metni(p["saat"])] for p in veri.get("proje_turleri", [])])
        self.doldur("bolum", [[b["ad"], b["rezervasyon_sayisi"], sayi_metni(b["saat"])] for b in veri.get("bolumler", [])])
        donem = dict(self._son_filtre).get("Dönem", "")
        self.durum_etiketi.setText(f"{veri.get('aciklama', '')}  ·  Dönem: {donem}")

    def excel_yaz(self, veri, filtre, dosya_yolu):
        ozet = veri.get("ozet", {})
        excel_olustur(
            dosya_yolu, "CİHAZ REZERVASYON RAPORU",
            "Bu rapor, cihaz rezervasyon kayıtlarından oluşturulmuştur. Saatler planlanan süreyi gösterir; gerçekleşen kullanım süresi ayrıca ölçülmez.",
            filtre,
            [
                ("Rezervasyon sayısı", ozet.get("rezervasyon_sayisi", 0), "Dönemle kesişen, iptal edilmeyen rezervasyonlar."),
                ("Toplam kullanım", ozet.get("toplam_saat", 0), "Dönem sınırlarına kırpılmış planlanan süre toplamı."),
                ("Ortalama süre", ozet.get("ortalama_sure_saat"), "Rezervasyon başına ortalama planlanan süre."),
                ("İptal edilen rezervasyon", ozet.get("iptal_edilen_rezervasyon", 0), "Dönemde başlayacak iken iptal edilenler; saate dahil değil."),
                ("Kullanılan cihaz", ozet.get("kullanilan_cihaz_sayisi", 0), "Dönemde en az bir rezervasyonu olan cihaz sayısı."),
                ("Hiç kullanılmayan cihaz", ozet.get("kullanilmayan_cihaz_sayisi", 0), "Dönemde hiç rezerve edilmeyen cihaz sayısı."),
            ],
            [
                ("Cihaz Bazlı", [("Envanter Kodu", None), ("Cihaz", None), ("Rezervasyon", None), ("Kullanım (saat)", None),
                                 ("İptal Edilen", None), ("Son Kullanım", TARIH_SAAT_BICIMI)],
                 [[c["envanter_kodu"], c["cihaz_adi"], c["rezervasyon_sayisi"], c["rezervasyon_saati"], c["iptal_edilen_rezervasyon"],
                   _tarih_degeri(c.get("son_kullanim"))] for c in veri.get("cihazlar", [])],
                 "Her cihaz için rezervasyon sayısı ve planlanan kullanım saati (hiç kullanılmayanlar sonda)."),
                ("Proje Türü", [("Proje Türü", None), ("Rezervasyon", None), ("Kullanım (saat)", None)],
                 [[p["ad"], p["rezervasyon_sayisi"], p["saat"]] for p in veri.get("proje_turleri", [])],
                 "Rezervasyonların proje türüne göre dağılımı."),
                ("Bölüm", [("Bölüm", None), ("Rezervasyon", None), ("Kullanım (saat)", None)],
                 [[b["ad"], b["rezervasyon_sayisi"], b["saat"]] for b in veri.get("bolumler", [])],
                 "Rezervasyonların bölüme göre dağılımı."),
                ("Rezervasyon Detayı", [("ID", None), ("Envanter Kodu", None), ("Cihaz", None), ("Bölüm", None), ("Oda", None),
                                        ("Rezervasyonu Yapan", None), ("Başlangıç", TARIH_SAAT_BICIMI), ("Bitiş", TARIH_SAAT_BICIMI),
                                        ("Süre (saat)", None), ("Proje Türü", None), ("Proje / Açıklama", None), ("Durum", None)],
                 [[r["rezervasyon_id"], r["envanter_kodu"], r["cihaz_adi"], r["bolum"], r["oda"], r["yapan"],
                   _tarih_degeri(r["baslangic_zamani"]), _tarih_degeri(r["bitis_zamani"]), r["sure_saat"], r["proje_turu"],
                   r["proje_adi"], r["durum"]] for r in veri.get("rezervasyonlar", [])],
                 "Tek tek rezervasyonlar (iptaller 'Durum' sütunuyla ayrılır; süre kaydın tamamıdır)."),
            ],
        )
