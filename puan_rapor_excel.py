"""TKYS - Öğrenci puan raporunu Excel (.xlsx) dosyasına yazar.

Ekrandan bağımsızdır; API'den gelen rapor verisini ve filtre özetini alır. Görünüm cihaz ve danışma masası
raporlarıyla aynıdır (rapor_excel.py'deki renkler, başlıklar ve yardımcılar kullanılır).
Rapor 4 sayfadan oluşur: Özet, Puan Sıralaması, Faaliyet Dağılımı, Faaliyet Detayı.
"""

from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from rapor_excel import (
    ACIKLAMA_FONT,
    BASLIK_FONT,
    BOLUM_DOLGU,
    BOLUM_FONT,
    TARIH_BICIMI,
    TARIH_SAAT_BICIMI,
    UYARI_FONT,
    _hucre_yaz,
    _sayfa_olustur,
    _tarih_degeri,
)

OGRENCI_AKTIF = "Aktif"
OGRENCI_PASIF = "Pasif"
SIRASIZ = "—"                 # puanı olmayan öğrencinin sırası yoktur

# İlk üç sıra açık renkle vurgulanır (altın, gümüş, bronz).
SIRA_DOLGULARI = {
    1: PatternFill("solid", fgColor="FFF2B8"),
    2: PatternFill("solid", fgColor="E9EDF3"),
    3: PatternFill("solid", fgColor="F7DCC2"),
}


def _sayi(deger):
    """Tam sayıysa int, değilse sayı olarak bırakır (Excel'de '12.' görünmesin)."""
    if deger is None:
        return 0
    deger = float(deger)
    return int(deger) if deger == int(deger) else round(deger, 2)


def _durum(aktif):
    return OGRENCI_AKTIF if aktif else OGRENCI_PASIF


def _sira(ogrenci):
    sira = ogrenci.get("sira")
    return sira if sira is not None else SIRASIZ


