"""TKYS Yönetim Raporları - bütünleşik raporlama paneli."""

import requests

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QGridLayout,
    QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QDateEdit, QFileDialog, QMessageBox, QScrollArea,
    QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView,
)

from client.tablo_tasarimi import cihaz_hucresi_uygula
from client.sayfa_tema import TABLO_STILI, golge, kart_olustur, liste_sayfasi_stili
from client.api_yoneticisi import (
    oturum_kontrollu_istek,
    api_hata_mesaji,
)
from client.yonetim_genel_bakis import KAYNAKLAR
from client.rapor_sayfasi_taban import sayi_metni, yuzde_metni
from client.yonetim_bugun_merkezde import BugunMerkezdeWidget
from client.yonetim_raporlari_pdf import pdf_olustur
from client.yonetim_rapor_hesaplari import (
    ROZET_RENKLERI, degisim, degisim_metni, gelmeme_orani, gerceklesen_randevu, iptal_orani,
    ileri_tarihli_planli, rozet_turu, tamamlanma_orani,
)


DONEM_KURALI_METNI = (
    "Önceki Dönem, takvime göre seçilir:\n"
    "•  Bu Ay: geçen ayın aynı günleri (1–21 Kasım ↔ 1–21 Ekim)\n"
    "•  Geçen Ay: bir önceki ayın tamamı\n"
    "•  Bugün ve Bu Hafta: geçen haftanın aynı günleri\n"
    "•  Diğer tarih aralıkları: hemen önceki, aynı uzunluktaki aralık"
)

RAPOR_TURLERI = (
    "Genel Bakış", "Randevular", "Cihazlar",
    "Öğrenciler", "Proje / Deney",
    "Oda Kullanımı", "Cihaz Kullanımı", "Yetkiler",
    "Öğrenci Mevcudu", "Faaliyetler", "Bakım Gecikmeleri",
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


GUN_KISALTMALARI = ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")


def gun_metni(iso_tarih):
    """2026-11-16 -> "16.11.2026 Pzt" (tabloda haftanın günü de görünsün)."""
    from datetime import date

    try:
        gun = date.fromisoformat(str(iso_tarih))
    except ValueError:
        return str(iso_tarih)
    return f"{gun:%d.%m.%Y} {GUN_KISALTMALARI[gun.weekday()]}"


ESKI_SUNUCU_NOTU = "Sunucuyu yeniden başlatın (eski sürüm)"


def _tarih_metni(iso):
    from datetime import date

    return date.fromisoformat(str(iso)).strftime("%d.%m.%Y")


def onceki_donem_kurali(secilen, onceki):
    """Önceki dönemin hangi kurala göre seçildiğini kullanıcının anlayacağı dille söyler."""
    from datetime import date

    s1, s2 = date.fromisoformat(secilen["baslangic"]), date.fromisoformat(secilen["bitis"])
    o1, o2 = date.fromisoformat(onceki["baslangic"]), date.fromisoformat(onceki["bitis"])
    if s1.day == 1 and o1.day == 1 and (s1.year, s1.month) == (s2.year, s2.month):
        import calendar

        ay_sonu = calendar.monthrange(s2.year, s2.month)[1]
        return "önceki ayın tamamı" if s2.day == ay_sonu else "geçen ayın aynı günleri"
    if (s1 - o1).days == 7 and (s2 - o2).days == 7:
        return "geçen haftanın aynı günleri"
    return "hemen önceki, aynı uzunluktaki dönem"


def donem_satiri(secilen, onceki, randevu_ozeti):
    """Rapor altındaki tarih satırı: 01.11.2026 – 21.11.2026 | Önceki: 01.10.2026 – 21.10.2026 (geçen ayın aynı günleri)."""
    metin_ = (
        f"Seçilen dönem: {_tarih_metni(secilen['baslangic'])} – {_tarih_metni(secilen['bitis'])}   |   "
        f"Önceki dönem: {_tarih_metni(onceki['baslangic'])} – {_tarih_metni(onceki['bitis'])}"
        f"  ({onceki_donem_kurali(secilen, onceki)})"
    )
    if "sonucu_girilmemis" not in randevu_ozeti:
        metin_ += "   |   ⚠ Sunucu eski sürümle çalışıyor: yeniden başlatın"
    return metin_


def randevu_durum_satirlari(secilen, onceki):
    """Randevu durumları: önce gerçekleşen (iptal hariç), sonra ayrıntısı, en sonda iptal.

    Sunucu "sonucu girilmemiş" sayısını göndermiyorsa (eski sürüm) o satırlar "—" gösterilir, 0 yazılmaz."""
    if "sonucu_girilmemis" in secilen:
        sonucsuz = (secilen["sonucu_girilmemis"], onceki.get("sonucu_girilmemis", 0))
        ileri = (ileri_tarihli_planli(secilen), ileri_tarihli_planli(onceki))
    else:
        sonucsuz = (None, None)
        ileri = (None, None)
    return [
        ("Gerçekleşen (iptal hariç)", gerceklesen_randevu(secilen), gerceklesen_randevu(onceki)),
        ("   Tamamlandı", secilen["tamamlandi"], onceki["tamamlandi"]),
        ("   Gelmedi", secilen["gelmedi"], onceki["gelmedi"]),
        ("   Sonucu girilmemiş", *sonucsuz),
        ("   İleri tarihli (planlı)", *ileri),
        ("İptal edildi", secilen["iptal_edildi"], onceki["iptal_edildi"]),
    ]


def bakim_uyari_tablosu(veri):
    """Cihazlar görünümü: bakım/kalibrasyon planlarının bugünkü durumu (Bakım Gecikmeleri raporuyla aynı veri)."""
    baslik = "Bakım Planı Uyarıları (bugün)"
    if veri is None:
        return (baslik, ["Bilgi"], [(YETKI_YOK,)])
    ozet = veri["ozet"]
    return (baslik, ["Gösterge", "Sayı"], [
        ("Geciken plan", ozet["geciken_plan"]),
        ("Yaklaşan plan (uyarı süresinde)", ozet["yaklasan_plan"]),
        ("Planı olmayan cihaz", ozet["plani_olmayan_cihaz"]),
    ])


def kullanilmayan_cihaz_tablosu(veri, en_cok=8):
    baslik = "Dönemde Hiç Kullanılmayan Cihazlar"
    if veri is None:
        return (baslik, ["Bilgi"], [(YETKI_YOK,)])
    satirlar = [
        (f"{c['envanter_kodu']} - {c['cihaz_adi']}",)
        for c in veri["cihazlar"] if c["rezervasyon_sayisi"] == 0
    ][:en_cok]
    return (baslik, ["Cihaz"], satirlar or [("Dönemde boş kalan cihaz yok.",)])


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
            (f"Saklama süresi: Gönüllü öğrenciler, pasife alındıktan {kural.get('saklama_yil', 2)} yıl (ertelenebilir).",),
            ("Öğrenci mevcudu dönemden bağımsız, güncel durumdur.",),
        ]),
    ]
    return kartlar, tablolar


