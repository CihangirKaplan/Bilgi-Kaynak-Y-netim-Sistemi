"""Zil bildirimleri için hafif özet uçları (salt okunur). Yalnızca sayı/durum döner; kişisel veri içermez.

Zil her dakika yenilenir; bu yüzden tam listeler (öğrenci listesi, sistem durumu) yerine yalnızca gereken sayıyı hesaplayan küçük
uçlar kullanılır. Her uç, ilgili sayfanın izniyle korunur: yetkisi olmayan kullanıcı bildirimi hiç görmez.
"""
from fastapi import APIRouter, HTTPException

from server import sistem_durumu as _sistem_durumu
from server.ortak_yardimcilar import psikolog_rolu_mu
from server.vt_ayarlari import VT_AYARLARI
from server.vt_baglanti import vt_baglan
from server.yetki_baglama import yetkiyle_bagla

# Saklama süresi: pasife alındıktan 2 yıl (Öğrenciler sayfasındaki "Süresi Dolan Kayıtlar" ve Öğrenci Raporu ile aynı kural).
OGRENCI_SAKLAMA_SQL = """
    SELECT
        COUNT(*) FILTER (WHERE doldu AND NOT ertelendi) AS bekleyen,
        COUNT(*) FILTER (WHERE doldu AND ertelendi) AS ertelenen
    FROM (
        SELECT
            (o.tur::text = 'GONULLU' AND NOT o.aktif_mi
             AND o.pasife_alinma_tarihi::date <= (CURRENT_DATE - INTERVAL '2 years')::date) AS doldu,
            COALESCE(e.yeni_uyari_tarihi > CURRENT_DATE, FALSE) AS ertelendi
        FROM ogrenciler o
        LEFT JOIN LATERAL (
            SELECT yeni_uyari_tarihi FROM ogrenci_kayit_erteleme_gecmisi e
            WHERE e.ogrenci_id = o.ogrenci_id ORDER BY e.erteleme_id DESC LIMIT 1
        ) e ON TRUE
    ) t
"""


def _bagli_calis(islem, hata_metni):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        return islem(cursor)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail=hata_metni)
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def ogrenci_saklama_ozeti(kullanici_id: int | None = None):
    """Saklama süresi dolmuş Gönüllü öğrenci sayıları: `bekleyen` (işlem bekliyor), `ertelenen` (ileri bir tarihe ertelenmiş)."""
    def islem(cursor):
        cursor.execute(OGRENCI_SAKLAMA_SQL)
        bekleyen, ertelenen = cursor.fetchone()
        return {"bekleyen": int(bekleyen), "ertelenen": int(ertelenen)}
    return _bagli_calis(islem, "Öğrenci saklama özeti alınamadı.")


def sonucu_girilmemis_randevu_ozeti(kullanici_id: int | None = None):
    """Tarihi geçmiş ama hâlâ "Planlandı" olan randevu sayısı (sonucu girilmemiş). Psikolog yalnızca kendi randevularını sayar."""
    def islem(cursor):
        cursor.execute(
            "SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("""
                SELECT COUNT(*) FROM randevular r JOIN personel p ON p.personel_id = r.psikolog_id
                WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani < NOW()
            """, (kullanici_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM randevular WHERE durum = 'PLANLANDI' AND baslangic_zamani < NOW()")
        return {"sayi": int(cursor.fetchone()[0])}
    return _bagli_calis(islem, "Randevu özeti alınamadı.")


def yedek_ozeti(kullanici_id: int | None = None):
    """Son yedeğin durumu (Sistem Durumu sayfasıyla aynı kural): var mı, ne zaman, kaç saat önce, eski mi."""
    return _sistem_durumu.son_yedek_bilgisi(_sistem_durumu.yedek_klasoru(), VT_AYARLARI["dbname"])


# (yol, uç fonksiyonu, gereken izin)
UCLAR = [
    ("/api/bildirim/ogrenci-saklama", ogrenci_saklama_ozeti, "FAALIYET_KAYITLARI_DUZENLE"),
    ("/api/bildirim/sonucu-girilmemis-randevu", sonucu_girilmemis_randevu_ozeti, "RANDEVU_DUZENLE"),
    ("/api/bildirim/yedek", yedek_ozeti, "AUDIT_KAYITLARI_INCELE"),
]


def router_olustur(izin_kontrol) -> APIRouter:
    """`izin_kontrol`: `server.sunucu.izin_kontrol` (kimlik doğrulama + izin kontrolü bağımlılığı üreticisi)."""
    router = APIRouter()
    for yol, fonksiyon, izin in UCLAR:
        router.add_api_route(yol, yetkiyle_bagla(fonksiyon, "kullanici_id", izin_kontrol(izin)), methods=["GET"])
    return router
