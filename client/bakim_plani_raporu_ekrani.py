"""TKYS - Geciken Bakım Planı Raporu: geciken ve yaklaşan bakım/kalibrasyon planları, cihaz ve tür bazlı özet, planı olmayan cihazlar.

Rapor bugünkü durumdur (dönemden bağımsız). Durum kuralı Bakım Planları ekranıyla aynıdır.
"""

import requests
from client.api_yoneticisi import oturum_hatasi_mi, oturum_kontrollu_istek
from client.ogrenci_raporu_ekrani import gun_metni
from client.rapor_excel import TARIH_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur
from client.rapor_sayfasi_taban import RaporSayfasiTaban, yuzde_metni

from PySide6.QtWidgets import QComboBox, QLabel

TURLER = (("Tümü", None), ("Bakım", "bakim"), ("Kalibrasyon", "kalibrasyon"))
DURUMLAR = (("Tümü", None), ("Gecikmiş", "gecikmis"), ("Yaklaşıyor", "yaklasiyor"), ("Planlı", "planli"), ("Pasif", "pasif"))


class BakimPlaniRaporuEkrani(RaporSayfasiTaban):
    NESNE_ADI = "bakimPlaniRaporu"
    BASLIK = "Bakım planı raporu"
    RAPOR_YOLU = "/api/bakim-plani-raporu"
    DOSYA_ONEKI = "geciken_bakim_plani_raporu"
    DONEM_VAR = False
    KARTLAR = [
        ("geciken", "Geciken Plan", "#BE185D"),
        ("yaklasan", "Yaklaşan Plan", "#B86B08"),
        ("ortalama", "Ortalama Gecikme (gün)", RaporSayfasiTaban.NAVY),
        ("planisiz", "Planı Olmayan Cihaz", "#64748B"),
    ]
    TABLO_DIZILIMI = [
        [
            ("geciken", "Geciken Planlar (en çok geciken önce)", ["Cihaz", "Plan", "Planlanan Tarih", "Gecikme (gün)", "Son Yapılan"], 3),
            ("yaklasan", "Yaklaşan Planlar", ["Cihaz", "Plan", "Tarih", "Kalan (gün)"], 2),
        ],
        [
            ("cihaz", "Cihaz Bazlı", ["Cihaz", "Geciken", "Yaklaşan", "Plan"], 2),
            ("tur", "Plan Türüne Göre", ["Tür", "Gecikmiş", "Yaklaşıyor", "Planlı", "Pasif"], 2),
            ("planisiz", "Planı Olmayan Cihazlar", ["Cihaz"], 1),
        ],
    ]

    def ek_suzgecleri_olustur(self, satir):
        satir.addWidget(QLabel("Cihaz:"))
        self.cihaz_sec = QComboBox()
        self.cihaz_sec.addItem("Tüm Cihazlar", None)
        self.cihaz_sec.setMinimumWidth(200)
        satir.addWidget(self.cihaz_sec)
        satir.addWidget(QLabel("Tür:"))
        self.tur_sec = QComboBox()
        for ad, kod in TURLER:
            self.tur_sec.addItem(ad, kod)
        satir.addWidget(self.tur_sec)
        satir.addWidget(QLabel("Durum:"))
        self.durum_sec = QComboBox()
        for ad, kod in DURUMLAR:
            self.durum_sec.addItem(ad, kod)
        satir.addWidget(self.durum_sec)
        for kutu in (self.cihaz_sec, self.tur_sec, self.durum_sec):
            kutu.currentIndexChanged.connect(self.suzgec_degisti)

    def ek_listeleri_yukle(self):
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
        params = {}
        if self.cihaz_sec.currentData() is not None:
            params["cihaz_id"] = int(self.cihaz_sec.currentData())
        if self.tur_sec.currentData() is not None:
            params["tur"] = self.tur_sec.currentData()
        if self.durum_sec.currentData() is not None:
            params["durum"] = self.durum_sec.currentData()
        return params

    def ek_filtre_ozeti(self):
        return [("Cihaz", self.cihaz_sec.currentText()), ("Plan Türü", self.tur_sec.currentText()), ("Durum", self.durum_sec.currentText())]

    @staticmethod
    def _cihaz(p):
        return f"{p['envanter_kodu']} - {p['cihaz_adi']}"

    def goster(self, veri):
        ozet = veri.get("ozet", {})
        self.kart_yaz("geciken", ozet.get("geciken_plan", 0),
                      f"Aktif planların {yuzde_metni(ozet.get('gecikme_orani'))}'i" if ozet.get("gecikme_orani") is not None else "Aktif plan yok")
        self.kart_yaz("yaklasan", ozet.get("yaklasan_plan", 0), "Uyarı süresi içinde")
        ort = ozet.get("ortalama_gecikme_gun")
        self.kart_yaz("ortalama", str(ort).replace(".", ",") if ort is not None else "—",
                      f"En çok geciken: {ozet['en_cok_gecikme_gun']} gün" if ozet.get("en_cok_gecikme_gun") is not None else "Geciken plan yok")
        self.kart_yaz("planisiz", ozet.get("plani_olmayan_cihaz", 0), "Aktif bakım/kalibrasyon planı yok")
        self.doldur("geciken", [[self._cihaz(p), p["gorev_turu"], gun_metni(p["sonraki_gorev_tarihi"]), p["gecikme_gun"], gun_metni(p["son_yapilan"])]
                                for p in veri.get("geciken", [])])
        self.doldur("yaklasan", [[self._cihaz(p), p["gorev_turu"], gun_metni(p["sonraki_gorev_tarihi"]), p["kalan_gun"]] for p in veri.get("yaklasan", [])])
        self.doldur("cihaz", [[c["cihaz"], c["geciken"], c["yaklasan"], c["plan_sayisi"]] for c in veri.get("cihaz_ozeti", [])])
        self.doldur("tur", [[t["tur"], t["gecikmis"], t["yaklasiyor"], t["planli"], t["pasif"]] for t in veri.get("tur_ozeti", [])])
        self.doldur("planisiz", [[f"{c['envanter_kodu']} - {c['cihaz_adi']}"] for c in veri.get("planisiz_cihazlar", [])])
        self.durum_etiketi.setText(
            "Bugünkü durumdur. Gecikmiş: sonraki görev tarihi geçmiş aktif plan; Yaklaşıyor: uyarı süresi içinde (Bakım Planları ekranıyla aynı kural). "
            "Pasif planlar gecikmiş sayılmaz."
        )

    def excel_yaz(self, veri, filtre, dosya_yolu):
        ozet = veri.get("ozet", {})
        plan_kolonlari = [("Cihaz", None), ("Plan", None), ("Tür", None), ("Periyot (gün)", None), ("Planlanan Tarih", TARIH_BICIMI),
                          ("Kalan / Gecikme (gün)", None), ("Durum", None), ("Son Yapılan", TARIH_BICIMI)]

        def plan_satiri(p):
            kalan = -p["gecikme_gun"] if p["durum"] == "Gecikmiş" else p["kalan_gun"]
            return [self._cihaz(p), p["gorev_turu"], p["tur"], p["periyot_gun"], _tarih_degeri(p["sonraki_gorev_tarihi"]), kalan, p["durum"],
                    _tarih_degeri(p["son_yapilan"])]

        excel_olustur(
            dosya_yolu, "GECİKEN BAKIM PLANI RAPORU",
            "Bu rapor, cihazların bakım ve kalibrasyon planlarının bugünkü durumunu gösterir. Durum kuralı Bakım Planları ekranıyla aynıdır: "
            "sonraki görev tarihi geçmiş aktif plan 'Gecikmiş', uyarı süresi içindeki plan 'Yaklaşıyor'. Pasif planlar gecikmiş sayılmaz.",
            filtre,
            [
                ("Aktif plan", ozet.get("aktif_plan", 0), "Süzgece uyan aktif plan sayısı."),
                ("Geciken plan", ozet.get("geciken_plan", 0), "Sonraki görev tarihi geçmiş aktif planlar."),
                ("Gecikme oranı", ozet.get("gecikme_orani"), "Geciken plan / aktif plan.", "0.0%"),
                ("Ortalama gecikme", ozet.get("ortalama_gecikme_gun"), "Geciken planların ortalama gecikmesi."),
                ("En çok gecikme", ozet.get("en_cok_gecikme_gun"), "En uzun süredir geciken planın gecikmesi."),
                ("Yaklaşan plan", ozet.get("yaklasan_plan", 0), "Uyarı süresi içinde, henüz gecikmemiş planlar."),
                ("Planlı / pasif plan", f"{ozet.get('planli_plan', 0)} planlı / {ozet.get('pasif_plan', 0)} pasif", "Zamanı gelmemiş ve pasif planlar."),
                ("Planı olmayan cihaz", ozet.get("plani_olmayan_cihaz", 0), "Aktif bakım/kalibrasyon planı bulunmayan (kullanım dışı olmayan) cihazlar."),
            ],
            [
                ("Geciken Planlar", plan_kolonlari, [plan_satiri(p) for p in veri.get("geciken", [])],
                 "Gecikmiş planlar, en çok geciken önce. 'Kalan / Gecikme' sütununda eksi değer gecikmeyi gösterir."),
                ("Yaklaşan Planlar", plan_kolonlari, [plan_satiri(p) for p in veri.get("yaklasan", [])], "Uyarı süresi içindeki planlar."),
                ("Tüm Planlar", plan_kolonlari, [plan_satiri(p) for p in veri.get("planlar", [])], "Süzgece uyan tüm planlar (planlanan tarihe göre)."),
                ("Cihaz Bazlı", [("Cihaz", None), ("Geciken", None), ("Yaklaşan", None), ("Aktif Plan", None)],
                 [[c["cihaz"], c["geciken"], c["yaklasan"], c["plan_sayisi"]] for c in veri.get("cihaz_ozeti", [])],
                 "Her cihaz için geciken ve yaklaşan plan sayısı."),
                ("Planı Olmayan Cihazlar", [("Envanter Kodu", None), ("Cihaz", None)],
                 [[c["envanter_kodu"], c["cihaz_adi"]] for c in veri.get("planisiz_cihazlar", [])],
                 "Aktif planı olmayan cihazlar (kullanım dışı olanlar hariç)."),
            ],
        )
