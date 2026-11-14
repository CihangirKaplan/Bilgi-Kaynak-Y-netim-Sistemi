"""TKYS - Randevu raporunu Excel (.xlsx) dosyasına yazar.

Ekrandan bağımsızdır; sunucudan gelen rapor verisini ve filtre özetini alır. Görünüm cihaz, danışma masası ve puan raporlarıyla aynıdır
(rapor_excel.py'deki renkler ve yardımcılar). Rapor 4 sayfadan oluşur: Özet, Psikolog Bazlı, Dağılımlar, Randevu Detayı.
Danışanlar yalnızca kodla yer alır; iptal notu (serbest metin) rapora konmaz.
"""

from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from rapor_excel import (
    ACIKLAMA_FONT,
    BASLIK_FONT,
    BOLUM_DOLGU,
    BOLUM_FONT,
    TARIH_BICIMI,
    TARIH_SAAT_BICIMI,
    _hucre_yaz,
    _sayfa_olustur,
    _tarih_degeri,
)

DURUM_ETIKETLERI = {"PLANLANDI": "Planlandı", "TAMAMLANDI": "Tamamlandı", "GELMEDI": "Gelmedi", "IPTAL_EDILDI": "İptal Edildi"}
YUZDE = "0.0%"


def _durum(kod):
    return DURUM_ETIKETLERI.get(kod, kod)


def _saat_metni(baslangic, bitis):
    bas, bit = _tarih_degeri(baslangic), _tarih_degeri(bitis)
    if not hasattr(bas, "strftime"):
        return None
    return bas.strftime("%H:%M") + (" – " + bit.strftime("%H:%M") if hasattr(bit, "strftime") else "")


def _ozet_sayfasini_yaz(sayfa, veri, filtre_ozeti):
    sayfa.sheet_view.showGridLines = False
    satir = 1
    ozet = veri.get("ozet", {})

    def yaz(a, b=None, c=None, bicim=None, kalin=False):
        nonlocal satir
        h1 = sayfa.cell(row=satir, column=1, value=a)
        h1.font = BASLIK_FONT if kalin else Font()
        h1.alignment = Alignment(vertical="top", wrap_text=True)
        if b is not None:
            h2 = _hucre_yaz(sayfa, satir, 2, b, bicim)
            h2.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        if c is not None:
            h3 = _hucre_yaz(sayfa, satir, 3, c)
            h3.font = ACIKLAMA_FONT
            h3.alignment = Alignment(vertical="top", wrap_text=True)
        satir += 1

    def bolum(metin):
        nonlocal satir
        satir += 1
        for sutun in (1, 2, 3):
            hucre = sayfa.cell(row=satir, column=sutun, value=metin if sutun == 1 else None)
            hucre.fill = BOLUM_DOLGU
            hucre.font = BOLUM_FONT
        satir += 1

    baslik = sayfa.cell(row=satir, column=1, value="RANDEVU RAPORU")
    baslik.font = Font(bold=True, size=15, color="16294B")
    satir += 1
    alt = sayfa.cell(
        row=satir, column=1,
        value="Bu rapor, sisteme girilmiş randevulardan oluşturulmuştur. Danışanlar yalnızca kodla yer alır; kişisel bilgi içermez. "
              "Randevu randevu ayrıntı için 'Randevu Detayı' sayfasına bakın.",
    )
    alt.font = ACIKLAMA_FONT
    satir += 1

    bolum("RAPOR BİLGİLERİ")
    yaz("Rapor Tarihi", datetime.now(), "Raporun Excel'e aktarıldığı an.", TARIH_SAAT_BICIMI, kalin=True)
    aciklamalar = {
        "Dönem": lambda d: ("Tarih sınırı uygulanmadı; tüm randevular rapora dahil." if d == "Tümü"
                            else "Başlangıç günü bu aralıkta olan randevular rapora dahil edildi."),
        "Psikolog": lambda d: "Tüm psikologların randevuları rapora dahil." if d == "Tümü" else "Rapor yalnızca bu psikologa aittir.",
        "Oda": lambda d: "Tüm odalardaki randevular rapora dahil." if d == "Tümü" else "Rapor yalnızca bu odadaki randevulara aittir.",
    }
    for ad, deger in filtre_ozeti:
        yaz(ad, deger, aciklamalar[ad](deger) if ad in aciklamalar else None, kalin=True)

    bolum("GENEL ÖZET")
    yaz("Toplam randevu", ozet.get("toplam", 0), "Dönemdeki tüm randevular (iptaller dahil).", kalin=True)
    yaz("Planlanmış", ozet.get("planlandi", 0), "Henüz yapılmamış, planlı randevular.", kalin=True)
    yaz("Tamamlanan", ozet.get("tamamlandi", 0), "Seansı yapılan randevular.", kalin=True)
    yaz("Gelmedi", ozet.get("gelmedi", 0), "Danışanın gelmediği randevular.", kalin=True)
    yaz("İptal edilen", ozet.get("iptal_edildi", 0), "İptal nedenleri 'Dağılımlar' sayfasında.", kalin=True)
    yaz("Tamamlanma oranı", ozet.get("tamamlanma_orani"), "Tamamlanan / (Tamamlanan + Gelmedi). Planlı ve iptal edilenler hesaba katılmaz.",
        YUZDE, kalin=True)
    yaz("Gelmeme oranı", ozet.get("gelmeme_orani"), "Gelmedi / (Tamamlanan + Gelmedi).", YUZDE, kalin=True)
    yaz("Farklı danışan", ozet.get("danisan_sayisi", 0), "Dönemde randevusu olan danışan sayısı (kodlarla).", kalin=True)

    bolum("SAYFA REHBERİ")
    for ad, aciklama in [
        ("Psikolog Bazlı", "Her psikolog için randevu sayıları ve durum dağılımı."),
        ("Dağılımlar", "İptal nedenleri; görüşme tipi, terapi türü ve yaş grubu dağılımı (iptal edilenler hariç)."),
        ("Randevu Detayı", "Tüm randevular, randevu randevu: tarih, saat, danışan kodu, psikolog, oda, görüşme, terapi, durum."),
    ]:
        yaz(ad, None, aciklama, kalin=True)

    sayfa.column_dimensions["A"].width = 30
    sayfa.column_dimensions["B"].width = 28
    sayfa.column_dimensions["C"].width = 90


