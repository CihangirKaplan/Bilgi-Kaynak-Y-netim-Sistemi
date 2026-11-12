"""TKYS - Danışma masası raporunu Excel (.xlsx) dosyasına yazar.

Ekrandan bağımsızdır; API'den gelen rapor verisini ve filtre özetini alır. Görünüm cihaz raporuyla
aynıdır (rapor_excel.py'deki renkler, başlıklar ve yardımcılar kullanılır).
Rapor 3 sayfadan oluşur: Özet, Görev Kayıtları, Öğrenci Bazlı.
"""

from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from rapor_excel import (
    ACIKLAMA_FONT,
    BASLIK_FONT,
    BOLUM_DOLGU,
    BOLUM_FONT,
    TARIH_SAAT_BICIMI,
    _hucre_yaz,
    _sayfa_olustur,
    _tarih_degeri,
)

SAAT_BICIMI = '0.00 "saat"'

OGRENCI_AKTIF = "Aktif"
OGRENCI_PASIF = "Pasif"
OGRENCI_BILINMIYOR = "Bilinmiyor"

GOREV_DEVAM = "Devam ediyor"
GOREV_BITTI = "Tamamlandı"
ONAY_YOK = "—"
ONAY_BEKLIYOR = "Onay bekliyor"
ONAY_ONAYLANDI = "Onaylandı"


def _saat(saniye):
    """Saniyeyi ondalık saate çevirir (Excel'de toplanabilir/sıralanabilir olsun diye sayı)."""
    return round(max(0, int(saniye or 0)) / 3600, 2)


def _ogrenci_durumu(aktif):
    if aktif is None:
        return OGRENCI_BILINMIYOR
    return OGRENCI_AKTIF if aktif else OGRENCI_PASIF


def _gorev_durumu(oturum):
    return GOREV_BITTI if oturum.get("bitis_zamani") else GOREV_DEVAM


def _onay_durumu(oturum):
    if not oturum.get("bitis_zamani"):
        return ONAY_YOK
    return ONAY_ONAYLANDI if oturum.get("onaylandi_mi") else ONAY_BEKLIYOR


def _ozet_sayfasini_yaz(sayfa, veri, filtre_ozeti):
    sayfa.sheet_view.showGridLines = False
    satir = 1
    ozet = veri.get("ozet", {})
    ogrenciler = veri.get("ogrenci_ozetleri", [])
    oturumlar = veri.get("oturumlar", [])

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

    baslik = sayfa.cell(row=satir, column=1, value="DANIŞMA MASASI RAPORU — Görevler ve Çalışma Süreleri")
    baslik.font = Font(bold=True, size=15, color="16294B")
    satir += 1
    alt = sayfa.cell(
        row=satir, column=1,
        value="Bu rapor, danışma masasında öğrencilerin başlattığı ve bitirdiği görev kayıtlarından oluşturulmuştur. "
              "Kayıt kayıt ayrıntı için 'Görev Kayıtları', öğrenci toplamları için 'Öğrenci Bazlı' sayfasına bakın.",
    )
    alt.font = ACIKLAMA_FONT
    satir += 1

    # ---- Rapor bilgileri ----
    bolum("RAPOR BİLGİLERİ")
    yaz("Rapor Tarihi", datetime.now(), "Raporun Excel'e aktarıldığı an.", TARIH_SAAT_BICIMI, kalin=True)
    for ad, deger in filtre_ozeti:
        if ad == "Dönem":
            aciklama = (
                "Tarih sınırı uygulanmadı; kayıtlı tüm dönemler rapora dahil." if deger == "Tümü"
                else "Başlangıç zamanı bu tarihler arasında olan görevler rapora dahil edildi."
            )
        elif ad == "Öğrenci":
            aciklama = (
                "Belirli bir öğrenci seçilmedi; görev kaydı olan tüm öğrenciler rapora dahil."
                if deger == "Tüm Öğrenciler"
                else "Rapor yalnızca bu öğrenciye aittir."
            )
        else:
            aciklama = None
        yaz(ad, deger, aciklama, kalin=True)
    yaz("Rapordaki öğrenciler", len(ogrenciler), "Seçilen dönemde en az bir görev kaydı olan öğrenci sayısı.", kalin=True)

    # ---- Görevler ----
    bolum("GÖREVLER")
    yaz("Toplam görev", ozet.get("toplam_gorev", len(oturumlar)), "Seçilen dönemde başlatılan tüm görevler.", kalin=True)
    yaz("Devam eden", ozet.get("devam_eden", 0), "Henüz bitirilmemiş görevler; süreleri toplamlara katılmaz.", kalin=True)
    yaz("Tamamlanan", ozet.get("tamamlanan", 0), "Bitiş zamanı girilmiş görevler.", kalin=True)
    yaz("Onay bekleyen", ozet.get("onay_bekleyen", 0), "Tamamlanmış ama henüz onaylanmamış görevler.", kalin=True)
    yaz("Onaylanan", ozet.get("onaylanan", 0), "Yetkili tarafından onaylanmış görevler.", kalin=True)

    # ---- Çalışma süresi ----
    bolum("ÇALIŞMA SÜRESİ")
    toplam = _saat(ozet.get("toplam_calisma_saniye", 0))
    onayli = _saat(ozet.get("onaylanan_calisma_saniye", 0))
    yaz("Toplam çalışma süresi", toplam, "Tamamlanan görevlerin sürelerinin toplamı.", SAAT_BICIMI, kalin=True)
    yaz("Onaylı çalışma süresi", onayli, "Yalnızca onaylanan görevlerin sürelerinin toplamı.", SAAT_BICIMI, kalin=True)
    yaz("Onay bekleyen süre", round(toplam - onayli, 2), "Tamamlanmış ama henüz onaylanmamış görevlerin süresi.",
        SAAT_BICIMI, kalin=True)
    tamamlanan = ozet.get("tamamlanan", 0)
    if tamamlanan:
        yaz("Ortalama görev süresi", round(toplam / tamamlanan, 2), "Toplam sürenin tamamlanan görev sayısına bölümü.",
            SAAT_BICIMI, kalin=True)

    # ---- Öğrenci durumu ----
    pasifler = [o for o in ogrenciler if o.get("aktif_mi") is False]
    bolum("ÖĞRENCİ DURUMU")
    yaz("Aktif öğrenci", sum(1 for o in ogrenciler if o.get("aktif_mi")),
        "Raporda yer alan ve hesabı aktif olan öğrenciler.", kalin=True)
    yaz("Pasif öğrenci", len(pasifler),
        ", ".join(f"{o['ad_soyad']} ({o['ogrenci_numarasi']})" for o in pasifler)
        or "Raporda pasif öğrenci yok.", kalin=True)
    yaz("Not", None, "Pasif öğrencilerin geçmiş görev kayıtları silinmez; raporda 'Pasif' olarak işaretlenerek yer alır.")

    # ---- Sayfa rehberi ----
    bolum("SAYFA REHBERİ")
    for ad, aciklama in [
        ("Görev Kayıtları", "Her görev için bir satır: öğrenci, başlangıç/bitiş, süre, görev ve onay durumu."),
        ("Öğrenci Bazlı", "Her öğrenci için tek satır: görev sayıları, toplam ve onaylı çalışma süresi, öğrenci durumu."),
    ]:
        yaz(ad, None, aciklama, kalin=True)

    sayfa.column_dimensions["A"].width = 34
    sayfa.column_dimensions["B"].width = 26
    sayfa.column_dimensions["C"].width = 90


