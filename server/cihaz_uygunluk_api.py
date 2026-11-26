"""Cihaz Uygunluğu takvimi ucu (salt okunur). `server/sunucu.py` içinden ayrıldı."""
from datetime import date
from datetime import datetime
from datetime import timedelta

from fastapi import APIRouter, HTTPException

from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla


# Cihaz Uygunluğu sayfasının verisi. Yalnızca "ne zaman, ne yüzden uygun değil" bilgisini verir:
# kişi adı, rezervasyonu yapan, işlem açıklaması, maliyet, sertifika no gibi ayrıntılar bilerek
# DÖNMEZ; bu yüzden yalnızca CIHAZ_UYGUNLUK_GORUNTULE izni yeterlidir.
UYGUNLUK_EN_FAZLA_GUN = 62
UYGUNLUK_ACIK_UCLU_DURUMLAR = {          # cihazın şu anki durumundan türeyen, bitişi belli olmayan dönemler
    "Bakimda": "BAKIM",
    "Kalibrasyonda": "KALIBRASYON",
    "Arizali": "ARIZA",
    "Kullanim_Disi": "KULLANIM_DISI",
}


def _uygunluk_uyari(hedef_tarih, uyari_gun, bugun, gecmis_kodu):
    """Tarih geçmişse gecmis_kodu, uyarı süresi içindeyse 'YAKLASIYOR', değilse None (zil/dashboard kuralı)."""
    if hedef_tarih is None:
        return None
    kalan = (hedef_tarih - bugun).days
    if kalan < 0:
        return gecmis_kodu
    return "YAKLASIYOR" if kalan <= (uyari_gun if uyari_gun is not None else 30) else None


def cihaz_uygunluk_hazirla(bugun, bas, bit, cihazlar, rezervasyonlar, bakimlar, kalibrasyonlar,
                           arizalar, son_kalibrasyonlar, son_bakimlar):
    """Veritabanı satırlarından cihaz başına dönem listesini ve uyarıları üretir (saf fonksiyon)."""
    def gun_basi(gun):
        return datetime.combine(gun, datetime.min.time())

    def iso(deger):
        return deger.isoformat() if hasattr(deger, "isoformat") else str(deger)

    donemler = {c[0]: [] for c in cihazlar}

    def ekle(cihaz_id, tur, baslangic, bitis, kaynak="kayit"):
        if cihaz_id in donemler:
            donemler[cihaz_id].append({"tur": tur, "baslangic": iso(baslangic),
                                       "bitis": None if bitis is None else iso(bitis), "kaynak": kaynak})

    for cihaz_id, baslangic, bitis in rezervasyonlar:
        ekle(cihaz_id, "REZERVASYON", baslangic, bitis)
    for cihaz_id, gun1, gun2 in bakimlar:                       # gün aralığı, bitiş günü dahil
        ilk_gun = max(gun1, bas)
        son_gun = min(gun2, bit)
        if ilk_gun <= son_gun:
            ekle(cihaz_id, "BAKIM", gun_basi(ilk_gun),
                 gun_basi(son_gun) + timedelta(days=1))
    for cihaz_id, gun1, gun2 in kalibrasyonlar:
        ilk_gun = max(gun1, bas)
        son_gun = min(gun2, bit)
        if ilk_gun <= son_gun:
            ekle(cihaz_id, "KALIBRASYON", gun_basi(ilk_gun),
                 gun_basi(son_gun) + timedelta(days=1))
    for cihaz_id, bildirim, cozum, cozuldu in arizalar:         # açık arızanın bitişi yoktur
        if cozuldu and cozum is None:                            # çözüldü ama çözüm zamanı yok: süresi belirsiz, gösterme
            continue
        ekle(cihaz_id, "ARIZA", bildirim, None if not cozuldu else cozum)

    baslangic_sinir = gun_basi(max(bas, bugun))                 # durumdan türeyen dönem bugünden başlar
    bitis_sinir = gun_basi(bit + timedelta(days=1))
    for cihaz_id, _kod, _ad, durum in cihazlar:
        tur = UYGUNLUK_ACIK_UCLU_DURUMLAR.get(durum)
        if tur and baslangic_sinir < bitis_sinir:
            ekle(cihaz_id, tur, baslangic_sinir, None, kaynak="durum")

    kal = {k[0]: (k[1], k[2]) for k in son_kalibrasyonlar}
    bak = {b[0]: (b[1], b[2]) for b in son_bakimlar}
    sonuc = []
    for cihaz_id, kod, ad, durum in cihazlar:
        gecerlilik, kal_uyari = kal.get(cihaz_id, (None, None))
        sonraki, bak_uyari = bak.get(cihaz_id, (None, None))
        sonuc.append({
            "cihaz_id": cihaz_id, "envanter_kodu": kod, "cihaz_adi": ad, "durum": durum,
            "kalibrasyon_gecerlilik": gecerlilik.isoformat() if gecerlilik else None,
            "kalibrasyon_uyari": _uygunluk_uyari(gecerlilik, kal_uyari, bugun, "SURESI_DOLDU"),
            "sonraki_bakim": sonraki.isoformat() if sonraki else None,
            "bakim_uyari": _uygunluk_uyari(sonraki, bak_uyari, bugun, "GECIKTI"),
            "donemler": sorted(donemler[cihaz_id], key=lambda d: (d["baslangic"], d["tur"])),
        })
    return {"bugun": bugun.isoformat(), "baslangic": bas.isoformat(), "bitis": bit.isoformat(), "cihazlar": sonuc}