def _dagilim_satirlari(veri):
    satirlar = []
    for baslik, liste in (
        ("İptal nedeni (iptal edilenler)", veri.get("iptal_nedenleri", [])),
        ("Görüşme tipi (iptal edilenler hariç)", veri.get("dagilimlar", {}).get("gorusme_tipi", [])),
        ("Terapi türü (iptal edilenler hariç)", veri.get("dagilimlar", {}).get("terapi_turu", [])),
        ("Yaş grubu (iptal edilenler hariç)", veri.get("dagilimlar", {}).get("yas_grubu", [])),
    ):
        for oge in liste:
            satirlar.append([baslik, oge.get("etiket"), oge.get("sayi", 0), oge.get("pay")])
    return satirlar


def excel_dosyasi_olustur(veri, filtre_ozeti, dosya_yolu):
    """Rapor verisini 4 sayfalı .xlsx dosyası olarak kaydeder.

    veri: GET /api/randevu-raporu?detay=true yanıtı
    filtre_ozeti: [(ad, değer)] biçiminde ekrandaki filtreler
    """
    kitap = Workbook()
    ozet_sayfasi = kitap.active
    ozet_sayfasi.title = "Özet"
    _ozet_sayfasini_yaz(ozet_sayfasi, veri, filtre_ozeti)

    _sayfa_olustur(
        kitap, "Psikolog Bazlı",
        [("Psikolog", None), ("Toplam", None), ("Planlanmış", None), ("Tamamlanan", None), ("Gelmedi", None), ("İptal Edilen", None),
         ("Tamamlanma Oranı", YUZDE)],
        [
            [p.get("ad"), p.get("toplam", 0), p.get("planlandi", 0), p.get("tamamlandi", 0), p.get("gelmedi", 0), p.get("iptal_edildi", 0),
             round(p["tamamlandi"] / (p["tamamlandi"] + p["gelmedi"]), 4) if (p.get("tamamlandi", 0) + p.get("gelmedi", 0)) else None]
            for p in veri.get("psikologlar", [])
        ],
    )

    _sayfa_olustur(
        kitap, "Dağılımlar",
        [("Başlık", None), ("Değer", None), ("Randevu Sayısı", None), ("Payı", YUZDE)],
        _dagilim_satirlari(veri),
    )

    _sayfa_olustur(
        kitap, "Randevu Detayı",
        [("Randevu ID", None), ("Tarih", TARIH_BICIMI), ("Saat", None), ("Danışan Kodu", None), ("Psikolog", None), ("Oda", None),
         ("Görüşme", None), ("Terapi", None), ("Yaş Grubu", None), ("Durum", None), ("İptal Nedeni", None)],
        [
            [r.get("randevu_id"), _tarih_degeri(r.get("baslangic_zamani")), _saat_metni(r.get("baslangic_zamani"), r.get("bitis_zamani")),
             r.get("danisan_kod_id"), r.get("psikolog"), r.get("oda"), r.get("gorusme_tipi"), r.get("terapi_turu"), r.get("yas_grubu"),
             _durum(r.get("durum")), r.get("iptal_nedeni")]
            for r in veri.get("randevular", [])
        ],
    )

    kitap.save(dosya_yolu)
