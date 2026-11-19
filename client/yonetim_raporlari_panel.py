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
from client.rapor_sayfasi_taban import sayi_metni, yuzde_metni
from client.yonetim_bugun_merkezde import BugunMerkezdeWidget
from client.yonetim_raporlari_pdf import pdf_olustur


RAPOR_TURLERI = (
    "Genel Bakış", "Randevular", "Cihazlar",
    "Öğrenciler", "Proje / Deney",
    "Oda Kullanımı", "Cihaz Kullanımı", "Yetkiler",
    "Öğrenci Mevcudu", "Faaliyet Onayları", "Bakım Gecikmeleri",
    "Bugün Merkezde",
)

# Ayrıntılı rapor sayfalarıyla (Oda Kullanım Raporu, Cihaz Rezervasyon Raporu, Yetki Raporu) aynı uç noktalardan beslenir; böylece
# yönetim panelindeki sayılar ayrıntılı sayfalardakiyle birebir aynıdır. Dönemli olanlar dönem parametresi alır.
EK_KAYNAKLAR = {
    "oda": ("oda-kullanim-raporu", True),
    "cihaz_rez": ("cihaz-rezervasyon-raporu", True),
    "yetki": ("yetki-raporu", False),
    "ogrenci_rapor": ("ogrenci-raporu", False),
    "faaliyet_rapor": ("faaliyet-raporu", True),
    "bakim_plani": ("bakim-plani-raporu", False),
}


def oda_kullanim_tablosu(kullanim, en_cok=8):
    """Randevular görünümü: odaların planlanan kullanım saatleri (randevu + cihaz rezervasyonu + etkinlik)."""
    baslik = "Oda Kullanımı (planlanan saat)"
    sutunlar = ["Oda", "Randevu", "Rez./Etkinlik", "Toplam Saat"]
    if kullanim is None:
        return (baslik, ["Bilgi"], [("Kullanım verisi alınamadı.",)])
    satirlar = [
        (
            o["oda_adi"],
            f"{o['randevu_sayisi']} ({o['randevu_saati']:g} sa)",
            f"{o['cihaz_rezervasyon_sayisi'] + o['etkinlik_sayisi']} "
            f"({o['cihaz_rezervasyon_saati'] + o['etkinlik_saati']:g} sa)",
            f"{o['toplam_saat']:g}",
        )
        for o in kullanim["odalar"][:en_cok]
    ]
    return (baslik, sutunlar, satirlar or [("Dönemde oda kullanımı yok.", "", "", "")])


def cihaz_kullanim_tablosu(kullanim, en_cok=8):
    """Cihazlar görünümü: cihazların rezervasyon sayısı ve planlanan kullanım saati (hiç kullanılmayanlar sonda)."""
    baslik = "Cihaz Kullanımı (planlanan saat)"
    sutunlar = ["Cihaz", "Rezervasyon", "Saat", "İptal"]
    if kullanim is None:
        return (baslik, ["Bilgi"], [("Kullanım verisi alınamadı.",)])
    satirlar = [
        (
            f"{c['envanter_kodu']} - {c['cihaz_adi']}",
            c["rezervasyon_sayisi"],
            f"{c['rezervasyon_saati']:g}",
            c["iptal_edilen_rezervasyon"],
        )
        for c in kullanim["cihazlar"][:en_cok]
    ]
    return (baslik, sutunlar, satirlar or [("Kayıtlı cihaz yok.", "", "", "")])


YETKI_YOK = "Bu rapor alınamadı (yetkiniz olmayabilir)."


def _veri_yok_gorunumu():
    kartlar = [("—", "—", "")] * 4
    tablolar = [("Rapor alınamadı", ["Bilgi"], [(YETKI_YOK,)])] + [("", ["Bilgi"], [])] * 4
    return kartlar, tablolar