def _ozet_sayfasini_yaz(sayfa, veri, filtre_ozeti):
    sayfa.sheet_view.showGridLines = False
    satir = 1
    ozet = veri.get("ozet", {})
    ogrenciler = veri.get("ogrenciler", [])

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

    baslik = sayfa.cell(row=satir, column=1, value="PUAN RAPORU — Öğrenci Faaliyet Puanları")
    baslik.font = Font(bold=True, size=15, color="16294B")
    satir += 1
    alt = sayfa.cell(
        row=satir, column=1,
        value="Bu rapor, öğrencilerin sisteme girilmiş faaliyet kayıtlarından oluşturulmuştur. Öğrenciler toplam puana göre "
              "en yüksekten en düşüğe sıralanır. Kayıt kayıt ayrıntı için 'Faaliyet Detayı' sayfasına bakın.",
    )
    alt.font = ACIKLAMA_FONT
    satir += 1

    # ---- Rapor bilgileri ----
    bolum("RAPOR BİLGİLERİ")
    yaz("Rapor Tarihi", datetime.now(), "Raporun Excel'e aktarıldığı an.", TARIH_SAAT_BICIMI, kalin=True)
    aciklamalar = {
        "Dönem": lambda d: ("Tarih sınırı uygulanmadı; kayıtlı tüm faaliyetler rapora dahil." if d == "Tümü"
                            else "Faaliyet tarihi bu aralıkta olan kayıtlar rapora dahil edildi."),
        "Öğrenci Türü": lambda d: ("Tüm öğrenci türleri rapora dahil." if d == "Tümü"
                                   else "Rapor yalnızca bu türdeki öğrencilere aittir."),
        "Öğrenci Durumu": lambda d: ("Aktif ve pasif tüm öğrenciler rapora dahil." if d == "Tümü"
                                     else "Rapor yalnızca bu durumdaki öğrencilere aittir."),
        "Puanı Olmayanlar": lambda d: ("Dönemde hiç faaliyeti olmayan öğrenciler de listelenir (sırasız)."
                                       if d == "Gösterilir" else "Dönemde faaliyeti olmayan öğrenciler listelenmedi."),
    }
    for ad, deger in filtre_ozeti:
        yaz(ad, deger, aciklamalar[ad](deger) if ad in aciklamalar else None, kalin=True)

    # ---- Genel özet ----
    bolum("GENEL ÖZET")
    yaz("Listelenen öğrenci", ozet.get("ogrenci_sayisi", len(ogrenciler)), "Bu raporda yer alan öğrenci sayısı.", kalin=True)
    yaz("Puanı olan öğrenci", ozet.get("puanli_ogrenci_sayisi", 0), "Dönemde en az bir puanlı faaliyeti olanlar.", kalin=True)
    yaz("Faaliyet kaydı", ozet.get("faaliyet_kaydi_sayisi", 0), "Dönemde girilen toplam faaliyet kaydı.", kalin=True)
    yaz("Toplam puan", _sayi(ozet.get("toplam_puan", 0)), "Listelenen tüm öğrencilerin puanlarının toplamı.", kalin=True)
    yaz("Ortalama puan", _sayi(ozet.get("ortalama_puan", 0)), "Puanı olan öğrencilerin ortalaması (puansızlar hesaba katılmaz).",
        kalin=True)
    yaz("En yüksek puan", _sayi(ozet.get("en_yuksek_puan", 0)),
        ", ".join(ozet.get("en_yuksek_ogrenciler", [])) or "Puanı olan öğrenci yok.", kalin=True)

    # ---- İlk üç ----
    ilk_uc = [o for o in ogrenciler if o.get("sira") is not None and o["sira"] <= 3]
    bolum("İLK ÜÇ (eşit puanlılar aynı sırayı paylaşır)")
    if ilk_uc:
        for o in ilk_uc:
            yaz(f"{o['sira']}. sıra", _sayi(o["toplam_puan"]),
                f"{o['ad_soyad']} ({o['ogrenci_numarasi']})" + ("" if o.get("aktif_mi", True) else " — pasif öğrenci"),
                kalin=True)
    else:
        yaz("Sıralama", None, "Bu raporda puanı olan öğrenci yok.")

    # ---- Pasif öğrenciler ----
    pasifler = [o for o in ogrenciler if o.get("aktif_mi") is False]
    bolum("ÖĞRENCİ DURUMU")
    yaz("Aktif öğrenci", sum(1 for o in ogrenciler if o.get("aktif_mi")), "Raporda yer alan ve hesabı aktif olan öğrenciler.",
        kalin=True)
    yaz("Pasif öğrenci", len(pasifler),
        ", ".join(f"{o['ad_soyad']} ({o['ogrenci_numarasi']})" for o in pasifler) or "Raporda pasif öğrenci yok.", kalin=True)
    yaz("Not", None, "Pasif öğrencilerin geçmiş puanları silinmez; sıralamada 'Pasif' olarak işaretlenerek yer alır.")

    # ---- Puan nasıl hesaplanır ----
    bolum("PUAN NASIL HESAPLANIR")
    yaz("Formül", "Miktar × Faaliyet puanı",
        "Her kayıt, girildiği andaki faaliyet puanıyla hesaplanır; sonradan değişen faaliyet puanı eski kayıtları etkilemez.",
        kalin=True)
    yaz("Sıralama", "Toplam puan, yüksekten düşüğe", "Eşit puanlılar aynı sırayı alır (1, 2, 2, 4 gibi). Puanı olmayanın sırası yoktur.",
        kalin=True)

    # ---- Sayfa rehberi ----
    bolum("SAYFA REHBERİ")
    for ad, aciklama in [
        ("Puan Sıralaması", "Her öğrenci için tek satır: sıra, toplam puan, faaliyet sayısı, son faaliyet tarihi, öğrenci durumu."),
        ("Faaliyet Dağılımı", "Hangi faaliyetten kaç kayıt girilmiş ve ne kadar puan getirmiş."),
        ("Faaliyet Detayı", "Tüm faaliyet kayıtları, kayıt kayıt: öğrenci, tarih, faaliyet, miktar ve puan."),
    ]:
        yaz(ad, None, aciklama, kalin=True)

    sayfa.column_dimensions["A"].width = 34
    sayfa.column_dimensions["B"].width = 26
    sayfa.column_dimensions["C"].width = 90