def cihaz_uygunluk_getir(
    baslangic: date | None = None,
    bitis: date | None = None,
    kullanici_id: int | None = None,
):
    """Seçilen tarih aralığında her cihazın rezervasyon, bakım, kalibrasyon, arıza ve kullanım dışı dönemleri."""
    bugun = date.today()
    if baslangic is None and bitis is None:
        baslangic = bugun
    if baslangic is None:
        baslangic = bitis - timedelta(days=6)
    if bitis is None:
        bitis = baslangic + timedelta(days=6)
    if bitis < baslangic:
        raise HTTPException(status_code=422, detail="Bitiş tarihi, başlangıç tarihinden önce olamaz.")
    if (bitis - baslangic).days + 1 > UYGUNLUK_EN_FAZLA_GUN:
        raise HTTPException(status_code=422, detail=f"En fazla {UYGUNLUK_EN_FAZLA_GUN} günlük aralık sorgulanabilir.")

    aralik_basi = datetime.combine(baslangic, datetime.min.time())
    aralik_sonu = datetime.combine(bitis + timedelta(days=1), datetime.min.time())
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, durum::text FROM cihazlar ORDER BY envanter_kodu, cihaz_id;")
        cihazlar = cursor.fetchall()
        cursor.execute(
            "SELECT cihaz_id, baslangic_zamani, bitis_zamani FROM cihaz_rezervasyonlari "
            "WHERE COALESCE(iptal_edildi_mi, FALSE) = FALSE AND baslangic_zamani < %s AND bitis_zamani > %s;",
            (aralik_sonu, aralik_basi))
        rezervasyonlar = cursor.fetchall()
        cursor.execute(
            "SELECT cihaz_id, COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date), "
            "COALESCE(bakim_bitis_tarihi, bakim_tarihi::date) FROM cihaz_bakimlari "
            "WHERE COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date) <= %s "
            "AND COALESCE(bakim_bitis_tarihi, bakim_tarihi::date) >= %s;",
            (bitis, baslangic))
        bakimlar = cursor.fetchall()
        cursor.execute(
            "SELECT cihaz_id, kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi FROM cihaz_kalibrasyonlari "
            "WHERE kalibrasyon_baslangic_tarihi IS NOT NULL AND kalibrasyon_bitis_tarihi IS NOT NULL "
            "AND kalibrasyon_baslangic_tarihi <= %s AND kalibrasyon_bitis_tarihi >= %s;",
            (bitis, baslangic))
        kalibrasyonlar = cursor.fetchall()
        cursor.execute(
            "SELECT cihaz_id, bildirim_tarihi, cozum_tarihi, COALESCE(cozuldu_mu, FALSE) FROM cihaz_arizalari "
            "WHERE bildirim_tarihi IS NOT NULL AND bildirim_tarihi < %s "
            "AND (NOT COALESCE(cozuldu_mu, FALSE) OR (cozum_tarihi IS NOT NULL AND cozum_tarihi > %s));",
            (aralik_sonu, aralik_basi))
        arizalar = cursor.fetchall()
        # Her cihazın güncel kalibrasyonu (geçerliliği en ileri olan) ve son bakım kaydı; dashboard/zil ile aynı kural.
        cursor.execute(
            "SELECT DISTINCT ON (cihaz_id) cihaz_id, gecerlilik_tarihi, uyari_suresi_gun FROM cihaz_kalibrasyonlari "
            "WHERE gecerlilik_tarihi IS NOT NULL ORDER BY cihaz_id, gecerlilik_tarihi DESC, kalibrasyon_id DESC;")
        son_kalibrasyonlar = cursor.fetchall()
        cursor.execute(
            "SELECT DISTINCT ON (cihaz_id) cihaz_id, sonraki_bakim_tarihi, uyari_suresi_gun FROM cihaz_bakimlari "
            "ORDER BY cihaz_id, COALESCE(bakim_baslangic_tarihi::date, bakim_tarihi::date) DESC, bakim_id DESC;")
        son_bakimlar = cursor.fetchall()
        return cihaz_uygunluk_hazirla(bugun, baslangic, bitis, cihazlar, rezervasyonlar, bakimlar,
                                      kalibrasyonlar, arizalar, son_kalibrasyonlar, son_bakimlar)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# (yol, uç fonksiyonu, yetki parametresi, gereken izin): yetki bağımlılığı kayıt sırasında eklenir.
# İzin None ise yalnızca oturum açmış olmak yeter (kimlik bağımlılığı).
UCLAR = [
    ("/api/cihaz-uygunluk", cihaz_uygunluk_getir, "kullanici_id", "CIHAZ_UYGUNLUK_GORUNTULE"),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol`."""
    router = APIRouter()
    for yol, fonksiyon, parametre, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, parametre, izin_kontrol(izin)), methods=["GET"])
    return router
