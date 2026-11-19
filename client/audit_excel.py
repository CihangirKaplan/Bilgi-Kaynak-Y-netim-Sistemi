"""TKYS - Denetim (audit) kayıtlarını Excel (.xlsx) dosyasına yazar (rapor_excel_genel.py'deki ortak görünümle)."""
from client.audit_kayitlari_ekrani import HEDEF_TABLO_ADLARI, OLAY_ADLARI, ayrinti_satirlari
from client.rapor_excel import TARIH_SAAT_BICIMI, _tarih_degeri
from client.rapor_excel_genel import excel_olustur

EN_FAZLA_KAYIT = 20000          # tek dosyada en çok bu kadar kayıt (Excel ve bellek için makul sınır)


def ayrinti_metni(ayrinti):
    """Silinen veri / önceki-yeni değerler: 'Alan: değer; Alan: değer'."""
    return "; ".join(f"{alan}: {deger}" for alan, deger in ayrinti_satirlari(ayrinti)) or None


def audit_excel_olustur(dosya_yolu, kayitlar, ozet, filtre_ozeti, kesildi=False):
    """kayitlar: GET /api/audit-kayitlari 'kayitlar' öğeleri; ozet: aynı yanıtın 'ozet'i; kesildi: kayıt sınırı aşıldı mı."""
    satirlar = [
        [
            k.get("denetim_id"),
            _tarih_degeri(k.get("olusturulma_tarihi")),
            k.get("kullanici_adi"),
            OLAY_ADLARI.get(k.get("olay_turu"), k.get("olay_turu")),
            HEDEF_TABLO_ADLARI.get(k.get("hedef_tablo"), k.get("hedef_tablo")),
            k.get("hedef_kayit_id"),
            k.get("hedef_kullanici_adi"),
            ayrinti_metni(k.get("ayrinti")),
        ]
        for k in kayitlar
    ]
    silmeler = [s for s, k in zip(satirlar, kayitlar) if k.get("olay_turu") == "DELETE"]
    excel_olustur(
        dosya_yolu, "DENETİM KAYITLARI RAPORU",
        "Bu rapor, sistemde kaydedilen işlemlerin (giriş, oluşturma, güncelleme, silme vb.) denetim izlerinden oluşturulmuştur. "
        "Denetim kayıtları sonradan değiştirilemez. Parola ya da kişisel veri içermez; silinen öğrenci kayıtlarında yalnızca "
        "kimliksiz alanlar yer alır."
        + (f" Dosya, en yeni {EN_FAZLA_KAYIT} kayıtla sınırlandırılmıştır; süzgeçle daraltabilirsiniz." if kesildi else ""),
        filtre_ozeti,
        [
            ("Toplam kayıt (süzgeçle)", ozet.get("toplam_kayit", 0), "Süzgece uyan tüm kayıtlar."),
            ("Dosyadaki kayıt", len(kayitlar), "Bu Excel dosyasına yazılan kayıt sayısı."),
            ("Başarısız giriş", ozet.get("basarisiz_giris", 0), "Başarısız giriş denemeleri."),
            ("Kullanıcı işlemleri", ozet.get("kullanici_islemleri", 0), "Oluşturma, güncelleme, rol değişikliği ve silme işlemleri."),
            ("Bugünkü işlemler", ozet.get("bugunku_islemler", 0), "Bugün yapılan işlemler."),
            ("Silme işlemi (dosyada)", len(silmeler), "Kalıcı silmeler; silinen verinin içeriği 'Ayrıntı' sütunundadır."),
        ],
        [
            ("Denetim Kayıtları",
             [("Kayıt ID", None), ("Tarih / Saat", TARIH_SAAT_BICIMI), ("İşlemi Yapan", None), ("İşlem Türü", None), ("Hedef", None),
              ("Hedef Kayıt ID", None), ("İşlem Yapılan Kullanıcı", None), ("Ayrıntı", None)],
             satirlar, "Tüm denetim kayıtları, en yeniden eskiye."),
            ("Silmeler",
             [("Kayıt ID", None), ("Tarih / Saat", TARIH_SAAT_BICIMI), ("İşlemi Yapan", None), ("İşlem Türü", None), ("Hedef", None),
              ("Hedef Kayıt ID", None), ("İşlem Yapılan Kullanıcı", None), ("Silinen Veri / Ayrıntı", None)],
             silmeler, "Yalnızca kalıcı silmeler ve silinen verinin içeriği."),
        ],
    )
