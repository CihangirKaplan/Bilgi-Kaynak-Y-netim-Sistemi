"""TKYS - Ortak Excel (.xlsx) rapor oluşturucu.

Cihaz, danışma masası, puan ve randevu raporlarıyla aynı görünümü kullanır (rapor_excel.py'deki renkler ve yardımcılar).
Her rapor: 'Özet' sayfası (rapor bilgileri, genel özet, sayfa rehberi) + istenen sayıda tablo sayfasından oluşur.
Metin hücreleri formül olarak yorumlanmaz (formül enjeksiyonuna karşı _hucre_yaz kullanılır).
"""
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from client.rapor_excel import (
    yazdirma_hazirla,
    birim_bicimi,
    ozet_bicimi,
    ACIKLAMA_FONT,
    BASLIK_FONT,
    BOLUM_DOLGU,
    BOLUM_FONT,
    TARIH_SAAT_BICIMI,
    _hucre_yaz,
    _sayfa_olustur,
)


# Raporlardaki sayı satırlarının birimi (rapor başlığına göre): "13" yerine "13 cihaz" görünsün; hücre yine sayıdır.
GENEL_BIRIMLER = {
    "ÖĞRENCİ RAPORU": {"Toplam öğrenci": "öğrenci", "Yeni kayıt (son 30 gün)": "öğrenci", "Saklama süresi dolmuş": "öğrenci",
                       "Saklama süresi ertelenen": "öğrenci", "Saklama süresi yaklaşan": "öğrenci", "Faaliyetsiz aktif öğrenci": "öğrenci"},
    "FAALİYET RAPORU": {"Faaliyet kaydı": "kayıt", "Faaliyet miktarı": "adet", "Toplam puan": "puan", "Faaliyet yapan öğrenci": "öğrenci",
                        "Kayıt başına ortalama puan": "puan"},
    "GECİKEN BAKIM PLANI RAPORU": {"Aktif plan": "plan", "Geciken plan": "plan", "Ortalama gecikme": "gün", "En çok gecikme": "gün",
                                   "Yaklaşan plan": "plan", "Planı olmayan cihaz": "cihaz"},
    "CİHAZ REZERVASYON RAPORU": {"Rezervasyon sayısı": "rezervasyon", "Toplam kullanım": "saat", "Ortalama süre": "saat",
                                 "İptal edilen rezervasyon": "rezervasyon", "Kullanılan cihaz": "cihaz", "Hiç kullanılmayan cihaz": "cihaz"},
    "ODA KULLANIM RAPORU": {"Toplam kullanım": "saat", "Randevu": "saat", "Cihaz rezervasyonu": "saat", "Etkinlik": "saat",
                            "Kullanılan oda": "oda", "Hiç kullanılmayan aktif oda": "oda"},
    "DENETİM KAYITLARI RAPORU": {"Toplam kayıt (süzgeçle)": "kayıt", "Dosyadaki kayıt": "kayıt", "Başarısız giriş": "giriş",
                                 "Kullanıcı işlemleri": "işlem", "Bugünkü işlemler": "işlem", "Silme işlemi (dosyada)": "işlem"},
}
LISTE_BIRIMLERI = {"Aktarılan Kayıt": "kayıt"}                        # liste sayfalarının tek özet satırı


def _ozet_sayfasini_yaz(sayfa, baslik, aciklama, filtre_ozeti, ozet_satirlari, sayfa_rehberi):
    sayfa.sheet_view.showGridLines = False
    satir = 1
    birimler = {**LISTE_BIRIMLERI, **GENEL_BIRIMLER.get(baslik, {})}

    def yaz(a, b=None, c=None, bicim=None, kalin=False):
        nonlocal satir
        h1 = sayfa.cell(row=satir, column=1, value=a)
        h1.font = BASLIK_FONT if kalin else Font()
        h1.alignment = Alignment(vertical="top", wrap_text=True)
        if b is not None:
            h2 = _hucre_yaz(sayfa, satir, 2, b, ozet_bicimi(birimler, a, b, bicim))
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

    ust = sayfa.cell(row=satir, column=1, value=baslik)
    ust.font = Font(bold=True, size=15, color="16294B")
    satir += 1
    alt = sayfa.cell(row=satir, column=1, value=aciklama)
    alt.font = ACIKLAMA_FONT
    satir += 1

    bolum("RAPOR BİLGİLERİ")
    yaz("Rapor Tarihi", datetime.now(), "Raporun oluşturulduğu an.", TARIH_SAAT_BICIMI, kalin=True)
    for ad, deger in filtre_ozeti:
        aciklama_metni = None
        if ad == "Arama":                                                  # liste sayfalarının arama kutusu: 'Yok' yerine ne olduğu açıkça yazılır
            deger, aciklama_metni = (("Uygulanmadı", "Arama kutusu boştu; ekrandaki tüm kayıtlar listelendi.") if deger in ("Yok", "", None)
                                     else (deger, "Yalnızca bu aramaya uyan kayıtlar listelendi."))
        yaz(ad, deger, aciklama_metni, kalin=True)

    bolum("GENEL ÖZET")
    for ad, deger, aciklama_metni, *bicim in ozet_satirlari:
        yaz(ad, deger, aciklama_metni, bicim[0] if bicim else None, kalin=True)

    bolum("SAYFA REHBERİ")
    for ad, aciklama_metni in sayfa_rehberi:
        yaz(ad, None, aciklama_metni, kalin=True)

    sayfa.column_dimensions["A"].width = 32
    sayfa.column_dimensions["B"].width = 30
    sayfa.column_dimensions["C"].width = 90


def excel_olustur(dosya_yolu, baslik, aciklama, filtre_ozeti, ozet_satirlari, sayfalar):
    """Raporu .xlsx dosyası olarak kaydeder.

    filtre_ozeti: [(ad, değer)]; ozet_satirlari: [(ad, değer, açıklama[, sayı biçimi])];
    sayfalar: [(sayfa adı, [(sütun başlığı, sayı biçimi)], satırlar, rehber açıklaması)]
    """
    kitap = Workbook()
    ozet = kitap.active
    ozet.title = "Özet"
    _ozet_sayfasini_yaz(ozet, baslik, aciklama, filtre_ozeti, ozet_satirlari, [(s[0], s[3]) for s in sayfalar])
    for ad, kolonlar, satirlar, _ in sayfalar:
        _sayfa_olustur(kitap, ad, kolonlar, satirlar)
    yazdirma_hazirla(kitap)
    kitap.save(dosya_yolu)