def excel_dosyasi_olustur(veri, filtre_ozeti, dosya_yolu):
    """Rapor verisini 3 sayfalı .xlsx dosyası olarak kaydeder.

    veri: GET /api/danisma/raporlar yanıtı
    filtre_ozeti: [(ad, değer)] biçiminde ekrandaki filtreler
    """
    kitap = Workbook()
    ozet_sayfasi = kitap.active
    ozet_sayfasi.title = "Özet"
    _ozet_sayfasini_yaz(ozet_sayfasi, veri, filtre_ozeti)

    _sayfa_olustur(
        kitap,
        "Görev Kayıtları",
        [("Öğrenci", None), ("Öğrenci No", None), ("Öğrenci Durumu", None),
         ("Başlangıç", TARIH_SAAT_BICIMI), ("Bitiş", TARIH_SAAT_BICIMI),
         ("Çalışma Süresi", SAAT_BICIMI), ("Görev Durumu", None), ("Onay Durumu", None)],
        [
            [
                o.get("ad_soyad"),
                o.get("ogrenci_numarasi"),
                _ogrenci_durumu(o.get("ogrenci_aktif_mi")),
                _tarih_degeri(o.get("baslangic_zamani")),
                _tarih_degeri(o.get("bitis_zamani")),
                _saat(o.get("toplam_saniye")) if o.get("bitis_zamani") else None,
                _gorev_durumu(o),
                _onay_durumu(o),
            ]
            for o in veri.get("oturumlar", [])
        ],
    )

    _sayfa_olustur(
        kitap,
        "Öğrenci Bazlı",
        [("Öğrenci", None), ("Öğrenci No", None), ("Öğrenci Durumu", None), ("Toplam Görev", None),
         ("Devam Eden", None), ("Onay Bekleyen", None), ("Onaylanan", None),
         ("Toplam Süre", SAAT_BICIMI), ("Onaylı Süre", SAAT_BICIMI)],
        [
            [
                o.get("ad_soyad"),
                o.get("ogrenci_numarasi"),
                _ogrenci_durumu(o.get("aktif_mi")),
                o.get("toplam_gorev", 0),
                o.get("devam_eden", 0),
                o.get("onay_bekleyen", 0),
                o.get("onaylanan", 0),
                _saat(o.get("toplam_saniye")),
                _saat(o.get("onaylanan_saniye")),
            ]
            for o in veri.get("ogrenci_ozetleri", [])
        ],
    )

    kitap.save(dosya_yolu)