def faaliyet_gorunumu(veri):
    """'Faaliyetler' görünümü: 4 kart + 5 tablo (Faaliyet Raporu sayfasıyla aynı veri)."""
    if veri is None:
        return _veri_yok_gorunumu()
    ozet = veri["ozet"]
    kartlar = [
        ("Faaliyet Kaydı", ozet["kayit_sayisi"], "Seçilen dönem"),
        ("Faaliyet Miktarı", ozet["faaliyet_miktari"], "Kayıtlardaki adetlerin toplamı"),
        ("Toplam Puan", sayi_metni(ozet["toplam_puan"]), "Adet × kayıt puanı"),
        ("Faaliyet Yapan Öğrenci", ozet["faaliyet_yapan_ogrenci"],
         f"Kayıt başına ort. {sayi_metni(ozet['ortalama_puan_kayit'])} puan" if ozet.get("ortalama_puan_kayit") is not None else ""),
    ]
    tablolar = [
        ("Faaliyet Türüne Göre", ["Faaliyet", "Kayıt", "Puan"],
         [(f["faaliyet"], f["kayit_sayisi"], sayi_metni(f["puan"])) for f in veri["faaliyetler"][:8]]),
        ("Birime Göre", ["Birim", "Kayıt", "Miktar"], [(b["birim"], b["kayit_sayisi"], b["miktar"]) for b in veri["birimler"][:8]]),
        ("Öğrenci Türüne Göre", ["Tür", "Öğrenci", "Puan"], [(t["etiket"], t["ogrenci_sayisi"], sayi_metni(t["puan"])) for t in veri["ogrenci_turleri"]]),
        ("Dönem Özeti", ["Gösterge", "Değer"], [
            ("Faaliyet kaydı", ozet["kayit_sayisi"]),
            ("Faaliyet miktarı", ozet["faaliyet_miktari"]),
            ("Toplam puan", sayi_metni(ozet["toplam_puan"])),
            ("Faaliyet yapan öğrenci", ozet["faaliyet_yapan_ogrenci"]),
        ]),
        ("Önemli Açıklamalar", ["Bilgi"], [
            ("Puan = adet × kaydın girildiği andaki faaliyet puanı.",),
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


GENIS_ALT_SIRA = 1180      # bu genişliğin altında alt sıradaki 3. tablo ikinci satıra iner


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
        self.setStyleSheet(liste_sayfasi_stili() + """
            QWidget#YonetimRaporPaneli {
                background: #EAF0FA;
            }
            QFrame#YonetimAnaPanel {
                background: transparent;
                border: none;
            }
            QFrame#YonetimKpiKarti {
                background: #FFFFFF;
                border: none;
                border-radius: 16px;
            }
            QFrame#YonetimKpiKarti QLabel {
                border: none;
                background: transparent;
            }
            QPushButton#YonetimPdf {
                background: #16803C;
                color: white;
                border: none;
            }
            QLabel#donemOzeti {
                font-size: 12px;
                color: #6B7FA8;
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
        govde_lay.setContentsMargins(12, 10, 12, 10)

        panel = QFrame()
        panel.setObjectName("YonetimAnaPanel")
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(12, 10, 12, 10)
        panel_lay.setSpacing(16)

        # Sayfa başlığı
        baslik_blogu = QVBoxLayout()
        baslik_blogu.setSpacing(3)
        sayfa_baslik = QLabel("Yönetim Raporları ve İstatistikler")
        sayfa_baslik.setObjectName("baslik")
        sayfa_alt = QLabel("Randevu, cihaz, öğrenci ve proje göstergelerinin dönem karşılaştırması.")
        sayfa_alt.setObjectName("altBaslik")
        baslik_blogu.addWidget(sayfa_baslik)
        baslik_blogu.addWidget(sayfa_alt)
        panel_lay.addLayout(baslik_blogu)

        self.filtreleri_olustur(panel_lay)

        self.bugun_panel = BugunMerkezdeWidget()
        panel_lay.addWidget(self.bugun_panel)

        self.analiz_alani = QWidget()
        self.analiz_layout = QVBoxLayout(self.analiz_alani)
        self.analiz_layout.setContentsMargins(0, 0, 0, 0)
        self.analiz_layout.setSpacing(16)

        self.kartlari_olustur(self.analiz_layout)

        self.karsilastirma_grafigi = YonetimKarsilastirmaGrafigi(
            baslik_metni="Dönem Karşılaştırması",
            aciklama_metni="İşlem sayıları (iptaller hariç) · Seçilen dönem (mavi) ile önceki dönem (turuncu)"
        )

        self.ogrenci_donem_grafigi = YonetimKarsilastirmaGrafigi(
            baslik_metni="Öğrenci Faaliyet Puanı",
            aciklama_metni=(
                "Faaliyet türüne göre puan dağılımı · Seçilen dönem · Onay bekleyen kayıtlar dahil"
            )
        )

        from client.yonetim_genel_bakis_ozet_widget import (
            OperasyonelOzet, OgrenciFaaliyetOzeti
        )

        self.operasyon_ozeti = OperasyonelOzet()
        self.ogrenci_ozeti = OgrenciFaaliyetOzeti()

        # Genel Bakış: sayılar solda, görseli sağda (iki sütun); sayfa tek ekrana yakın kalır.
        for sol, sag in (
            (self.operasyon_ozeti, self.karsilastirma_grafigi),
            (self.ogrenci_ozeti, self.ogrenci_donem_grafigi),
        ):
            yan_yana = QHBoxLayout()
            yan_yana.setSpacing(16)
            yan_yana.addWidget(sol, 5)
            yan_yana.addWidget(sag, 6)
            self.analiz_layout.addLayout(yan_yana)

        self.randevu_grafigi = YonetimRandevuGrafigi()
        self.analiz_layout.addWidget(self.randevu_grafigi)

        self.cihaz_grafigi = YonetimKarsilastirmaGrafigi()
        self.analiz_layout.addWidget(self.cihaz_grafigi)

        self.ogrenci_puan_grafigi = YonetimOgrenciPuanGrafigi()
        self.analiz_layout.addWidget(self.ogrenci_puan_grafigi)

        self.proje_grafigi = YonetimProjeGrafigi()
        self.analiz_layout.addWidget(self.proje_grafigi)

        from client.yonetim_grafik_turleri import GRAFIK_TURLERI, grafik_secimi_ekle

        # Kategorileri karşılaştıran grafiklerde yalnızca Sütun anlamlıdır (Çizgi süreklilik, Pasta dönem kıyası ima eder);
        # puanın faaliyet türüne göre dağılımı ise en iyi Pasta ile okunur.
        for widget, rapor, varsayilan, turler in (
            (self.karsilastirma_grafigi, "karsilastirma", "Sütun", ("Sütun",)),
            (self.ogrenci_donem_grafigi, "ogrenci", "Pasta", ("Pasta", "Sütun")),
            (self.randevu_grafigi, "randevu", "Çizgi", GRAFIK_TURLERI),
            (self.cihaz_grafigi, "karsilastirma", "Sütun", ("Sütun",)),
            (self.ogrenci_puan_grafigi, "ogrenci", "Yatay Çubuk", GRAFIK_TURLERI),
            (self.proje_grafigi, "proje", "Yatay Çubuk", GRAFIK_TURLERI),
        ):
            grafik_secimi_ekle(widget, rapor, varsayilan, turler)

        from client.yonetim_ek_rapor_grafigi import EkRaporGrafigi

        self.ek_rapor_grafigi = EkRaporGrafigi()
        self.analiz_layout.addWidget(self.ek_rapor_grafigi)

        self.tablolari_olustur(self.analiz_layout)
        # Grafiği olmayan görünümlerde (Oda Kullanımı, Yetkiler...) boş alan tablolar arasına dağılmasın, sona toplansın.
        self.analiz_layout.addStretch(1)
        panel_lay.addWidget(self.analiz_alani)

        self.durum = QLabel(
            "Rapor verilerini görmek için Raporu Yenile'ye basın."
        )
        self.durum.setWordWrap(True)
        self.durum.setStyleSheet(
            "color: #6B7FA8; font-size: 12px;"
            "background: transparent; border: none;"
        )
        panel_lay.addWidget(self.durum)

        govde_lay.addWidget(panel)
        kaydir.setWidget(govde)

        self.rapor_turu.setCurrentText("Genel Bakış")
        self.gorunumu_guncelle()



    def filtreleri_olustur(self, panel_lay):
        # Süzgeçler tek beyaz kartta: üstte dönem/rapor seçimi, altta dönemin gerçek tarihleri, "Tarih Aralığı"nda tarih seçiciler.
        filtre_karti = kart_olustur()
        filtre_duzen = QVBoxLayout(filtre_karti)
        filtre_duzen.setContentsMargins(16, 12, 16, 12)
        filtre_duzen.setSpacing(10)
        filtre = QHBoxLayout()
        filtre.setSpacing(10)
        filtre_duzen.addLayout(filtre)

        def kucuk_etiket(yazi):
            lbl = QLabel(yazi)
            lbl.setObjectName("etiket")
            return lbl

        self.donem_etiketi = kucuk_etiket("Dönem")
        filtre.addWidget(self.donem_etiketi)

        self.donem = QComboBox()
        self.donem.addItems([
            "Bugün", "Bu Hafta", "Bu Ay",
            "Geçen Ay", "Tarih Aralığı"
        ])
        self.donem.setCurrentText("Bu Ay")
        self.donem.setMinimumWidth(140)
        filtre.addWidget(self.donem)

        filtre.addWidget(kucuk_etiket("Rapor"))

        self.rapor_turu = QComboBox()
        self.rapor_turu.addItems(RAPOR_TURLERI)
        self.rapor_turu.setMinimumWidth(180)
        filtre.addWidget(self.rapor_turu)

        filtre.addStretch(1)

        self.donem_bilgi_btn = QPushButton("ⓘ  Dönemler Hakkında")
        self.donem_bilgi_btn.setObjectName("hayalet")
        self.donem_bilgi_btn.setToolTip(
            "Seçilen ve önceki dönemin ne anlama geldiğini gösterir."
        )
        filtre.addWidget(self.donem_bilgi_btn)
        self.donem_bilgi_btn.clicked.connect(
            self.donem_bilgisi_goster
        )

        self.yenile_btn = QPushButton("⟳  Yenile")
        self.yenile_btn.setObjectName("hayalet")
        filtre.addWidget(self.yenile_btn)

        self.pdf_btn = QPushButton("PDF Kaydet")
        self.pdf_btn.setObjectName("YonetimPdf")
        filtre.addWidget(self.pdf_btn)
        self.pdf_btn.hide()  # PDF özelliği şimdilik gizli

        # Başlangıç/bitiş yalnızca "Tarih Aralığı" seçilince görünür (hazır dönemlerde tarihler alttaki satırda yazılıdır).
        self.tarih_alani = QWidget()
        tarih_satiri = QHBoxLayout(self.tarih_alani)
        tarih_satiri.setContentsMargins(0, 0, 0, 0)
        tarih_satiri.setSpacing(10)

        self.baslangic = QDateEdit()
        self.bitis = QDateEdit()

        for alan in (self.baslangic, self.bitis):
            alan.setCalendarPopup(True)
            alan.setDisplayFormat("dd.MM.yyyy")
            alan.setDate(QDate.currentDate())
            alan.setMinimumWidth(160)
            alan.setEnabled(False)

        self.baslangic_etiketi = kucuk_etiket("Başlangıç")
        tarih_satiri.addWidget(self.baslangic_etiketi)
        tarih_satiri.addWidget(self.baslangic)
        tarih_satiri.addSpacing(8)
        self.bitis_etiketi = kucuk_etiket("Bitiş")
        tarih_satiri.addWidget(self.bitis_etiketi)
        tarih_satiri.addWidget(self.bitis)
        tarih_satiri.addStretch(1)
        self.tarih_alani.setVisible(False)

        self.donem_ozeti = QLabel("Karşılaştırılan dönemler, rapor yüklenince burada görünür.")
        self.donem_ozeti.setObjectName("donemOzeti")
        filtre_duzen.addWidget(self.donem_ozeti)
        filtre_duzen.addWidget(self.tarih_alani)

        panel_lay.addWidget(filtre_karti)

        # Seçilen hazır dönemin gerçek tarihlerini de göster.
        self.donem.currentTextChanged.connect(
            self.tarih_alanlarini_guncelle
        )
        self.donem.currentTextChanged.connect(self._donem_degisti)
        self.rapor_turu.currentTextChanged.connect(
            self._tur_degisti
        )
        self.yenile_btn.clicked.connect(self.raporu_yukle)
        self.pdf_btn.clicked.connect(self.pdf_kaydet)

        self.tarih_alanlarini_guncelle(
            self.donem.currentText()
        )

    def donem_bilgisi_goster(self):
        """Raporun karşılaştırdığı tarih aralıklarını açıklar."""
        secili = self.yuklenen_donem
        veriler = self.veriler

        if not secili or not veriler:
            QMessageBox.information(
                self,
                "Dönemler Hakkında",
                "Seçilen Dönem: Tarih filtresinde belirlediğiniz aralıktır.\n\n"
                + DONEM_KURALI_METNI +
                "\n\nGerçek tarihleri görmek için raporu yükleyin."
            )
            return

        try:
            guncel_filtre = self.tarih_parametreleri()
        except ValueError:
            QMessageBox.information(
                self,
                "Dönemler Hakkında",
                "Geçerli bir tarih aralığı seçin."
            )
            return

        if guncel_filtre != secili:
            QMessageBox.information(
                self,
                "Dönemler Hakkında",
                "Tarih filtresi değişti. Güncel dönemlerin tarihlerini "
                "görmek için raporu yenileyin."
            )
            return

        try:
            onceki = veriler["randevu"]["onceki_donem"]
            from datetime import date

            def tarih_yaz(deger):
                return date.fromisoformat(deger).strftime("%d.%m.%Y")

            secilen_tarih = (
                f"{tarih_yaz(secili['baslangic'])} – "
                f"{tarih_yaz(secili['bitis'])}"
            )
            onceki_tarih = (
                f"{tarih_yaz(onceki['baslangic'])} – "
                f"{tarih_yaz(onceki['bitis'])}"
            )
        except (KeyError, TypeError):
            QMessageBox.information(
                self,
                "Dönemler Hakkında",
                "Tarih bilgileri alınamadı. Raporu yenileyin."
            )
            return

        QMessageBox.information(
            self,
            "Dönem Karşılaştırması",
            "SEÇİLEN DÖNEM\n"
            f"{secilen_tarih}\n"
            "Filtrede belirlediğiniz tarih aralığıdır.\n\n"
            "ÖNCEKİ DÖNEM\n"
            f"{onceki_tarih}\n\n"
            + DONEM_KURALI_METNI +
            "\n\nGrafikler, kartlardaki ▲▼ değişimler ve karşılaştırma tabloları bu "
            "iki dönemin verilerini gösterir. Sayılarda iptal edilenler hariçtir."
        )

    def kartlari_olustur(self, panel_lay):
        satir = QHBoxLayout()
        satir.setSpacing(16)
        self.kartlar = []

        for serit_rengi in ("#1D4ED8", "#D97706", "#DC2626", "#0E9F6E"):
            kart = QFrame()
            kart.setObjectName("YonetimKpiKarti")
            golge(kart)
            kart_duzen = QHBoxLayout(kart)
            kart_duzen.setContentsMargins(16, 14, 18, 14)
            kart_duzen.setSpacing(14)
            serit = QFrame()
            serit.setFixedWidth(4)
            serit.setStyleSheet(f"background: {serit_rengi}; border: none; border-radius: 2px;")
            kart_duzen.addWidget(serit)
            kl = QVBoxLayout()
            kl.setSpacing(4)
            kart_duzen.addLayout(kl, 1)

            baslik = QLabel("—")
            baslik.setStyleSheet(
                "color: #6B7FA8; font-size: 12px; font-weight: 700;"
            )

            deger = QLabel("—")
            deger.setStyleSheet(
                "color: #0F2552; font-size: 28px;"
                "font-weight: 800;"
            )

            alt = QLabel("")
            alt.setWordWrap(True)
            alt.setStyleSheet(
                "color: #8A98B0; font-size: 11px;"
            )

            # Önceki döneme göre değişim rozeti (▲ %12 / ▼ 2 puan); renk iyi/kötü yönünü, ok ve yazı değeri söyler.
            rozet = QLabel("")
            rozet.setToolTip("Önceki döneme göre değişim")
            rozet.hide()

            deger_satiri = QHBoxLayout()
            deger_satiri.setSpacing(8)
            deger_satiri.addWidget(deger)
            deger_satiri.addWidget(rozet, 0, Qt.AlignVCenter)
            deger_satiri.addStretch(1)

            kl.addWidget(baslik)
            kl.addLayout(deger_satiri)
            kl.addWidget(alt)

            satir.addWidget(kart, 1)
            self.kartlar.append((baslik, deger, alt, rozet))

        panel_lay.addLayout(satir)

    def karti_doldur(self, widgetlar, ad, deger, alt, ek):
        """Kartı doldurur. ek: {"once", "simdi", "yon", "oran"} değişim rozeti için;
        {"uyari": True} kartın kendisi dikkat istiyorsa (değer ve not turuncu), {"uyari_notu": True} yalnızca not turuncu."""
        baslik_lbl, deger_lbl, alt_lbl, rozet = widgetlar
        baslik_lbl.setText(ad)
        deger_lbl.setText(metin(deger))
        alt_lbl.setText(alt)
        uyari = bool(ek.get("uyari"))
        uyari_notu = uyari or bool(ek.get("uyari_notu"))
        deger_lbl.setStyleSheet(
            f"color: {'#B45309' if uyari else '#0F2552'}; font-size: 28px; font-weight: 800;"
        )
        alt_lbl.setStyleSheet(f"color: {'#B45309' if uyari_notu else '#8A98B0'}; font-size: 11px;")

        if "once" not in ek:
            rozet.hide()
            return
        simdi = ek.get("simdi", deger)
        ok, yazi = degisim(simdi, ek["once"], oran=ek.get("oran", False))
        if ok is None and yazi == "—":
            rozet.hide()
            return
        renk, zemin = ROZET_RENKLERI[rozet_turu(ok, ek.get("yon", 0))]
        rozet.setText(f"{ok} {yazi}" if ok else yazi)
        rozet.setStyleSheet(
            f"color: {renk}; background: {zemin}; border-radius: 9px; padding: 2px 8px;"
            "font-size: 11px; font-weight: 700;"
        )
        rozet.show()

    def tablo_olustur(self, yukseklik):
        bolum = kart_olustur()
        lay = QVBoxLayout(bolum)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        baslik = QLabel("—")
        baslik.setObjectName("kartBaslik")
        lay.addWidget(baslik)

        tablo = QTableWidget()
        tablo.setStyleSheet(TABLO_STILI + "QTableWidget::item { padding: 3px 10px; }")
        tablo.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tablo.setShowGrid(False)
        tablo.setFrameShape(QFrame.NoFrame)
        tablo.setMinimumHeight(yukseklik)
        tablo.setMaximumHeight(yukseklik)
        tablo.verticalHeader().setVisible(False)
        tablo.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        tablo.setSelectionMode(QTableWidget.NoSelection)
        tablo.setFocusPolicy(Qt.NoFocus)                 # tıklanınca hücre çevresinde çerçeve çıkmasın
        tablo.setWordWrap(True)                          # uzun açıklamalar "…" ile kesilmez, alt satıra geçer
        tablo.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        lay.addWidget(tablo)
        lay.addStretch(1)                                # kart yüksekliği farklıysa başlık/tablo üstte kalır

        return bolum, baslik, tablo

    def tablolari_olustur(self, panel_lay):
        self.tablolar = []

        ust = QHBoxLayout()
        ust.setSpacing(14)
        ust.setAlignment(Qt.AlignTop)

        for i in range(2):
            bolum, baslik, tablo = self.tablo_olustur(300)      # 7 satır kaydırmadan görünsün
            ust.addWidget(bolum, 3 if i == 0 else 2)
            self.tablolar.append((baslik, tablo))

        panel_lay.addLayout(ust)

        # Alt sıra: geniş pencerede 3 tablo yan yana, dar pencerede 2 + 1 (tablolar sıkışıp yatay kaydırma çıkarmasın).
        self.alt_izgara = QGridLayout()
        self.alt_izgara.setSpacing(14)
        self.alt_izgara.setAlignment(Qt.AlignTop)
        self.alt_kartlar = []
        self.alt_sutun_sayisi = 0

        for _ in range(3):
            bolum, baslik, tablo = self.tablo_olustur(250)      # 5 satır kaydırmadan görünsün
            self.alt_kartlar.append(bolum)
            self.tablolar.append((baslik, tablo))

        panel_lay.addLayout(self.alt_izgara)
        self.alt_sirayi_diz(GENIS_ALT_SIRA)

    def alt_sirayi_diz(self, genislik):
        sutun = 3 if genislik >= GENIS_ALT_SIRA else 2
        if sutun == self.alt_sutun_sayisi:
            return
        self.alt_sutun_sayisi = sutun
        for kart in self.alt_kartlar:
            self.alt_izgara.removeWidget(kart)
        for sira, kart in enumerate(self.alt_kartlar):
            if sutun == 3 or sira < 2:
                self.alt_izgara.addWidget(kart, 0, sira)
            else:
                self.alt_izgara.addWidget(kart, 1, 0, 1, 2)
        for sira in range(3):
            self.alt_izgara.setColumnStretch(sira, 1 if sira < sutun else 0)

    def resizeEvent(self, olay):
        super().resizeEvent(olay)
        self.alt_sirayi_diz(olay.size().width())

    def tarih_alanlarini_guncelle(self, secim):
        ozel = secim == "Tarih Aralığı"
        self.baslangic.setEnabled(ozel)
        self.bitis.setEnabled(ozel)
        self.tarih_alani.setVisible(ozel and self.rapor_turu.currentText() != "Bugün Merkezde")

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
        """Görünüm değişince ekranı günceller ve raporu kendiliğinden yükler (Yenile'ye basmak gerekmez)."""
        self.gorunumu_guncelle()
        self.raporu_yukle()

    def _donem_degisti(self, secim):
        """Hazır dönem seçilince rapor kendiliğinden yenilenir; 'Tarih Aralığı'nda kullanıcı tarihleri seçip Yenile'ye basar."""
        if secim != "Tarih Aralığı":
            self.raporu_yukle()

    def sayfa_gosterildi(self):
        """Menüden açılınca ya da yeniden girilince güncel raporu getirir."""
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

            self.durum.setText(donem_satiri(params, onceki, veriler["randevu"]["ozet"]))
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
        # Aynı tablolar farklı görünümlerde yeniden kullanılır: önce eski çizicileri kaldır, sonra "Cihaz" sütununu iki satırlı çiz.
        varsayilan = widget.property("varsayilan_satir_yuksekligi")
        if varsayilan is None:
            varsayilan = widget.verticalHeader().defaultSectionSize()
            widget.setProperty("varsayilan_satir_yuksekligi", varsayilan)
        for j in range(len(sutunlar)):
            widget.setItemDelegateForColumn(j, None)
        widget.verticalHeader().setDefaultSectionSize(int(varsayilan))
        for j, ad in enumerate(sutunlar):
            if ad == "Cihaz":
                cihaz_hucresi_uygula(widget, j)

        for i, satir in enumerate(satirlar):
            for j, deger in enumerate(satir):
                oge = QTableWidgetItem(metin(deger))
                oge.setToolTip(metin(deger).strip())
                widget.setItem(i, j, oge)

        widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        if len(sutunlar) > 1:
            # Ad sütunu esnek kalır (oda/cihaz/faaliyet adı kırpılmasın); sayı sütunları içeriğe göre daralır.
            for sutun in range(1, len(sutunlar)):
                widget.horizontalHeader().setSectionResizeMode(
                    sutun, QHeaderView.ResizeToContents
                )
        self._tablo_yuksekligini_ayarla(widget, len(satirlar))

    def _tablo_yuksekligini_ayarla(self, widget, satir_sayisi):
        """Tablo, satırları kaydırma çubuğu olmadan gösterecek kadar yüksek olur (en az 7, en çok 12 satırlık yükseklik)."""
        widget.resizeRowsToContents()
        satir_yuksekligi = max(30, widget.verticalHeader().defaultSectionSize() // 2 * 2)
        gerekli = widget.horizontalHeader().height() + sum(widget.rowHeight(i) for i in range(satir_sayisi)) + 6
        yukseklik = max(7 * satir_yuksekligi, min(gerekli, 12 * satir_yuksekligi + 60))
        widget.setMinimumHeight(int(yukseklik))
        widget.setMaximumHeight(int(yukseklik))

    def donem_ozetini_yaz(self, randevu):
        """Süzgeç kartının altındaki satıra, karşılaştırılan iki dönemin gerçek tarihlerini yazar (her rapor türünde)."""
        from datetime import date

        try:
            def aralik(donem):
                ilk, son = date.fromisoformat(donem["baslangic"]), date.fromisoformat(donem["bitis"])
                return f"{ilk:%d.%m.%Y} – {son:%d.%m.%Y}"

            self.donem_ozeti.setText(
                f"Seçilen dönem: {aralik(randevu['donem'])}    ·    Önceki dönem: {aralik(randevu['onceki_donem'])}"
            )
        except (KeyError, TypeError, ValueError):
            self.donem_ozeti.setText("Karşılaştırılan dönemler, rapor yüklenince burada görünür.")

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
        self.donem_bilgi_btn.setVisible(not gunluk)

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
            self.donem_ozeti,
        ):
            kontrol.setVisible(not gunluk)
        self.tarih_alani.setVisible(
            not gunluk and self.donem.currentText() == "Tarih Aralığı"
        )

        if gunluk:
            return

        genel_bakis = (
            self.rapor_turu.currentText() == "Genel Bakış"
        )
        self.operasyon_ozeti.setVisible(genel_bakis)
        self.ogrenci_ozeti.setVisible(genel_bakis)

        self.karsilastirma_grafigi.setVisible(genel_bakis)

        self.ogrenci_donem_grafigi.setVisible(genel_bakis)

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

        ek_raporlar = (
            "Oda Kullanımı", "Cihaz Kullanımı", "Yetkiler",
            "Öğrenci Mevcudu", "Faaliyetler",
            "Bakım Gecikmeleri",
        )
        self.ek_rapor_grafigi.setVisible(
            self.rapor_turu.currentText() in ek_raporlar
        )

        if self.veriler is None:
            for baslik, deger, alt, rozet in self.kartlar:
                baslik.setText("—")
                deger.setText("—")
                alt.setText("")
                rozet.hide()

            for tablo in self.tablolar:
                self.tabloyu_doldur(
                    tablo, "Rapor henüz yüklenmedi",
                    ["Bilgi"], []
                )
            return

        r = self.veriler["randevu"]
        self.donem_ozetini_yaz(r)
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

        # Ortak kural: "yapılan iş" sayılarında iptal edilenler hariçtir, iptaller ayrıca gösterilir.
        ro_gercek, rr_gercek = gerceklesen_randevu(ro), gerceklesen_randevu(rr)
        ro_gelmeme, rr_gelmeme = gelmeme_orani(ro), gelmeme_orani(rr)
        # Sunucu eski sürümle çalışıyorsa bu alan gelmez: "0" (hepsi girilmiş) sanılmasın, uyarılsın.
        eski_sunucu = "sonucu_girilmemis" not in ro
        sonucsuz = None if eski_sunucu else int(ro["sonucu_girilmemis"])
        sonucsuz_notu = (
            f"⚠ {sonucsuz} randevunun sonucu girilmemiş" if sonucsuz else ""
        )

        if tur == "Genel Bakış":
            self.operasyon_ozeti.tarihleri_guncelle(
                r["donem"],
                r["onceki_donem"],
            )
            secilen = [
                ro_gercek, co["bakim"], co["kalibrasyon"], co["ariza"],
                co["rezervasyon"], po["etkinlik_iptal_edilmemis"],
            ]
            onceki = [
                rr_gercek, cr["bakim"], cr["kalibrasyon"], cr["ariza"],
                cr["rezervasyon"], pr["etkinlik_iptal_edilmemis"],
            ]
            self.operasyon_ozeti.guncelle(secilen, onceki)

            self.ogrenci_ozeti.guncelle(
                o["guncel_ogrenci"]["toplam"],
                oo["kayit_sayisi"],
                oo["faaliyet_yapan_ogrenci"],
            )

            self.karsilastirma_grafigi.guncelle(
                [
                    "Randevu", "Bakım", "Kalibrasyon",
                    "Arıza", "Rezervasyon",
                    "Oda etkinliği",
                ],
                secilen,
                onceki,
            )

            self.ogrenci_donem_grafigi.guncelle(o["faaliyet_dagilimi"])
            kartlar = [
                ("Randevu", ro_gercek,
                 f"İptal hariç · {ro['iptal_edildi']} iptal ayrıca",
                 {"once": rr_gercek, "yon": 0}),
                ("Gelmeme Oranı", yuzde_metni(ro_gelmeme),
                 sonucsuz_notu or f"{ro['gelmedi']} danışan gelmedi",
                 {"simdi": ro_gelmeme, "once": rr_gelmeme, "yon": -1, "oran": True, "uyari_notu": bool(sonucsuz)}),
                ("Arıza Bildirimi", co["ariza"], "Seçilen dönem",
                 {"once": cr["ariza"], "yon": -1}),
                ("Faaliyet Puanı", oo["toplam_puan"],
                 f"{oo['kayit_sayisi']} faaliyet kaydı",
                 {"once": ore["toplam_puan"], "yon": 1}),
            ]
            tablolar = [
                ("Randevu Durumu", ["Durum", "Seçilen Dönem", "Önceki Dönem"],
                 randevu_durum_satirlari(ro, rr)),
                ("Öğrenci Faaliyetleri", ["Faaliyet", "Kayıt", "Puan"],
                 [
                     (f["faaliyet"], f["kayit_sayisi"], f["toplam_puan"])
                     for f in o["faaliyet_dagilimi"]
                 ] or [("Dönemde faaliyet kaydı yok.", "", "")]),
                ("Proje / Etkinlik", ["Gösterge", "Sayı"], [
                    ("Cihaz rezervasyonu (iptal hariç)", po["rezervasyon_iptal_edilmemis"]),
                    ("İptal edilen rezervasyon", po["rezervasyon_iptal"]),
                    ("Oda etkinliği (iptal hariç)", po["etkinlik_iptal_edilmemis"]),
                    ("Kayıtlı katılımcı", po["kayitli_katilimci_toplami"]),
                ]),
            ]

        elif tur == "Randevular":
            self.randevu_grafigi.guncelle(r["gunluk"])
            ro_tamam, rr_tamam = tamamlanma_orani(ro), tamamlanma_orani(rr)
            kartlar = [
                ("Gerçekleşen Randevu", ro_gercek,
                 f"İptal hariç · {ro['iptal_edildi']} iptal edildi",
                 {"once": rr_gercek, "yon": 0}),
                ("Tamamlanma Oranı", yuzde_metni(ro_tamam),
                 f"{ro['tamamlandi']} randevu tamamlandı",
                 {"simdi": ro_tamam, "once": rr_tamam, "yon": 1, "oran": True}),
                ("Gelmeme Oranı", yuzde_metni(ro_gelmeme),
                 f"{ro['gelmedi']} danışan gelmedi",
                 {"simdi": ro_gelmeme, "once": rr_gelmeme, "yon": -1, "oran": True}),
                ("Sonucu Girilmemiş", sonucsuz,
                 ESKI_SUNUCU_NOTU if eski_sunucu else (
                     "Tarihi geçti, hâlâ “Planlandı”" if sonucsuz else "Tüm geçmiş randevuların sonucu girilmiş"),
                 {"uyari": eski_sunucu or bool(sonucsuz)}),
            ]
            tablolar = [
                ("Randevu Durumları",
                 ["Durum", "Seçilen Dönem", "Önceki Dönem"],
                 randevu_durum_satirlari(ro, rr)),
                ("Günlük Randevu Sayıları", ["Tarih", "Randevu"], [
                    (gun_metni(g["tarih"]), g["sayi"]) for g in r["gunluk"]
                ]),
                ("Oranlar", ["Gösterge", "Seçilen", "Önceki", "Değişim"], [
                    ("Tamamlanma", yuzde_metni(ro_tamam), yuzde_metni(rr_tamam),
                     degisim_metni(ro_tamam, rr_tamam, oran=True)),
                    ("Gelmeme", yuzde_metni(ro_gelmeme), yuzde_metni(rr_gelmeme),
                     degisim_metni(ro_gelmeme, rr_gelmeme, oran=True)),
                    ("İptal", yuzde_metni(iptal_orani(ro)), yuzde_metni(iptal_orani(rr)),
                     degisim_metni(iptal_orani(ro), iptal_orani(rr), oran=True)),
                ]),
                ("Yapılması Gerekenler", ["Bilgi"], (
                    [
                        ("Sunucu eski sürümle çalışıyor: sonucu girilmemiş randevular sayılamadı.",),
                        ("Sunucuyu yeniden başlatın, sonra Yenile'ye basın.",),
                    ] if eski_sunucu else [
                        (f"{sonucsuz} randevunun tarihi geçti ama sonucu girilmedi.",),
                        ("Randevu Yönetimi'nden sonuçlarını girin.",),
                        ("Sonuç girilmeden oranlar eksik hesaplanır.",),
                    ] if sonucsuz else [
                        ("Tüm geçmiş randevuların sonucu girilmiş.",),
                        ("Oranlar sonuçlanan randevulara (tamamlanan + gelmeyen) göre hesaplanır.",),
                    ]
                )),
                oda_kullanim_tablosu(self.veriler.get("oda")),
            ]

        elif tur == "Cihazlar":
            self.cihaz_grafigi.guncelle(
                ["Bakım", "Kalibrasyon", "Arıza", "Rezervasyon"],
                [co["bakim"], co["kalibrasyon"], co["ariza"], co["rezervasyon"]],
                [cr["bakim"], cr["kalibrasyon"], cr["ariza"], cr["rezervasyon"]],
            )
            kodlar = [
                ("Bakım", "bakim", 0),
                ("Kalibrasyon", "kalibrasyon", 0),
                ("Arıza", "ariza", -1),
                ("Rezervasyon", "rezervasyon", 0),
            ]
            kartlar = [
                (ad + (" (iptal hariç)" if kod == "rezervasyon" else " Kaydı"), co[kod], "Seçilen dönem",
                 {"once": cr[kod], "yon": yon})
                for ad, kod, yon in kodlar
            ]
            tablolar = [
                ("Cihaz İşlem Karşılaştırması",
                 ["İşlem", "Seçilen", "Önceki", "Değişim"], [
                     (ad, co[kod], cr[kod], degisim_metni(co[kod], cr[kod])) for ad, kod, _ in kodlar
                 ]),
                cihaz_kullanim_tablosu(self.veriler.get("cihaz_rez")),
                bakim_uyari_tablosu(self.veriler.get("bakim_plani")),
                kullanilmayan_cihaz_tablosu(self.veriler.get("cihaz_rez")),
                ("Veri Açıklaması", ["Bilgi"], [
                    ("Bunlar işlem kayıtlarının sayılarıdır.",),
                    ("İptal edilen rezervasyonlar sayılmaz.",),
                    ("Bakım planı uyarıları bugünkü durumdur.",),
                ]),
            ]

        elif tur == "Öğrenciler":
            self.ogrenci_puan_grafigi.guncelle(
                o["faaliyet_dagilimi"]
            )
            aktif = o["guncel_ogrenci"]["aktif"]
            katilim = (oo["faaliyet_yapan_ogrenci"] / aktif) if aktif else None
            kartlar = [
                ("Aktif Öğrenci", aktif,
                 f"Toplam {o['guncel_ogrenci']['toplam']} öğrenci · güncel durum"),
                ("Faaliyet Yapan Öğrenci", oo["faaliyet_yapan_ogrenci"],
                 f"Aktiflerin {yuzde_metni(katilim)}'i" if katilim is not None else "Seçilen dönem",
                 {"once": ore["faaliyet_yapan_ogrenci"], "yon": 1}),
                ("Toplam Puan", oo["toplam_puan"],
                 "Seçilen dönem",
                 {"once": ore["toplam_puan"], "yon": 1}),
                ("Faaliyet Kaydı", oo["kayit_sayisi"],
                 "Seçilen dönem",
                 {"once": ore["kayit_sayisi"], "yon": 1}),
            ]
            alanlar = [
                ("Faaliyet kaydı", "kayit_sayisi"),
                ("Faaliyet miktarı", "faaliyet_miktari"),
                ("Toplam puan", "toplam_puan"),
                ("Faaliyet yapan öğrenci",
                 "faaliyet_yapan_ogrenci"),
            ]
            tablolar = [
                ("Faaliyet Türlerine Göre Puanlar",
                 ["Faaliyet", "Kayıt", "Puan"], [
                     (f["faaliyet"], f["kayit_sayisi"], f["toplam_puan"])
                     for f in o["faaliyet_dagilimi"]
                 ] or [("Dönemde faaliyet kaydı yok.", "", "")]),
                ("Önceki Dönem Karşılaştırması",
                 ["Gösterge", "Seçilen", "Önceki", "Değişim"], [
                     (ad, oo[kod], ore[kod], degisim_metni(oo[kod], ore[kod])) for ad, kod in alanlar
                 ]),
                ("Önemli Açıklamalar", ["Bilgi"], [
                    ("Puan = adet × kaydın girildiği andaki faaliyet puanı.",),
                    ("Öğrenci mevcudu günceldir; diğer sayılar seçilen döneme aittir.",),
                ]),
                ("Katılım", ["Gösterge", "Değer"], [
                    ("Aktif öğrenci (güncel)", aktif),
                    ("Faaliyet yapan öğrenci", oo["faaliyet_yapan_ogrenci"]),
                    ("Katılım oranı", yuzde_metni(katilim)),
                ]),
                ("Öğrenci Mevcudu", ["Durum", "Sayı"], [
                    ("Toplam (güncel)", o["guncel_ogrenci"]["toplam"]),
                    ("Aktif (güncel)", aktif),
                    ("Pasif (güncel)", max(0, o["guncel_ogrenci"]["toplam"] - aktif)),
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

        elif tur == "Faaliyetler":
            kartlar, tablolar = faaliyet_gorunumu(self.veriler.get("faaliyet_rapor"))

        elif tur == "Bakım Gecikmeleri":
            kartlar, tablolar = bakim_gecikme_gorunumu(self.veriler.get("bakim_plani"))

        else:
            self.proje_grafigi.guncelle(
                p["proje_turu_dagilimi"]
            )
            etkinlik_iptal = max(0, po["etkinlik_toplam"] - po["etkinlik_iptal_edilmemis"])
            rez_iptal_orani = iptal_orani({"iptal_edildi": po["rezervasyon_iptal"], "toplam": po["rezervasyon_toplam"]})
            kartlar = [
                ("Cihaz Rezervasyonu", po["rezervasyon_iptal_edilmemis"],
                 "İptal hariç",
                 {"once": pr["rezervasyon_iptal_edilmemis"], "yon": 0}),
                ("İptal Edilen Rezervasyon", po["rezervasyon_iptal"],
                 f"Tüm rezervasyonların {yuzde_metni(rez_iptal_orani)}'i" if rez_iptal_orani is not None else "Seçilen dönem",
                 {"once": pr["rezervasyon_iptal"], "yon": -1}),
                ("Oda Etkinliği", po["etkinlik_iptal_edilmemis"],
                 f"İptal hariç · {etkinlik_iptal} iptal edildi" if etkinlik_iptal else "İptal hariç",
                 {"once": pr["etkinlik_iptal_edilmemis"], "yon": 0}),
                ("Kayıtlı Katılımcı", po["kayitli_katilimci_toplami"],
                 "Girilen sayıların toplamı",
                 {"once": pr["kayitli_katilimci_toplami"], "yon": 1}),
            ]
            alanlar = [
                ("Cihaz rezervasyonu (iptal hariç)", "rezervasyon_iptal_edilmemis"),
                ("İptal edilen rezervasyon", "rezervasyon_iptal"),
                ("Oda etkinliği (iptal hariç)", "etkinlik_iptal_edilmemis"),
                ("Kayıtlı katılımcı", "kayitli_katilimci_toplami"),
            ]
            tablolar = [
                ("Proje Türleri (iptal hariç)", ["Tür", "Rezervasyon"], [
                    (f["tur"], f["rezervasyon_sayisi"])
                    for f in p["proje_turu_dagilimi"]
                ] or [("Dönemde rezervasyon yok.", "")]),
                ("Dönem Karşılaştırması",
                 ["Gösterge", "Seçilen", "Önceki", "Değişim"], [
                     (ad, po[kod], pr[kod], degisim_metni(po[kod], pr[kod])) for ad, kod in alanlar
                 ]),
                ("Rezervasyon Durumu", ["Durum", "Sayı"], [
                    ("Gerçekleşen (iptal hariç)", po["rezervasyon_iptal_edilmemis"]),
                    ("İptal edilen", po["rezervasyon_iptal"]),
                    ("Toplam kayıt", po["rezervasyon_toplam"]),
                ]),
                ("Oda Etkinlikleri", ["Durum", "Sayı"], [
                    ("Gerçekleşen (iptal hariç)", po["etkinlik_iptal_edilmemis"]),
                    ("İptal edilen", etkinlik_iptal),
                    ("Toplam kayıt", po["etkinlik_toplam"]),
                ]),
                ("Önemli Açıklamalar", ["Bilgi"], [
                    ("Sayılarda iptal edilenler hariçtir; iptaller ayrıca gösterilir.",),
                    ("Rezervasyon tamamlanmış deney değildir.",),
                    ("Katılımcı toplamı benzersiz kişi sayısı değildir.",),
                ]),
            ]

        if tur in (
            "Oda Kullanımı", "Cihaz Kullanımı", "Yetkiler",
            "Öğrenci Mevcudu", "Faaliyetler",
            "Bakım Gecikmeleri",
        ):
            self.ek_rapor_grafigi.guncelle(tur, self.veriler)

        for widgetlar, kart in zip(self.kartlar, kartlar):
            ad, deger, alt = kart[:3]
            ek = kart[3] if len(kart) > 3 else {}
            self.karti_doldur(widgetlar, ad, deger, alt, ek)

        # Genel Bakış'ın üç tablosu tek satırda (alttaki üç yuva); diğer görünümler yuvaları sırayla kullanır.
        yuvalar = [2, 3, 4] if tur == "Genel Bakış" else list(range(len(tablolar)))
        for yuva, (ad, sutunlar, satirlar) in zip(yuvalar, tablolar):
            self.tabloyu_doldur(
                self.tablolar[yuva], ad, sutunlar, satirlar
            )

        # Bu görünümde kullanılmayan tablo kartları gizlenir (eski içerik boş kartta kalmasın).
        for sira, (_, tablo_widget) in enumerate(self.tablolar):
            tablo_widget.parentWidget().setVisible(sira in yuvalar)

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