def oda_gorunumu(veri):
    """'Oda Kullanımı' görünümü: 4 kart + 5 tablo (Oda Kullanım Raporu sayfasıyla aynı veri)."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet, varsayim, odalar = veri["ozet"], veri.get("varsayim", {}), veri["odalar"]
    toplam = ozet["toplam_saat"]
    pay = lambda saat: yuzde_metni(saat / toplam) if toplam else "—"
    kartlar = [
        ("Toplam Kullanım (saat)", sayi_metni(toplam), f"{ozet['kullanilan_oda_sayisi']} oda kullanıldı"),
        ("Randevu Saati", sayi_metni(ozet["randevu_saati"]), "İptal edilenler hariç"),
        ("Cihaz Rez. + Etkinlik (saat)", sayi_metni(ozet["cihaz_rezervasyon_saati"] + ozet["etkinlik_saati"]),
         f"Cihaz: {sayi_metni(ozet['cihaz_rezervasyon_saati'])} · Etkinlik: {sayi_metni(ozet['etkinlik_saati'])}"),
        ("Mesai Doluluk Oranı", yuzde_metni(ozet.get("mesai_doluluk_orani")),
         f"Hafta içi {varsayim.get('is_gunu_sayisi', 0)} gün × {varsayim.get('gunluk_mesai_saati', 8)} saat"),
    ]
    tablolar = [
        ("Oda Bazlı Kullanım", ["Oda", "Randevu (sa)", "Cihaz Rez. (sa)", "Etkinlik (sa)", "Toplam (sa)", "Doluluk"], [
            (o["oda_adi"] + ("" if o["aktif_mi"] else " (pasif)"), sayi_metni(o["randevu_saati"]), sayi_metni(o["cihaz_rezervasyon_saati"]),
             sayi_metni(o["etkinlik_saati"]), sayi_metni(o["toplam_saat"]), yuzde_metni(o.get("mesai_doluluk_orani")))
            for o in odalar[:8]
        ]),
        ("Haftanın Günlerine Göre", ["Gün", "Kayıt", "Saat"], [(g["gun"], g["kayit_sayisi"], sayi_metni(g["saat"])) for g in veri["gun_dagilimi"]]),
        ("Kullanım Türleri", ["Tür", "Saat", "Pay"], [
            ("Randevu", sayi_metni(ozet["randevu_saati"]), pay(ozet["randevu_saati"])),
            ("Cihaz rezervasyonu", sayi_metni(ozet["cihaz_rezervasyon_saati"]), pay(ozet["cihaz_rezervasyon_saati"])),
            ("Oda etkinliği", sayi_metni(ozet["etkinlik_saati"]), pay(ozet["etkinlik_saati"])),
        ]),
        ("Hiç Kullanılmayan Odalar", ["Oda"], [(o["oda_adi"],) for o in odalar if o["aktif_mi"] and o["toplam_saat"] == 0]
         or [("Dönemde boş kalan aktif oda yok.",)]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Saatler planlanan süreyi gösterir (iptaller hariç).",),
            ("Gerçekleşen kullanım süresi ayrıca ölçülmez.",),
            (f"Doluluk: hafta içi günlük {varsayim.get('gunluk_mesai_saati', 8)} saat varsayımıyla.",),
        ]),
    ]
    return kartlar, tablolar


def cihaz_gorunumu(veri):
    """'Cihaz Kullanımı' görünümü: 4 kart + 5 tablo (Cihaz Rezervasyon Raporu sayfasıyla aynı veri)."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet, cihazlar = veri["ozet"], veri["cihazlar"]
    kartlar = [
        ("Rezervasyon", ozet["rezervasyon_sayisi"],
         f"Ortalama süre: {sayi_metni(ozet['ortalama_sure_saat'])} saat" if ozet.get("ortalama_sure_saat") is not None else ""),
        ("Toplam Kullanım (saat)", sayi_metni(ozet["toplam_saat"]), f"{ozet['kullanilan_cihaz_sayisi']} cihaz kullanıldı"),
        ("İptal Edilen", ozet["iptal_edilen_rezervasyon"], "Kullanım saatine dahil değil"),
        ("Hiç Kullanılmayan Cihaz", ozet["kullanilmayan_cihaz_sayisi"], "Dönemde hiç rezerve edilmedi"),
    ]
    tablolar = [
        ("Cihaz Bazlı Kullanım", ["Cihaz", "Rezervasyon", "Saat", "İptal"], [
            (f"{c['envanter_kodu']} - {c['cihaz_adi']}", c["rezervasyon_sayisi"], sayi_metni(c["rezervasyon_saati"]), c["iptal_edilen_rezervasyon"])
            for c in cihazlar[:8]
        ]),
        ("Proje Türüne Göre", ["Proje Türü", "Rezervasyon", "Saat"], [(p["ad"], p["rezervasyon_sayisi"], sayi_metni(p["saat"])) for p in veri["proje_turleri"]]),
        ("Bölüme Göre", ["Bölüm", "Rezervasyon", "Saat"], [(b["ad"], b["rezervasyon_sayisi"], sayi_metni(b["saat"])) for b in veri["bolumler"]]),
        ("Hiç Kullanılmayan Cihazlar", ["Cihaz"], [(f"{c['envanter_kodu']} - {c['cihaz_adi']}",) for c in cihazlar if c["rezervasyon_sayisi"] == 0]
         or [("Dönemde boş kalan cihaz yok.",)]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Saatler planlanan süreyi gösterir (iptaller hariç).",),
            ("Gerçekleşen kullanım süresi ayrıca ölçülmez.",),
            ("Rezervasyon, tamamlanmış deney demek değildir.",),
        ]),
    ]
    return kartlar, tablolar