def _faaliyet_dagilimi(detaylar):
    """Faaliyet adına göre: kayıt sayısı, katılan öğrenci sayısı, toplam puan, puan payı."""
    gruplar = {}
    for d in detaylar:
        g = gruplar.setdefault(d["faaliyet"], {"kayit": 0, "ogrenciler": set(), "puan": 0.0})
        g["kayit"] += 1
        g["ogrenciler"].add(d["ogrenci_id"])
        g["puan"] += float(d.get("toplam_puan") or 0)
    genel = sum(g["puan"] for g in gruplar.values())
    sirali = sorted(gruplar.items(), key=lambda kv: (-kv[1]["puan"], kv[0].casefold()))
    return [
        [ad, g["kayit"], len(g["ogrenciler"]), _sayi(g["puan"]), (g["puan"] / genel) if genel else 0]
        for ad, g in sirali
    ]


def excel_dosyasi_olustur(veri, filtre_ozeti, dosya_yolu):
    """Rapor verisini 4 sayfalı .xlsx dosyası olarak kaydeder.

    veri: GET /api/puan-raporu?detay=true yanıtı
    filtre_ozeti: [(ad, değer)] biçiminde ekrandaki filtreler
    """
    ogrenciler = veri.get("ogrenciler", [])
    detaylar = veri.get("detaylar", [])
    ogrenci_bilgisi = {o["ogrenci_id"]: o for o in ogrenciler}
    siralama = {o["ogrenci_id"]: i for i, o in enumerate(ogrenciler)}

    kitap = Workbook()
    ozet_sayfasi = kitap.active
    ozet_sayfasi.title = "Özet"
    _ozet_sayfasini_yaz(ozet_sayfasi, veri, filtre_ozeti)

    sira_sayfasi = _sayfa_olustur(
        kitap,
        "Puan Sıralaması",
        [("Sıra", None), ("Öğrenci", None), ("Öğrenci No", None), ("Öğrenci Türü", None), ("Öğrenci Durumu", None),
         ("Faaliyet Sayısı", None), ("Toplam Puan", None), ("Faaliyet Başına Ortalama Puan", None),
         ("Son Faaliyet Tarihi", TARIH_BICIMI)],
        [
            [
                _sira(o), o.get("ad_soyad"), o.get("ogrenci_numarasi"), o.get("tur_etiketi") or o.get("tur"),
                _durum(o.get("aktif_mi")), o.get("faaliyet_sayisi", 0), _sayi(o.get("toplam_puan")),
                round(float(o.get("toplam_puan") or 0) / o["faaliyet_sayisi"], 2) if o.get("faaliyet_sayisi") else None,
                _tarih_degeri(o.get("son_faaliyet_tarihi")),
            ]
            for o in ogrenciler
        ],
    )
    for satir_no, o in enumerate(ogrenciler, start=2):
        dolgu = SIRA_DOLGULARI.get(o.get("sira"))
        if dolgu is not None:
            for hucre in sira_sayfasi[satir_no]:
                hucre.fill = dolgu
        if not o.get("aktif_mi", True):
            sira_sayfasi.cell(row=satir_no, column=5).font = UYARI_FONT

    _sayfa_olustur(
        kitap,
        "Faaliyet Dağılımı",
        [("Faaliyet", None), ("Kayıt Sayısı", None), ("Katılan Öğrenci", None), ("Toplam Puan", None),
         ("Toplam İçindeki Payı", "0.0%")],
        _faaliyet_dagilimi(detaylar),
    )

    _sayfa_olustur(
        kitap,
        "Faaliyet Detayı",
        [("Sıra", None), ("Öğrenci", None), ("Öğrenci No", None), ("Öğrenci Durumu", None), ("Tarih", TARIH_BICIMI),
         ("Faaliyet", None), ("Miktar", None), ("Birim", None), ("Birim Puan", None), ("Toplam Puan", None)],
        [
            [
                _sira(ogrenci_bilgisi.get(d["ogrenci_id"], {})),
                ogrenci_bilgisi.get(d["ogrenci_id"], {}).get("ad_soyad"),
                ogrenci_bilgisi.get(d["ogrenci_id"], {}).get("ogrenci_numarasi"),
                _durum(ogrenci_bilgisi.get(d["ogrenci_id"], {}).get("aktif_mi")),
                _tarih_degeri(d.get("tarih")),
                d.get("faaliyet"), d.get("adet"), d.get("birim") or None,
                _sayi(d.get("birim_puan")), _sayi(d.get("toplam_puan")),
            ]
            for d in sorted(detaylar, key=lambda d: siralama.get(d["ogrenci_id"], len(siralama)))
        ],
    )

    kitap.save(dosya_yolu)