def yetki_gorunumu(veri):
    """'Yetkiler' görünümü: 4 kart + 5 tablo (Yetki Raporu sayfasıyla aynı veri). Parola ya da parola özeti içermez."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet, kullanicilar = veri["ozet"], veri["kullanicilar"]
    uyarili = []
    for k in kullanicilar:
        uyarilar = [ad for ad, var in (("Kilitli", k["kilitli_mi"]), ("Hiç giriş yok", k["aktif_mi"] and k["son_giris"] is None),
                                       ("Geçici parola", k["gecici_parola_mi"])) if var]
        if uyarilar:
            uyarili.append((k["kullanici_adi"], k["rol_adi"], ", ".join(uyarilar)))
    son_girisler = sorted((k for k in kullanicilar if k["son_giris"]), key=lambda k: k["son_giris"], reverse=True)[:8]
    kartlar = [
        ("Kullanıcı", ozet["kullanici_sayisi"], f"{ozet['aktif_kullanici']} aktif · {ozet['pasif_kullanici']} pasif"),
        ("Kilitli Hesap", ozet["kilitli_kullanici"], "Şu an geçici olarak kilitli"),
        ("Hiç Giriş Yapmamış", ozet["hic_giris_yapmamis"], "Aktif ama hiç giriş kaydı yok"),
        ("Başarısız Giriş (30 gün)", ozet["son_30_gun_basarisiz_giris"], f"{ozet['rol_sayisi']} rol · {ozet['izin_sayisi']} izin tanımlı"),
    ]
    tablolar = [
        ("Roller", ["Rol", "Kullanıcı", "İzin"], [(r["rol_adi"], f"{r['aktif_kullanici_sayisi']} / {r['kullanici_sayisi']}", r["izin_sayisi"]) for r in veri["roller"]]),
        ("Hesap Durumu", ["Gösterge", "Sayı"], [
            ("Aktif", ozet["aktif_kullanici"]), ("Pasif", ozet["pasif_kullanici"]),
            ("Kilitli", ozet["kilitli_kullanici"]), ("Geçici parolalı", ozet["gecici_parolali"]),
        ]),
        ("Uyarılı Hesaplar", ["Kullanıcı", "Rol", "Uyarı"], uyarili[:8] or [("Uyarılı hesap yok.", "", "")]),
        ("Son Girişler", ["Kullanıcı", "Son Giriş"], [(k["kullanici_adi"], k["son_giris"].replace("T", " ")[:16]) for k in son_girisler]
         or [("Giriş kaydı yok.", "")]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Parola ve parola özeti raporda yer almaz.",),
            ("Rol-izin matrisi Yetki Raporu sayfasının Excel çıktısındadır.",),
            ("Yetkiler dönemden bağımsız, güncel durumdur.",),
        ]),
    ]
    return kartlar, tablolar


def ogrenci_mevcut_gorunumu(veri):
    """'Öğrenci Mevcudu' görünümü: 4 kart + 5 tablo (Öğrenci Raporu sayfasıyla aynı veri; telefon yok)."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet, ogrenciler, kural = veri["ozet"], veri["ogrenciler"], veri.get("kurallar", {})
    saklama = [o for o in ogrenciler if o["saklama_durumu"]]
    faaliyetsiz = [o for o in ogrenciler if o["faaliyetsiz_mi"]]
    kartlar = [
        ("Toplam Öğrenci", ozet["toplam"], f"{ozet['aktif']} aktif · {ozet['pasif']} pasif"),
        ("Yeni Kayıt (30 gün)", ozet["son_30_gun_yeni"], "Son 30 günde kaydedilen"),
        ("Saklama Süresi Dolmuş", ozet["saklama_suresi_dolmus"], f"{ozet['saklama_ertelenen']} ertelendi · {ozet['saklama_yaklasan']} yaklaşıyor"),
        ("Faaliyetsiz Aktif Öğrenci", ozet["faaliyetsiz_aktif"], f"Son {kural.get('faaliyetsiz_gun', 90)} günde faaliyeti yok"),
    ]
    tablolar = [
        ("Öğrenci Türüne Göre", ["Tür", "Toplam", "Aktif", "Pasif"], [(g["etiket"], g["toplam"], g["aktif"], g["pasif"]) for g in veri["tur_dagilimi"]]),
        ("Bölüme Göre", ["Bölüm", "Öğrenci"], [(b["bolum"], b["ogrenci"]) for b in veri["bolum_dagilimi"][:8]]),
        ("Saklama Süresi Takibi", ["Öğrenci", "Durum"], [(o["ad_soyad"], o["saklama_durumu"]) for o in saklama[:8]] or [("Takip gerektiren kayıt yok.", "")]),
        ("Faaliyetsiz Aktif Öğrenciler", ["Öğrenci", "Son Faaliyet"],
         [(o["ad_soyad"], (o["son_faaliyet_tarihi"] or "Hiç yok")) for o in faaliyetsiz[:8]] or [("Faaliyetsiz aktif öğrenci yok.", "")]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Telefon raporda yer almaz.",),
            (f"Saklama süresi: Gönüllü öğrenciler, {kural.get('saklama_yil', 10)} yıl (ertelenebilir).",),
            ("Öğrenci mevcudu dönemden bağımsız, güncel durumdur.",),
        ]),
    ]
    return kartlar, tablolar


def faaliyet_onay_gorunumu(veri):
    """'Faaliyet Onayları' görünümü: 4 kart + 5 tablo (Faaliyet Raporu sayfasıyla aynı veri)."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet = veri["ozet"]
    eski = ozet.get("en_eski_bekleyen_gun")
    kartlar = [
        ("Faaliyet Kaydı", ozet["kayit_sayisi"], f"Toplam miktar: {ozet['faaliyet_miktari']}"),
        ("Toplam Puan", sayi_metni(ozet["toplam_puan"]), f"Onaylı: {sayi_metni(ozet['onayli_puan'])} · Bekleyen: {sayi_metni(ozet['onay_bekleyen_puan'])}"),
        ("Onay Bekleyen Kayıt", ozet["onay_bekleyen_kayit"], f"En eski {eski} gündür bekliyor" if eski is not None else "Bekleyen kayıt yok"),
        ("Faaliyet Yapan Öğrenci", ozet["faaliyet_yapan_ogrenci"],
         f"Kayıt başına ort. {sayi_metni(ozet['ortalama_puan_kayit'])} puan" if ozet.get("ortalama_puan_kayit") is not None else ""),
    ]
    tablolar = [
        ("Faaliyet Türüne Göre", ["Faaliyet", "Kayıt", "Puan", "Bekleyen"],
         [(f["faaliyet"], f["kayit_sayisi"], sayi_metni(f["puan"]), f["onay_bekleyen"]) for f in veri["faaliyetler"][:8]]),
        ("Birime Göre", ["Birim", "Kayıt", "Miktar"], [(b["birim"], b["kayit_sayisi"], b["miktar"]) for b in veri["birimler"][:8]]),
        ("Öğrenci Türüne Göre", ["Tür", "Öğrenci", "Puan"], [(t["etiket"], t["ogrenci_sayisi"], sayi_metni(t["puan"])) for t in veri["ogrenci_turleri"]]),
        ("Onay Bekleyen Kayıtlar", ["Öğrenci", "Faaliyet", "Gün"],
         [(b["ogrenci"], b["faaliyet"], b["bekleme_gun"]) for b in veri["onay_bekleyenler"][:8]] or [("Onay bekleyen kayıt yok.", "", "")]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Puan = adet × kaydın girildiği andaki faaliyet puanı.",),
            ("Toplam puana onay bekleyen kayıtlar da dahildir.",),
            ("Sayılar Faaliyet Raporu sayfasıyla aynıdır.",),
        ]),
    ]
    return kartlar, tablolar


def bakim_gecikme_gorunumu(veri):
    """'Bakım Gecikmeleri' görünümü: 4 kart + 5 tablo (Geciken Bakım Planı Raporu sayfasıyla aynı veri)."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet = veri["ozet"]
    cihaz = lambda p: f"{p['envanter_kodu']} - {p['cihaz_adi']}"
    ort = ozet.get("ortalama_gecikme_gun")
    kartlar = [
        ("Geciken Plan", ozet["geciken_plan"],
         f"Aktif planların {yuzde_metni(ozet['gecikme_orani'])}'i" if ozet.get("gecikme_orani") is not None else "Aktif plan yok"),
        ("Yaklaşan Plan", ozet["yaklasan_plan"], "Uyarı süresi içinde"),
        ("Ortalama Gecikme (gün)", sayi_metni(ort) if ort is not None else "—",
         f"En çok geciken: {ozet['en_cok_gecikme_gun']} gün" if ozet.get("en_cok_gecikme_gun") is not None else "Geciken plan yok"),
        ("Planı Olmayan Cihaz", ozet["plani_olmayan_cihaz"], "Aktif planı yok"),
    ]
    tablolar = [
        ("Geciken Planlar", ["Cihaz", "Plan", "Gecikme (gün)"],
         [(cihaz(p), p["gorev_turu"], p["gecikme_gun"]) for p in veri["geciken"][:8]] or [("Geciken plan yok.", "", "")]),
        ("Yaklaşan Planlar", ["Cihaz", "Plan", "Kalan (gün)"],
         [(cihaz(p), p["gorev_turu"], p["kalan_gun"]) for p in veri["yaklasan"][:8]] or [("Yaklaşan plan yok.", "", "")]),
        ("Cihaz Bazlı", ["Cihaz", "Geciken", "Yaklaşan"], [(c["cihaz"], c["geciken"], c["yaklasan"]) for c in veri["cihaz_ozeti"][:8]]),
        ("Planı Olmayan Cihazlar", ["Cihaz"], [(f"{c['envanter_kodu']} - {c['cihaz_adi']}",) for c in veri["planisiz_cihazlar"][:8]]
         or [("Tüm cihazların planı var.",)]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Gecikmiş: sonraki görev tarihi geçmiş aktif plan.",),
            ("Pasif planlar gecikmiş sayılmaz.",),
            ("Rapor bugünkü durumdur, dönemden bağımsızdır.",),
        ]),
    ]
    return kartlar, tablolar


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
        # Grafiği olmayan görünümlerde (Oda Kullanımı, Yetkiler...) boş alan tablolar arasına dağılmasın, sona toplansın.
        self.analiz_layout.addStretch(1)
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
            self._tur_degisti
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

        # Oda/cihaz kullanımı ve yetki raporları ek bilgidir: biri alınamazsa (örn. yetki yok) diğer raporlar yine gösterilir.
        for ad, (yol, donemli) in EK_KAYNAKLAR.items():
            try:
                yanit = oturum_kontrollu_istek(
                    "GET",
                    f"{self.api_url}/api/{yol}",
                    headers={
                        "Authorization": f"Bearer {self.token}"
                    },
                    params=params if donemli else {},
                    timeout=15,
                )
                sonuc[ad] = yanit.json() if yanit.status_code == 200 else None
            except (requests.RequestException, ValueError):
                sonuc[ad] = None

        return sonuc

    def _tur_degisti(self, *_):
        """Görünüm değişince ekranı günceller. 'Bugün Merkezde' dönemden bağımsız olduğu için seçilince kendiliğinden yüklenir."""
        self.gorunumu_guncelle()
        if self.rapor_turu.currentText() == "Bugün Merkezde":
            self.raporu_yukle()

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
        if "Kullanım" in baslik and len(sutunlar) > 1:
            # Ad sütunu esnek kalır (oda/cihaz adı kırpılmasın); sayı sütunları içeriğe göre daralır.
            for sutun in range(1, len(sutunlar)):
                widget.horizontalHeader().setSectionResizeMode(
                    sutun, QHeaderView.ResizeToContents
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
                oda_kullanim_tablosu(self.veriler.get("oda")),
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
                cihaz_kullanim_tablosu(self.veriler.get("cihaz_rez")),
                ("Bu Dönem", ["İşlem", "Kayıt"], [
                    (ad, co[kod]) for ad, kod in kodlar
                ]),
                ("Önceki Dönem", ["İşlem", "Kayıt"], [
                    (ad, cr[kod]) for ad, kod in kodlar
                ]),
                ("Veri Açıklaması", ["Bilgi"], [
                    ("Bunlar işlem kayıtlarının sayılarıdır.",),
                    ("Anlık cihaz durumu değildir.",),
                    ("Kullanım saatleri planlanan süredir.",),
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

        elif tur == "Oda Kullanımı":
            kartlar, tablolar = oda_gorunumu(self.veriler.get("oda"))

        elif tur == "Cihaz Kullanımı":
            kartlar, tablolar = cihaz_gorunumu(self.veriler.get("cihaz_rez"))

        elif tur == "Yetkiler":
            kartlar, tablolar = yetki_gorunumu(self.veriler.get("yetki"))

        elif tur == "Öğrenci Mevcudu":
            kartlar, tablolar = ogrenci_mevcut_gorunumu(self.veriler.get("ogrenci_rapor"))

        elif tur == "Faaliyet Onayları":
            kartlar, tablolar = faaliyet_onay_gorunumu(self.veriler.get("faaliyet_rapor"))

        elif tur == "Bakım Gecikmeleri":
            kartlar, tablolar = bakim_gecikme_gorunumu(self.veriler.get("bakim_plani"))

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
