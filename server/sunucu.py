from server.modeller import DanismaGorevOlusturModeli
from fastapi import FastAPI, HTTPException, Depends, Query, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.errors import ExclusionViolation, DeadlockDetected
from psycopg2.extras import Json
from server.oda_etkinlikleri_kurallari import (
    oda_kilidini_al,
    oda_cakismasi_bul,
)
import logging
import os
import time
from functools import lru_cache
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta, date
from typing import Optional
from server.modeller import (
    FaaliyetBirimIslemModeli,
    GirisModeli,
    ParolaSifirlamaTalebiModeli,
    RolDegistirModeli,
    KullaniciOlusturModeli,
    PersonelOlusturModeli,
    PersonelGuncelleModeli,
    SifreDegistirModeli,
    RandevuOlusturModeli,
    RandevuGuncelleModeli,
    RandevuIptalModeli,
    RandevuDurumModeli,
    DanisanBilgiModeli,
    YAS_GRUPLARI,
    TERAPI_TURLERI,
    GORUSME_TIPLERI,
    IPTAL_NEDENLERI,
    randevu_terapisini_belirle,
    BakimPlaniGuncelleModeli,
    BakimPlaniOlusturModeli,
    OdaOlusturModeli,
    OdaGuncelleModeli,
    CihazOlusturModeli,
    CihazGuncelleModeli,
    RezervasyonOlusturModeli,
    BolumOlusturModeli,
    ProjeTuruOlusturModeli,
    ArizaBildirimModeli,
    ArizaGuncelleModeli,
    KalibrasyonOlusturModeli,
    KalibrasyonGuncelleModeli,
    BakimOlusturModeli,
    BakimGuncelleModeli,
    IzinDuzenleModeli,
    RolGorunenAdModeli
)
from server.guvenlik import (
    parola_hashle,
    parola_dogrula,
    gecici_parola_uret,
    access_token_olustur,
    token_dogrula,
    token_parola_gecerli,
    token_surumu_gecerli,
    GECICI_PAROLA_BITIS_SQL,
    GECICI_PAROLA_GECERLILIK_SAAT,
)
from server.guvenlik_basliklari import GuvenlikBasliklari
from server.personel_kaydi import personel_kaydi_ata
from server.vt_baglanti import vt_baglan
from server.parola_politikasi import parola_ihlalleri
from server.rol_hiyerarsisi import HIYERARSI_MESAJI, hiyerarsi_ihlali_var_mi
from server.denetim import (
    ayrintili_kayit_yaz,
    denetim_kaydi_olustur,
    durum_degisikligi_yaz,
    psikolog_oda_degisikligini_yaz,
    psikolog_odalarini_oku,
    satiri_sil_ve_ayrintisini_al,
)
from server import giris_siniri, rapor_bakim_plani, rapor_kullanim, rapor_ogrenci_faaliyet
from server.girdi_korumasi import NulVeSayiKorumasi, merkezi_hata_yakalayicilari_kur
from server.randevu_rapor_hesapla import randevu_raporu_hesapla
from server.modeller import FaaliyetKayitModeli, DuyuruModeli
from server.modeller import bakim_tarihi_sorunu, RezervasyonGuncelleModeli, rezervasyon_zaman_sorunu
import psycopg2.errors
from server.modeller import OgrenciEkleModeli, DanismaGorevDuzenleModeli, RolModeli

load_dotenv()


def api_belgeleri_acik_mi() -> bool:
    """/docs, /redoc ve /openapi.json yalnızca TKYS_API_DOCS=1 ise açılır (varsayılan kapalı)."""
    return os.getenv("TKYS_API_DOCS", "").strip() == "1"


def fastapi_olustur(belgeler_acik: bool) -> FastAPI:
    return FastAPI(
        docs_url="/docs" if belgeler_acik else None,
        redoc_url="/redoc" if belgeler_acik else None,
        openapi_url="/openapi.json" if belgeler_acik else None,
    )


app = fastapi_olustur(api_belgeleri_acik_mi())
# Bozuk girdi (NUL karakter, taşan sayı) ve veritabanı kural hataları 500 yerine anlamlı hata döndürür.
app.add_middleware(NulVeSayiKorumasi)
app.add_middleware(GuvenlikBasliklari)
merkezi_hata_yakalayicilari_kur(app)


@app.get("/api/saglik")
def saglik_kontrolu():
    """Sunucunun ayakta olduğunu gösterir (kimlik doğrulama ve veritabanı gerektirmez)."""
    return {"durum": "calisiyor"}

bearer_scheme = HTTPBearer()


from server.ortak_sabitler import CIHAZ_ODALARI_SORGUSU, ETKIN_CIHAZ_DURUMU_SQL, OGRENCI_TUR_ETIKETLERI
from server.ortak_yardimcilar import plan_kalibrasyon_mu, psikolog_rolu_mu
from server.liste_siniri import (
    LISTE_UST_SINIRI,
    liste_siniri_coz,
    liste_toplamini_bildir,
)
from server.rezervasyon_cakismasi import (
    REZERVASYON_CAKISMA_KODU,
    rezervasyon_cakisma_detayi,
    cakisan_rezervasyonlari_denetle,
)
from server.vt_ayarlari import VT_AYARLARI          # tek tanım yeri; ayrılan modüller de aynı sözlüğü kullanır

def otomatik_danisan_kodu_uret(cursor, yil=None, kilitle=True) -> str:
    """Yıl bazlı sıradaki danışan kodu: DAN-<yıl>-<sıra>. Sıra, o yılın en büyük kodunun bir fazlasıdır; her yıl 0001'den başlar.

    kilitle=True (kayıt anı): aynı yılın kod üretimi transaction sonuna kadar kilitlenir, böylece iki kayıt aynı kodu almaz.
    kilitle=False (önizleme): kilit alınmaz ve hiçbir sayaç tüketilmez; ekran açılıp kapanınca numara atlamaz."""
    yil = int(yil or datetime.now().year)
    if kilitle:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s);", (4210, yil))
    cursor.execute(
        "SELECT COALESCE(MAX(CAST(SUBSTRING(danisan_kod_id FROM %s) AS INTEGER)), 0) + 1 FROM danisan_kodlari WHERE danisan_kod_id ~ %s;",
        (f"^DAN-{yil}-([0-9]+)$", f"^DAN-{yil}-[0-9]+$"),
    )
    return f"DAN-{yil}-{cursor.fetchone()[0]:04d}"


ROL_PASIF_ATAMA_MESAJI = "Seçilen rol pasif; pasif role kullanıcı atanamaz. Önce rolü aktif edin."
ROL_PASIF_GIRIS_MESAJI = "Rolünüz pasif durumda; sisteme giriş engellendi. Yöneticinize başvurun."


@lru_cache(maxsize=1)
def _sahte_parola_hash() -> str:
    """Var olmayan kullanıcı adında da bir bcrypt doğrulaması yapılır; yanıt süresi hesabın var olup olmadığını ele vermesin."""
    return parola_hashle("zamanlama-korumasi-sahte-parola")




def token_kullanici_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> int:
    """İlk girişte parola değiştirmeye de izin veren güvenli token kontrolü."""
    token = credentials.credentials

    try:
        kullanici_id = token_dogrula(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT k.parola_hash, k.aktif_mi, COALESCE(r.aktif_mi, TRUE), k.token_surumu FROM kullanicilar k "
            "LEFT JOIN roller r ON r.rol_id = k.rol_id "
            "WHERE k.kullanici_id = %s;",
            (kullanici_id,)
        )
        kayit = cursor.fetchone()

        if kayit is None:
            raise HTTPException(
                status_code=401,
                detail="Kullanıcı bulunamadı."
            )

        if not kayit[1]:
            raise HTTPException(
                status_code=403,
                detail="Kullanıcı hesabı aktif değil."
            )

        if len(kayit) > 2 and kayit[2] is False:
            raise HTTPException(status_code=403, detail=ROL_PASIF_GIRIS_MESAJI)

        if not token_parola_gecerli(token, kayit[0]) or not token_surumu_gecerli(token, kayit[3] if len(kayit) > 3 else 0):
            raise HTTPException(
                status_code=401,
                detail="Oturum geçersiz. Yeniden giriş yapınız."
            )

        return kullanici_id

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def mevcut_kullanici_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> int:
    try:
        token = credentials.credentials
        kullanici_id = token_dogrula(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT k.aktif_mi, k.ilk_giris_mi, k.parola_hash, COALESCE(r.aktif_mi, TRUE), k.token_surumu FROM kullanicilar k "
            "LEFT JOIN roller r ON r.rol_id = k.rol_id WHERE k.kullanici_id = %s;",
            (kullanici_id,),
        )
        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[0]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
        if len(kullanici) > 3 and kullanici[3] is False:
            raise HTTPException(status_code=403, detail=ROL_PASIF_GIRIS_MESAJI)
        if not token_parola_gecerli(token, kullanici[2]) or not token_surumu_gecerli(token, kullanici[4] if len(kullanici) > 4 else 0):
            raise HTTPException(
                status_code=401,
                detail="Oturum geçersiz. Yeniden giriş yapınız."
            )

        if kullanici[1]:
            raise HTTPException(status_code=403, detail="İlk girişte şifrenizi değiştirmeniz gerekiyor.")

        return kullanici_id
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

def izin_kontrol(izin_adi: str):
    def kontrol(kullanici_id: int = Depends(mevcut_kullanici_id)):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ri.izin_var FROM kullanicilar k
                JOIN rol_izinleri ri ON k.rol_id = ri.rol_id
                JOIN izinler i ON ri.izin_id = i.izin_id
                WHERE k.kullanici_id = %s AND i.izin_adi = %s;
                """, (kullanici_id, izin_adi)
            )
            sonuc = cursor.fetchone()
            if sonuc is None or sonuc[0] != 1:
                raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz bulunmuyor.")
            return kullanici_id
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()
    return kontrol

def izin_kontrol_biri(*izin_adlari: str):
    """İzinlerden en az birine sahip kullanıcıya izin verir (örn. kayıtları görme VEYA yönetme)."""
    def kontrol(kullanici_id: int = Depends(mevcut_kullanici_id)):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT MAX(ri.izin_var) FROM kullanicilar k
                JOIN rol_izinleri ri ON k.rol_id = ri.rol_id
                JOIN izinler i ON ri.izin_id = i.izin_id
                WHERE k.kullanici_id = %s AND i.izin_adi = ANY(%s);
                """, (kullanici_id, list(izin_adlari)),
            )
            sonuc = cursor.fetchone()
            if sonuc is None or sonuc[0] != 1:
                raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz bulunmuyor.")
            return kullanici_id
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()
    return kontrol

@app.get("/api/korumali-test")
def korumali_test(kullanici_id: int = Depends(mevcut_kullanici_id)):
    return {"durum": "basarili", "mesaj": "Token geçerli.", "kullanici_id": kullanici_id}

@app.get("/api/yetkilerim")
def yetkilerim(kullanici_id: int = Depends(mevcut_kullanici_id)):
    """Giriş yapan kullanıcının rolünü ve o role açık olan izinleri döndürür.

    İstemci menüsü bu yanıta göre çizilir; böylece menü ile sunucunun gerçekte uyguladığı
    yetkiler (rol_izinleri tablosu) her zaman aynıdır. Kullanıcı yalnızca kendi rolünün
    izinlerini görür, ayrıca bir izin gerektirmez.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.rol_adi, i.izin_adi
            FROM kullanicilar k
            JOIN roller r ON r.rol_id = k.rol_id
            LEFT JOIN rol_izinleri ri ON ri.rol_id = k.rol_id AND ri.izin_var = 1
            LEFT JOIN izinler i ON i.izin_id = ri.izin_id
            WHERE k.kullanici_id = %s
            ORDER BY i.izin_adi;
            """,
            (kullanici_id,)
        )
        satirlar = cursor.fetchall()
        if not satirlar:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
        return {
            "rol_adi": satirlar[0][0],
            "izinler": [satir[1] for satir in satirlar if satir[1] is not None],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/login")
def giris_yap(giris: GirisModeli, request: Request = None):
    # İstemci (IP) bazlı başarısız deneme sınırı: var olmayan kullanıcı adlarıyla yapılan denemeleri de durdurur.
    istemci = giris_siniri.istemci_anahtari(request)
    bekleme = giris_siniri.engel_suresi(VT_AYARLARI, istemci)
    if bekleme:
        raise HTTPException(
            status_code=429,
            detail="Bu bilgisayardan çok fazla hatalı giriş denemesi yapıldı. Lütfen biraz bekleyip tekrar deneyin.",
            headers={"Retry-After": str(bekleme)},
        )
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT k.kullanici_id, k.kullanici_adi, k.parola_hash, k.rol_id, k.aktif_mi,
                   k.basarisiz_giris_sayisi, k.kilit_bitis_zamani, k.ilk_giris_mi, r.rol_adi, k.gecici_parola_bitis,
                   COALESCE(r.aktif_mi, TRUE), k.token_surumu
            FROM kullanicilar k
            LEFT JOIN roller r ON k.rol_id = r.rol_id
            WHERE LOWER(k.kullanici_adi) = LOWER(%s)
            ORDER BY (k.kullanici_adi = %s) DESC
            LIMIT 1;
            """, (giris.kullanici_adi, giris.kullanici_adi)
        )
        kullanici = cursor.fetchone()

        if kullanici is None:
            parola_dogrula(giris.parola, _sahte_parola_hash())      # yanıt süresi, hesabın var olup olmadığını ele vermesin
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", hedef_tablo="kullanicilar")
            giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, istemci)
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya parola hatalı.")
        if kullanici[6] is not None and kullanici[6] > datetime.now():
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="LOGIN_FAILED",
                kullanici_id=kullanici[0],
                hedef_tablo="kullanicilar",
                hedef_kayit_id=kullanici[0],
            )
            kalan_saniye = max(1, int((kullanici[6] - datetime.now()).total_seconds()) + 1)
            raise HTTPException(
                status_code=429,
                detail="Hesap geçici olarak kilitli.",
                headers={"Retry-After": str(kalan_saniye)},
            )

        if not parola_dogrula(giris.parola, kullanici[2]):
            # Sayaç tek SQL ile artırılır (okuyup +1 yazmak eşzamanlı denemelerde eksik sayardı ve kilidi geciktirirdi).
            cursor.execute(
                "UPDATE kullanicilar SET basarisiz_giris_sayisi = basarisiz_giris_sayisi + 1 WHERE kullanici_id = %s RETURNING basarisiz_giris_sayisi;",
                (kullanici[0],),
            )
            yeni_basarisiz_giris_sayisi = cursor.fetchone()[0]
            if yeni_basarisiz_giris_sayisi >= 5:
                kilit_saniye = 900 if yeni_basarisiz_giris_sayisi >= 10 else 60
                kilit_bitis_zamani = datetime.now() + timedelta(seconds=kilit_saniye)
                cursor.execute("UPDATE kullanicilar SET kilit_bitis_zamani = %s WHERE kullanici_id = %s;", (kilit_bitis_zamani, kullanici[0]))
            conn.commit()
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, istemci)
            if yeni_basarisiz_giris_sayisi >= 5:
                raise HTTPException(
                    status_code=429,
                    detail="Çok fazla hatalı giriş denemesi. Hesap geçici olarak kilitlendi.",
                    headers={"Retry-After": str(kilit_saniye)},
                )
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya parola hatalı.")

        # Parola DOĞRU: hesap ya da rol pasifse bu ancak şimdi söylenir (parolayı bilmeyen biri hesabın var/pasif olduğunu öğrenemez).
        if not kullanici[4]:
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
        if len(kullanici) > 10 and kullanici[10] is False:
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            raise HTTPException(status_code=403, detail=ROL_PASIF_GIRIS_MESAJI)

        # Parola doğru ama GEÇİCİ parolanın süresi dolmuşsa giriş yapılamaz (yanlış parolada bu bilgi verilmez).
        gecici_bitis = kullanici[9] if len(kullanici) > 9 else None
        if kullanici[7] and gecici_bitis is not None and gecici_bitis < datetime.now():
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            raise HTTPException(
                status_code=403,
                detail="Geçici parolanızın süresi doldu. Yöneticinizden yeni bir geçici parola isteyin.",
            )

        cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = 0, kilit_bitis_zamani = NULL WHERE kullanici_id = %s;", (kullanici[0],))
        conn.commit()
        cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici[0],))
        pers = cursor.fetchone()
        # YENİ KONTROL: Personel kaydı yoksa 403 hatası fırlat ve girişi kes
        if not pers:
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="LOGIN_FAILED",
                kullanici_id=kullanici[0],
                hedef_tablo="kullanicilar",
                hedef_kayit_id=kullanici[0],
            )
            raise HTTPException(
                status_code=403, 
                detail="Yöneticinizden sizi personel olarak tanımlamasını isteyiniz."
            )
        personel_id = pers[0]
        access_token = access_token_olustur(kullanici[0], kullanici[2], kullanici[11] if len(kullanici) > 11 else 0)

        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
        return {
            "durum": "basarili",
            "mesaj": "Giriş başarılı.",
            "access_token": access_token,
            "token_type": "bearer",
            "kullanici_id": kullanici[0],
            "personel_id": personel_id,
            "kullanici_adi": kullanici[1],
            "rol_id": kullanici[3],
            "sifre_degistirme_gerekli": kullanici[7],
            "rol_adi": kullanici[8]
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/cikis")
def cikis_yap(kullanici_id: int = Depends(token_kullanici_id)):
    """Oturumu kapatır: kullanıcının oturum sürümü artar, bu kullanıcıya ait TÜM açık oturum anahtarları (token) geçersiz olur.

    Çalınmış ya da unutulmuş bir oturum anahtarı süresi dolmayı beklemeden işe yaramaz hale gelir. Aynı hesapla başka bilgisayarda
    açık olan oturumlar da kapanır (tek hesapta tek sürüm tutulur)."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("UPDATE kullanicilar SET token_surumu = token_surumu + 1 WHERE kullanici_id = %s;", (kullanici_id,))
        ayrintili_kayit_yaz(cursor, kullanici_id, "LOGOUT", "kullanicilar", kullanici_id)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Oturum kapatıldı."}
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Oturum kapatılamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.post("/api/sifre-degistir")
def sifre_degistir(veri: SifreDegistirModeli, request: Request = None, kullanici_id: int = Depends(token_kullanici_id)):
    # Eski şifre de giriş ekranındaki IP sınırıyla korunur: açık kalmış bir oturumdan şifre tahmin edilemesin.
    istemci = giris_siniri.istemci_anahtari(request)
    bekleme = giris_siniri.engel_suresi(VT_AYARLARI, istemci)
    if bekleme:
        raise HTTPException(
            status_code=429,
            detail="Bu bilgisayardan çok fazla hatalı şifre denemesi yapıldı. Lütfen biraz bekleyip tekrar deneyin.",
            headers={"Retry-After": str(bekleme)},
        )
    if veri.yeni_parola != veri.yeni_parola_tekrar:
        raise HTTPException(status_code=422, detail="Yeni şifreler birbiriyle eşleşmiyor.")
    if len(veri.yeni_parola.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Yeni şifre en fazla 72 bayt olabilir.")
    if veri.eski_parola == veri.yeni_parola:
        raise HTTPException(status_code=422, detail="Yeni şifre eski şifreyle aynı olamaz.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT parola_hash, aktif_mi, kullanici_adi FROM kullanicilar WHERE kullanici_id = %s FOR UPDATE;",
            (kullanici_id,)
        )
        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[1]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")

        if not parola_dogrula(veri.eski_parola, kullanici[0]):
            conn.rollback()
            cursor.execute(
                """
                INSERT INTO denetim_kayitlari
                    (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id)
                VALUES (%s, %s, %s, %s);
                """,
                (kullanici_id, "PASSWORD_CHANGE_FAILED", "kullanicilar", kullanici_id)
            )
            conn.commit()
            giris_siniri.basarisiz_girisi_kaydet(VT_AYARLARI, istemci)
            raise HTTPException(status_code=401, detail="Eski şifre hatalı.")

        ihlaller = parola_ihlalleri(veri.yeni_parola, kullanici[2] if len(kullanici) > 2 else None)
        if ihlaller:
            raise HTTPException(status_code=422, detail=" ".join(ihlaller))

        yeni_hash = parola_hashle(veri.yeni_parola)
        cursor.execute(
            "UPDATE kullanicilar SET parola_hash = %s, ilk_giris_mi = FALSE, gecici_parola_bitis = NULL WHERE kullanici_id = %s;",
            (yeni_hash, kullanici_id)
        )
        cursor.execute(
            """
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
            """,
            (kullanici_id, "PASSWORD_CHANGE", "kullanicilar", kullanici_id)
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Şifreniz başarıyla değiştirildi."}
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# ==========================================
# ADM MODÜLÜ (Kullanıcı, Rol ve Personel)
# ==========================================



def _siradaki_personel_kodu(cursor, rol_adi):
    """Rol bazında benzersiz personel kodu üretir."""
    import re

    rol_kodlari = {
        "PSIKOLOG": "PSK",
        "MEMUR": "MEM",
        "MUDUR": "MUD",
        "DANISMA_OGRENCISI": "OGR",
        "PROJE_ASISTANI": "AST",
        "ADMIN": "ADM",
    }

    rol_kodu = rol_kodlari.get(rol_adi, "SYS")
    onek = f"PER-{rol_kodu}-"

    # Kullanıcı oluşturmayla aynı kilit: eşzamanlı kod çakışmasını önler.
    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s));",
        (f"TKYS_PERSONEL_KODU_{rol_kodu}",),
    )

    cursor.execute(
        "SELECT personel_kodu FROM kullanicilar "
        "WHERE personel_kodu LIKE %s;",
        (onek + "%",),
    )

    numaralar = []
    for (kod,) in cursor.fetchall():
        if not isinstance(kod, str):
            continue

        eslesme = re.fullmatch(
            re.escape(onek) + r"([0-9]+)", kod
        )
        if eslesme:
            numaralar.append(int(eslesme.group(1)))

    return f"{onek}{max(numaralar, default=0) + 1:03d}"


@app.post("/api/kullanicilar", status_code=201)
def kullanici_olustur(
    yeni_kullanici: KullaniciOlusturModeli,
    kullanici_id: int = Depends(izin_kontrol("KULLANICI_OLUSTUR")),
):

    conn = None
    cursor = None
    asama = "kullanici"
    personel_id = None
    personel_kodu = None
    ogrenci_id = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # İşlemi yapan kişinin rolünü öğren.
        cursor.execute(
            """
            SELECT r.rol_adi
            FROM kullanicilar k
            JOIN roller r ON k.rol_id = r.rol_id
            WHERE k.kullanici_id = %s;
            """,
            (kullanici_id,),
        )
        yapan = cursor.fetchone()

        # Birleşik oluşturma için iki yetki de gerekli.
        # Mevcut rol atama izni korunur.
        cursor.execute(
            """
            SELECT 1
            FROM kullanicilar k
            WHERE k.kullanici_id = %s
              AND EXISTS (
                  SELECT 1
                  FROM rol_izinleri ri
                  JOIN izinler i ON i.izin_id = ri.izin_id
                  WHERE ri.rol_id = k.rol_id
                    AND i.izin_adi = 'ROL_ATAMA_DEGISTIRME'
                    AND ri.izin_var = 1
              )
              AND EXISTS (
                  SELECT 1
                  FROM rol_izinleri ri
                  JOIN izinler i ON i.izin_id = ri.izin_id
                  WHERE ri.rol_id = k.rol_id
                    AND i.izin_adi = 'PERSONEL_TANIMLA'
                    AND ri.izin_var = 1
              );
            """,
            (kullanici_id,),
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=403,
                detail="Kullanıcı oluşturma için gerekli yetkileriniz bulunmuyor.",
            )

        cursor.execute(
            "SELECT rol_adi, aktif_mi FROM roller WHERE rol_id = %s;",
            (yeni_kullanici.rol_id,),
        )
        hedef_rol = cursor.fetchone()

        if hedef_rol is None:
            raise HTTPException(
                status_code=422,
                detail="Geçersiz rol seçildi.",
            )
        if len(hedef_rol) > 1 and hedef_rol[1] is False:
            raise HTTPException(status_code=422, detail=ROL_PASIF_ATAMA_MESAJI)

        rol_adi = hedef_rol[0]

        if rol_adi == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="ADMIN kullanıcısı bu ekran üzerinden oluşturulamaz.",
            )
        if hiyerarsi_ihlali_var_mi(yapan[0] if yapan else None, rol_adi):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        danisma_ogrencisi = rol_adi == "DANISMA_OGRENCISI"

        ogrenci_bilgisi_var = any([
            yeni_kullanici.ad_soyad,
            yeni_kullanici.ogrenci_numarasi,
            yeni_kullanici.telefon,
        ])

        if danisma_ogrencisi:
            if (
                not yeni_kullanici.ad_soyad
                or not yeni_kullanici.ogrenci_numarasi
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Danışma öğrencisi için ad soyad ve öğrenci numarası zorunludur.",
                )
        elif ogrenci_bilgisi_var:
            raise HTTPException(
                status_code=422,
                detail="Öğrenci bilgileri yalnızca danışma öğrencisi rolü için girilebilir.",
            )

        psikolog_rolu = psikolog_rolu_mu(rol_adi)
        istenen_odalar = sorted(set(yeni_kullanici.oda_idleri or []))
        if psikolog_rolu:
            # Her psikologun en az bir (aktif) odası olmalı.
            if not istenen_odalar:
                raise HTTPException(
                    status_code=422,
                    detail="Psikolog için en az bir görüşme odası seçilmelidir.",
                )
            cursor.execute(
                "SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;",
                (istenen_odalar,),
            )
            if {k[0] for k in cursor.fetchall()} != set(istenen_odalar):
                raise HTTPException(
                    status_code=422,
                    detail="Seçilen odalardan biri bulunamadı veya aktif değil.",
                )
            etkinlik_oda_atama_kilitlerini_al(
                cursor, istenen_odalar
            )
            cihaz_rezervasyonlu_odalari_denetle(cursor, istenen_odalar)
            oda_etkinlikli_odalari_denetle(cursor, istenen_odalar)
        elif istenen_odalar:
            raise HTTPException(
                status_code=422,
                detail="Oda yetkisi yalnızca psikolog rolü için tanımlanabilir.",
            )

        gecici_parola = gecici_parola_uret()
        parola_hash = parola_hashle(gecici_parola)
        personel_kodu = _siradaki_personel_kodu(cursor, rol_adi)

        cursor.execute(
            f"""
            INSERT INTO kullanicilar
                (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi, gecici_parola_bitis,
                 personel_id, personel_kodu, personel_kaydi_tarihi)
            SELECT %s, %s, %s, TRUE, TRUE, {GECICI_PAROLA_BITIS_SQL},
                   nextval('personel_personel_id_seq'), %s, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM kullanicilar WHERE LOWER(kullanici_adi) = LOWER(%s))
            RETURNING kullanici_id, personel_id;
            """,
            (
                yeni_kullanici.kullanici_adi,
                parola_hash,
                yeni_kullanici.rol_id,
                personel_kodu,
                yeni_kullanici.kullanici_adi,
            ),
        )
        satir = cursor.fetchone()
        if satir is None:                                   # aynı ad (büyük/küçük harf farkıyla da olsa) zaten var
            raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten kullanılıyor.")
        yeni_id, personel_id = satir

        # Tek denetim kaydı: kullanıcı ve personel bilgisi aynı kayıttır.
        ayrintili_kayit_yaz(
            cursor, kullanici_id, "CREATE", "kullanicilar", yeni_id,
            rol=rol_adi, personel_kodu=personel_kodu, oda_sayisi=len(istenen_odalar),
        )

        if danisma_ogrencisi:
            asama = "ogrenci"
            cursor.execute(
                """
                INSERT INTO ogrenciler
                    (kullanici_id, ad_soyad, ogrenci_numarasi, telefon, tur)
                VALUES (%s, %s, %s, %s, 'DANISMA_MASASI')
                RETURNING ogrenci_id;
                """,
                (
                    yeni_id,
                    yeni_kullanici.ad_soyad,
                    yeni_kullanici.ogrenci_numarasi,
                    yeni_kullanici.telefon,
                ),
            )
            ogrenci_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO denetim_kayitlari
                    (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id)
                VALUES (%s, %s, %s, %s);
                """,
                (kullanici_id, "CREATE", "ogrenciler", ogrenci_id),
            )

        # Psikolog oda yetkileri.
        for oda_id in istenen_odalar:
            cursor.execute(
                "INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s);",
                (yeni_id, oda_id),
            )

        # Her şey başarılıysa tek commit.
        conn.commit()

        return {
            "durum": "basarili",
            "kullanici_id": yeni_id,
            "kullanici_adi": yeni_kullanici.kullanici_adi,
            "gecici_parola": gecici_parola,
            "gecici_parola_gecerlilik_saat": GECICI_PAROLA_GECERLILIK_SAAT,
            "ilk_giris_mi": True,
            "personel_id": personel_id,
            "personel_kodu": personel_kodu,
            "ogrenci_id": ogrenci_id,
        }

    except psycopg2.errors.UniqueViolation as hata:
        if conn is not None:
            conn.rollback()

        kisit = getattr(getattr(hata, "diag", None), "constraint_name", None) or ""
        if asama == "ogrenci":
            mesaj = "Bu öğrenci numarası zaten kullanılıyor."
        elif kisit.startswith("kullanicilar_personel_"):
            mesaj = "Personel kodu veya personel kaydı zaten mevcut."
        else:
            mesaj = "Bu kullanıcı adı zaten kullanılıyor."

        raise HTTPException(status_code=409, detail=mesaj)

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Kullanıcı oluşturulurken beklenmeyen bir hata oluştu.",
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/api/kullanicilar/musait-kullanici-adi")
def musait_kullanici_adi(
    temel: str = Query(..., min_length=1, max_length=90),
    kullanici_id: int = Depends(izin_kontrol("KULLANICI_OLUSTUR"))
):
    """Verilen ad boşsa onu, doluysa sonuna sayı ekleyerek ilk boş adı döndürür.

    Örn. 'cihangir.kaplan' doluysa 'cihangir.kaplan2', o da doluysa 'cihangir.kaplan3'.
    Aynı isimli kişiler için kullanıcı adı çakışmasını önler.
    """
    temel = "".join(c for c in temel.lower() if c.isascii() and (c.isalnum() or c in "._-")).strip("._-")
    if len(temel) < 3:
        raise HTTPException(status_code=422, detail="Kullanıcı adı en az 3 karakter olmalıdır.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT lower(kullanici_adi) FROM kullanicilar WHERE starts_with(lower(kullanici_adi), %s);",
            (temel,)
        )
        kullanilan = {satir[0] for satir in cursor.fetchall()}
        onerilen, sayi = temel, 1
        while onerilen in kullanilan:
            sayi += 1
            onerilen = f"{temel}{sayi}"
        return {"kullanici_adi": onerilen}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/kullanicilar/{kullanici_id}/ogrenci-kayit-durumu")
def kullanici_ogrenci_kayit_durumu(
    kullanici_id: int,
    islem_yapan_id: int = Depends(izin_kontrol("ROL_ATAMA_DEGISTIRME")),
):
    conn = vt_baglan(VT_AYARLARI)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM kullanicilar WHERE kullanici_id = %s;",
                (kullanici_id,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

            cursor.execute(
                "SELECT ogrenci_id FROM ogrenciler WHERE kullanici_id = %s;",
                (kullanici_id,),
            )
            return {"ogrenci_kaydi_var": cursor.fetchone() is not None}
    finally:
        conn.close()


@app.patch("/api/kullanicilar/{kullanici_id}/rol")
def kullanici_rol_degistir(kullanici_id: int, veri: RolDegistirModeli, islem_yapan_id: int = Depends(izin_kontrol("ROL_ATAMA_DEGISTIRME"))):
    conn = None
    cursor = None
    if kullanici_id == islem_yapan_id:
        raise HTTPException(
            status_code=403,
            detail="Kendi rolünüzü değiştiremezsiniz."
        )

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()
        if islem_yapan is None:
            raise HTTPException(status_code=403, detail="Yetkisiz işlem.")
        islem_yapan_rol = islem_yapan[0]

        # KİLİT SIRASI (deadlock önleme): önce oda kilitleri, sonra kullanıcı satırı. Rezervasyon/randevu yolları oda kilidini alıp sonra
        # denetim kaydıyla kullanıcı satırını (FK) okur; burada tersi sıra (önce satır, sonra oda kilidi) karşılıklı beklemeye yol açıyordu.
        if veri.oda_idleri:
            etkinlik_oda_atama_kilitlerini_al(cursor, sorted(set(veri.oda_idleri)))

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef_kullanici = cursor.fetchone()
        if hedef_kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
        mevcut_rol = hedef_kullanici[0]

        cursor.execute("SELECT rol_adi, aktif_mi FROM roller WHERE rol_id = %s;", (veri.rol_id,))
        yeni_rol = cursor.fetchone()
        if yeni_rol is None:
            raise HTTPException(status_code=404, detail="Atanacak rol bulunamadı.")
        if len(yeni_rol) > 1 and yeni_rol[1] is False:
            raise HTTPException(status_code=422, detail=ROL_PASIF_ATAMA_MESAJI)
        yeni_rol_adi = yeni_rol[0]

        # ADMIN rolu normal rol degistirme islemlerine kapali.
        # ADMIN kullanicilar da bu kisitlamadan muaf degildir.
        if mevcut_rol == "ADMIN" or yeni_rol_adi == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="ADMIN rolü atanamaz veya başka bir role dönüştürülemez."
            )

        if hiyerarsi_ihlali_var_mi(islem_yapan_rol, mevcut_rol, yeni_rol_adi):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        if mevcut_rol == yeni_rol_adi:
            raise HTTPException(
                status_code=409,
                detail="Kullanıcı zaten seçilen role sahip."
            )

        # Her psikologun en az bir (aktif) odası olmalı: psikolog yapılırken oda seçilmesi zorunludur.
        psikolog_olacak = psikolog_rolu_mu(yeni_rol_adi)
        psikolog_idi = psikolog_rolu_mu(mevcut_rol)
        istenen_odalar = sorted(set(veri.oda_idleri or []))
        if psikolog_idi and not psikolog_olacak:
            # Psikologluktan çıkarken odaları kalkar: bugün ve sonrası için planlı randevusu varsa önce iptal edilmeli.
            psikolog_planli_randevulari_denetle(cursor, kullanici_id)
        if psikolog_olacak:
            if not istenen_odalar:
                raise HTTPException(
                    status_code=422,
                    detail="Psikolog rolü için en az bir görüşme odası seçilmelidir.",
                )
            cursor.execute(
                "SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;",
                (istenen_odalar,),
            )
            if {k[0] for k in cursor.fetchall()} != set(istenen_odalar):
                raise HTTPException(
                    status_code=422,
                    detail="Seçilen odalardan biri bulunamadı veya aktif değil.",
                )
            etkinlik_oda_atama_kilitlerini_al(
                cursor, istenen_odalar
            )
            cihaz_rezervasyonlu_odalari_denetle(cursor, istenen_odalar)
            oda_etkinlikli_odalari_denetle(cursor, istenen_odalar)
        elif istenen_odalar:
            raise HTTPException(
                status_code=422,
                detail="Oda yetkisi yalnızca psikolog rolü için tanımlanabilir.",
            )

        ogrenci_kaydi = None
        bilgi_var = any((veri.ad_soyad, veri.ogrenci_numarasi, veri.telefon))

        if yeni_rol_adi == "DANISMA_OGRENCISI":
            cursor.execute(
                "SELECT ogrenci_id, tur::text FROM ogrenciler "
                "WHERE kullanici_id = %s FOR UPDATE;",
                (kullanici_id,),
            )
            ogrenci_kaydi = cursor.fetchone()

            if ogrenci_kaydi is None and (
                not veri.ad_soyad or not veri.ogrenci_numarasi
            ):
                raise HTTPException(
                    status_code=422,
                    detail="Ad soyad ve öğrenci numarası zorunludur.",
                )
        elif bilgi_var:
            raise HTTPException(
                status_code=422,
                detail="Öğrenci bilgileri yalnızca Danışma Öğrencisi rolü içindir.",
            )

        # Danışma öğrencisi rolünden ayrılırken açık görev bulunmamalı.
        pasiflestirilecek_ogrenci_id = None

        if (
            mevcut_rol == "DANISMA_OGRENCISI"
            and yeni_rol_adi != "DANISMA_OGRENCISI"
        ):
            cursor.execute(
                "SELECT ogrenci_id FROM ogrenciler "
                "WHERE kullanici_id = %s FOR UPDATE;",
                (kullanici_id,),
            )
            onceki_ogrenci = cursor.fetchone()

            if onceki_ogrenci is not None:
                pasiflestirilecek_ogrenci_id = onceki_ogrenci[0]

                cursor.execute(
                    "SELECT 1 FROM danisma_masasi_oturumlari "
                    "WHERE ogrenci_id = %s "
                    "AND bitis_zamani IS NULL LIMIT 1;",
                    (pasiflestirilecek_ogrenci_id,),
                )

                if cursor.fetchone() is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Bu öğrencinin devam eden danışma masası "
                            "görevi bulunuyor. Önce görevi bitirin."
                        ),
                    )

        # Personel bilgisi kullanıcı satırındadır; mevcut personel_id korunacak.
        cursor.execute(
            "SELECT personel_id, personel_kodu FROM kullanicilar "
            "WHERE kullanici_id = %s AND personel_id IS NOT NULL FOR UPDATE;",
            (kullanici_id,),
        )
        personel = cursor.fetchone()

        if personel is None:
            raise HTTPException(
                status_code=409,
                detail="Kullanıcıya ait personel kaydı bulunamadı."
            )

        yeni_personel_kodu = _siradaki_personel_kodu(
            cursor, yeni_rol_adi
        )

        cursor.execute(
            "UPDATE kullanicilar SET rol_id = %s, personel_kodu = %s WHERE kullanici_id = %s;",
            (veri.rol_id, yeni_personel_kodu, kullanici_id),
        )
        if yeni_rol_adi == "DANISMA_OGRENCISI":
            if ogrenci_kaydi is None:
                cursor.execute(
                    "INSERT INTO ogrenciler "
                    "(kullanici_id, ad_soyad, ogrenci_numarasi, telefon, tur) "
                    "VALUES (%s, %s, %s, %s, 'DANISMA_MASASI') "
                    "RETURNING ogrenci_id;",
                    (
                        kullanici_id,
                        veri.ad_soyad,
                        veri.ogrenci_numarasi,
                        veri.telefon,
                    ),
                )
                ogrenci_id = cursor.fetchone()[0]
                ogrenci_olay = "CREATE"
            else:
                ogrenci_id = ogrenci_kaydi[0]
                ogrenci_olay = None
                if ogrenci_kaydi[1] != "DANISMA_MASASI":
                    cursor.execute(
                        "UPDATE ogrenciler "
                        "SET tur = 'DANISMA_MASASI', aktif_mi = TRUE "
                        "WHERE ogrenci_id = %s;",
                        (ogrenci_id,),
                    )
                    ogrenci_olay = "UPDATE"
                else:
                    cursor.execute(
                        "UPDATE ogrenciler SET aktif_mi = TRUE "
                        "WHERE ogrenci_id = %s AND aktif_mi = FALSE;",
                        (ogrenci_id,),
                    )
                    if cursor.rowcount > 0:
                        ogrenci_olay = "UPDATE"

            if ogrenci_olay:
                cursor.execute(
                    "INSERT INTO denetim_kayitlari "
                    "(kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) "
                    "VALUES (%s, %s, %s, %s);",
                    (islem_yapan_id, ogrenci_olay, "ogrenciler", ogrenci_id),
                )
        if pasiflestirilecek_ogrenci_id is not None:
            cursor.execute(
                "UPDATE ogrenciler SET aktif_mi = FALSE "
                "WHERE ogrenci_id = %s AND aktif_mi = TRUE;",
                (pasiflestirilecek_ogrenci_id,),
            )

            if cursor.rowcount > 0:
                cursor.execute(
                    "INSERT INTO denetim_kayitlari "
                    "(kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) "
                    "VALUES (%s, %s, %s, %s);",
                    (
                        islem_yapan_id,
                        "UPDATE",
                        "ogrenciler",
                        pasiflestirilecek_ogrenci_id,
                    ),
                )

        # Bir danışanın tek psikoloğu vardır: psikologluktan çıkan kişinin danışanları pasife alınır (randevu geçmişi korunur); yeniden
        # psikolog olunca yalnızca BU YÜZDEN pasifleşenler geri açılır (elle pasif olanlar pasif kalır). Pasif kullanıcıda geri açma bekler.
        danisan_sayisi = 0
        if psikolog_idi and not psikolog_olacak:
            cursor.execute(
                "UPDATE danisan_kodlari SET aktif_mi = FALSE, psikolog_pasifligi_nedeniyle_pasif = TRUE "
                "WHERE aktif_mi = TRUE AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s);",
                (kullanici_id,),
            )
        elif psikolog_olacak and not psikolog_idi:
            cursor.execute(
                "UPDATE danisan_kodlari SET aktif_mi = TRUE, psikolog_pasifligi_nedeniyle_pasif = FALSE "
                "WHERE psikolog_pasifligi_nedeniyle_pasif = TRUE "
                "AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s) "
                "AND EXISTS (SELECT 1 FROM kullanicilar WHERE kullanici_id = %s AND aktif_mi = TRUE);",
                (kullanici_id, kullanici_id),
            )
        if psikolog_idi != psikolog_olacak:
            danisan_sayisi = cursor.rowcount if isinstance(cursor.rowcount, int) else 0
            if danisan_sayisi:
                ayrintili_kayit_yaz(cursor, islem_yapan_id, "UPDATE", "danisan_kodlari", None, neden="psikolog rolünden çıkıldı" if psikolog_idi else "psikolog rolüne geri dönüldü",
                                    etkilenen_danisan=danisan_sayisi, aktif_mi="pasif" if psikolog_idi else "aktif", psikolog_kullanici_id=kullanici_id)

        # Oda yetkileri yalnızca psikologlar içindir: psikolog olurken verilen odalar yazılır,
        # psikologluktan çıkarken silinir (yeniden psikolog olursa odalar yeniden seçilir).
        if psikolog_olacak or psikolog_idi:
            onceki_odalar = psikolog_odalarini_oku(cursor, kullanici_id)
            cursor.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s;", (kullanici_id,))
            for oda_id in istenen_odalar:
                cursor.execute(
                    "INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s);",
                    (kullanici_id, oda_id),
                )
            psikolog_oda_degisikligini_yaz(cursor, islem_yapan_id, kullanici_id, onceki_odalar)

        rol_ayrintisi = {"onceki": {"rol": mevcut_rol, "personel_kodu": personel[1]}, "yeni": {"rol": yeni_rol_adi, "personel_kodu": yeni_personel_kodu}}
        if danisan_sayisi:
            rol_ayrintisi["pasife_alinan_danisan" if psikolog_idi else "aktif_edilen_danisan"] = danisan_sayisi
        ayrintili_kayit_yaz(cursor, islem_yapan_id, "ROLE_CHANGE", "kullanicilar", kullanici_id, **rol_ayrintisi)
        conn.commit()

        yanit = {"mesaj": "Kullanıcı rolü ve personel kodu başarıyla değiştirildi.", "kullanici_id": kullanici_id, "yeni_rol_id": veri.rol_id, "yeni_rol_adi": yeni_rol_adi, "yeni_personel_kodu": yeni_personel_kodu}
        if danisan_sayisi:
            if psikolog_idi:
                yanit["pasife_alinan_danisan"] = danisan_sayisi
                yanit["mesaj"] += f" {danisan_sayisi} danışan pasife alındı (psikolog yeniden psikolog olunca geri açılır)."
            else:
                yanit["aktif_edilen_danisan"] = danisan_sayisi
                yanit["mesaj"] += f" {danisan_sayisi} danışan yeniden aktif edildi."
        return yanit
    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Öğrenci numarası veya personel kodu zaten kullanılıyor.",
        )
    except DeadlockDetected:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=503, detail="İşlem eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/roller", status_code=201)
def rol_olustur(rol: RolModeli, kullanici_id: int = Depends(izin_kontrol("ROL_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        gorunen_ad = rol.rol_adi.strip()
        if not gorunen_ad:
            raise HTTPException(status_code=422, detail="Rol adı boş olamaz.")
 
        # Teknik ad: büyük harfe çevrilir. Yazılan ad olduğu gibi görünen ad olarak da saklanır.
        rol_adi_upper = gorunen_ad.upper()
 
        cursor.execute("SELECT 1 FROM roller WHERE rol_adi = %s;", (rol_adi_upper,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Bu rol zaten sistemde mevcut.")
 
        cursor.execute(
            "INSERT INTO roller (rol_adi, gorunen_ad) VALUES (%s, %s) RETURNING rol_id;",
            (rol_adi_upper, gorunen_ad),
        )
        yeni_id = cursor.fetchone()[0]
 
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="roller",
            hedef_kayit_id=yeni_id,
            mevcut_cursor=cursor,
            ayrinti={"yeni": {"rol_adi": rol_adi_upper, "gorunen_ad": gorunen_ad}},
        )
        conn.commit()
        return {
            "durum": "basarili",
            "mesaj": "Rol başarıyla oluşturuldu.",
            "rol_id": yeni_id,
            "rol_adi": rol_adi_upper,
            "gorunen_ad": gorunen_ad,
        }
    except HTTPException:
        if conn:
            conn.rollback()
        raise
    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Rol oluşturulurken bir hata oluştu.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
 
 
# Giriş ekranı ve sunucu kontrolleri bu rollerin teknik adlarına bağlıdır.
# (Modül düzeyinde tanımlanmalıdır; bir fonksiyonun içine yazılmaz.)
SISTEM_ROLLERI = {"ADMIN", "PSIKOLOG", "MEMUR", "MUDUR", "DANISMA_OGRENCISI", "PROJE_ASISTANI"}
 
 
@app.put("/api/roller/{rol_id}")
def rol_guncelle(rol_id: int, veri: RolGorunenAdModeli, kullanici_id: int = Depends(izin_kontrol("ROL_DUZENLE"))):
    """Rolün görünür adını ve aktiflik durumunu günceller."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        # 1. Rolün teknik adını (rol_adi) çekip satırı kilitliyoruz
        cursor.execute("SELECT rol_adi, aktif_mi, gorunen_ad FROM roller WHERE rol_id = %s FOR UPDATE;", (rol_id,))
        kayit = cursor.fetchone()
        
        if kayit is None:
            raise HTTPException(status_code=404, detail="Güncellenecek rol bulunamadı.")
 
        # 2. GÜVENLİK KİLİDİ: Admin rolü asla değiştirilemez veya pasife alınamaz!
        if kayit[0] == "ADMIN":
            raise HTTPException(status_code=403, detail="SİSTEM UYARISI: ADMIN rolü düzenlenemez ve pasife alınamaz.")

        # 3. Pasif rol = o roldeki kullanıcılar sisteme giremez (giriş ve her istek rol aktifliğini denetler). Kişi kendi rolünü
        #    pasife alıp kendini dışarıda bırakamaz.
        etkilenen = 0
        onceki_aktif = kayit[1] if len(kayit) > 1 else True
        if veri.aktif_mi is False and onceki_aktif is not False:
            cursor.execute("SELECT rol_id FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
            yapan = cursor.fetchone()
            if yapan is not None and yapan[0] == rol_id:
                raise HTTPException(status_code=409, detail="Kendi rolünüzü pasife alamazsınız; oturumunuz kapanırdı.")
            cursor.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol_id = %s AND aktif_mi = TRUE;", (rol_id,))
            etkilenen = cursor.fetchone()[0]
 
        # 4. Güncelleme işlemi
        cursor.execute(
            "UPDATE roller SET gorunen_ad = %s, aktif_mi = %s WHERE rol_id = %s;",
            (veri.gorunen_ad.strip(), veri.aktif_mi, rol_id),
        )

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="roller",
            hedef_kayit_id=rol_id,
            mevcut_cursor=cursor,
            ayrinti={
                "onceki": {"gorunen_ad": kayit[2] if len(kayit) > 2 else None, "aktif_mi": onceki_aktif},
                "yeni": {"gorunen_ad": veri.gorunen_ad.strip(), "aktif_mi": veri.aktif_mi},
                "girisi_engellenen_kullanici": etkilenen,
            },
        )
        conn.commit()
        yanit = {"durum": "basarili", "mesaj": "Rol güncellendi."}
        if etkilenen:
            yanit["etkilenen_kullanici"] = etkilenen
            yanit["mesaj"] = f"Rol pasife alındı; bu roldeki {etkilenen} aktif kullanıcının sisteme girişi engellendi."
        return yanit
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Rol güncellenirken bir hata oluştu.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
 
@app.delete("/api/roller/{rol_id}")
def rol_sil(rol_id: int, kullanici_id: int = Depends(izin_kontrol("ROL_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        cursor.execute("SELECT rol_adi FROM roller WHERE rol_id = %s FOR UPDATE;", (rol_id,))
        rol = cursor.fetchone()
        if rol is None:
            raise HTTPException(status_code=404, detail="Silinecek rol bulunamadı.")
 
        if rol[0] in SISTEM_ROLLERI:
            raise HTTPException(status_code=403, detail="Sistem rolleri silinemez.")
 
        cursor.execute("SELECT COUNT(*) FROM kullanicilar WHERE rol_id = %s;", (rol_id,))
        kullanici_sayisi = cursor.fetchone()[0]
        if kullanici_sayisi > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Bu role atanmış {kullanici_sayisi} kullanıcı var. Önce kullanıcıların rolünü değiştirin.",
            )
 
        # Yalnızca gerçekten verilmiş izinler sayılır (izin_var = 1).
        cursor.execute("SELECT COUNT(*) FROM rol_izinleri WHERE rol_id = %s AND izin_var = 1;", (rol_id,))
        izin_sayisi = cursor.fetchone()[0]
        if izin_sayisi > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Bu role ait {izin_sayisi} izin var. Silmek için önce izinleri kaldırın.",
            )
 
        cursor.execute("DELETE FROM rol_izinleri WHERE rol_id = %s;", (rol_id,))
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "roller", rol_id)
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="DELETE",
            kullanici_id=kullanici_id,
            hedef_tablo="roller",
            hedef_kayit_id=rol_id,
            mevcut_cursor=cursor,
            ayrinti=silinen,
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": f"'{rol[0]}' rolü silindi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Rol silinirken bir hata oluştu.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
 
 

def _atanabilir_rolleri_getir():
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rol_id, rol_adi, gorunen_ad
            FROM roller
            WHERE aktif_mi = TRUE
              AND UPPER(rol_adi) <> 'ADMIN'
            ORDER BY rol_id;
        """)
        return [
            {
                "rol_id": kayit[0],
                "rol_adi": kayit[1],
                "gorunen_ad": kayit[2] or kayit[1],
            }
            for kayit in cursor.fetchall()
        ]
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Atanabilir roller alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/api/roller/atanabilir/olusturma")
def olusturma_rolleri(
    kullanici_id: int = Depends(izin_kontrol("KULLANICI_OLUSTUR"))
):
    return _atanabilir_rolleri_getir()


@app.get("/api/roller/atanabilir/degistirme")
def degistirme_rolleri(
    kullanici_id: int = Depends(izin_kontrol("ROL_ATAMA_DEGISTIRME"))
):
    return _atanabilir_rolleri_getir()


@app.get("/api/roller")
def rolleri_listele(kullanici_id: int = Depends(izin_kontrol("ROL_IZIN_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT r.rol_id, r.rol_adi, r.gorunen_ad, r.aktif_mi, "
            "(SELECT COUNT(*) FROM kullanicilar k WHERE k.rol_id = r.rol_id AND k.aktif_mi = TRUE) "
            "FROM roller r ORDER BY r.rol_id ASC;"
        )
        return [
            {"rol_id": k[0], "rol_adi": k[1], "gorunen_ad": k[2], "aktif_mi": k[3], "aktif_kullanici_sayisi": k[4] if len(k) > 4 else 0}
            for k in cursor.fetchall()
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Roller alınamadı.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
 
@app.get("/api/roller/{rol_id}/yetki-ozeti")
def rol_yetki_ozeti(rol_id: int, kullanici_id: int = Depends(izin_kontrol("KULLANICI_OLUSTUR"))):
    """Bir rolün yapabildiği işlemlerin özeti (kullanıcı oluştururken 'bu rol neler yapabilir?').

    Yalnızca o role AÇIK izinler döner. Kullanıcı oluşturabilen herkes görebilsin diye
    rol yönetim izni (ROL_IZIN_YONET) değil KULLANICI_OLUSTUR istenir.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT rol_id, rol_adi, gorunen_ad FROM roller WHERE rol_id = %s;", (rol_id,))
        rol = cursor.fetchone()
        if rol is None:
            raise HTTPException(status_code=404, detail="Rol bulunamadı.")
        cursor.execute(
            """
            SELECT i.izin_adi, i.gorunen_ad
            FROM rol_izinleri ri
            JOIN izinler i ON i.izin_id = ri.izin_id
            WHERE ri.rol_id = %s AND ri.izin_var = 1
            ORDER BY i.izin_id ASC;
            """,
            (rol_id,),
        )
        return {
            "rol_id": rol[0],
            "rol_adi": rol[1],
            "gorunen_ad": rol[2],
            "izinler": [{"izin_adi": k[0], "gorunen_ad": k[1] or k[0]} for k in cursor.fetchall()],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Rol yetkileri alınamadı.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.get("/api/rol-izin-matrisi")
def rol_izin_matrisi_getir(kullanici_id: int = Depends(izin_kontrol("ROL_IZIN_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        
        # 1. Tüm Rolleri Çek
        cursor.execute("SELECT rol_id, rol_adi, gorunen_ad, aktif_mi FROM roller ORDER BY rol_id ASC")
        roller = [{"rol_id": r[0], "rol_adi": r[1], "gorunen_ad": r[2], "aktif_mi": r[3]} for r in cursor.fetchall()]
        
        # 2. Tüm İzinleri (Faaliyetleri/Yetkileri) Çek
        cursor.execute("SELECT izin_id, izin_adi, gorunen_ad FROM izinler ORDER BY izin_id ASC")
        izinler = [{"izin_id": i[0], "izin_adi": i[1], "gorunen_ad": i[2]} for i in cursor.fetchall()]
        
        # 3. Rol-İzin Eşleşmelerini Çek
        cursor.execute("SELECT rol_id, izin_id FROM rol_izinleri WHERE izin_var = 1")
        eslesmeler = cursor.fetchall()
        
        # Hangi rolün hangi izinleri olduğunu bir sözlükte topla (rol_id: [izin_id1, izin_id2...])
        rol_izin_map = {}
        for r_id, i_id in eslesmeler:
            if r_id not in rol_izin_map:
                rol_izin_map[r_id] = []
            rol_izin_map[r_id].append(i_id)
            
        return {
            "roller": roller,
            "izinler": izinler,
            "rol_izin_map": rol_izin_map
        }
        
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Rol ve izin bilgileri alınamadı."
        )
    finally:
        if cursor: cursor.close()
        if conn: conn.close()



YONETICI_PAROLASI_ENGEL_MESAJI = (
    "Yönetici (ADMIN) hesaplarının parolası uygulamadan sıfırlanamaz; başka bir yönetici de sıfırlayamaz. "
    "Sunucu bilgisayarında kurtarma aracı kullanılmalıdır (scripts/admin_parola_kurtar.py)."
)


@app.post("/api/kullanicilar/{kullanici_id}/parola-sifirla")
def kullanici_parola_sifirla(
    kullanici_id: int,
    response: Response,
    islem_yapan_id: int = Depends(izin_kontrol("KULLANICI_PAROLA_SIFIRLA"))
):
    """Yalnızca ADMIN başka bir aktif kullanıcının parolasını sıfırlar."""

    if kullanici_id == islem_yapan_id:
        raise HTTPException(
            status_code=403,
            detail="Kendi parolanızı bu işlemle sıfırlayamazsınız."
        )

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kullanıcı arayüzüne güvenmeden sunucuda ADMIN kontrolü
        cursor.execute(
            """
            SELECT r.rol_adi
            FROM kullanicilar k
            JOIN roller r ON r.rol_id = k.rol_id
            WHERE k.kullanici_id = %s;
            """,
            (islem_yapan_id,)
        )
        yonetici = cursor.fetchone()

        if yonetici is None or yonetici[0] != "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="Bu işlem yalnızca ADMIN tarafından yapılabilir."
            )

        cursor.execute(
            """
            SELECT k.aktif_mi, r.rol_adi
            FROM kullanicilar k
            LEFT JOIN roller r ON r.rol_id = k.rol_id
            WHERE k.kullanici_id = %s
            FOR UPDATE OF k;
            """,
            (kullanici_id,)
        )
        hedef = cursor.fetchone()

        if hedef is None:
            raise HTTPException(
                status_code=404,
                detail="Kullanıcı bulunamadı."
            )

        # Yönetici hesapları uygulamadan sıfırlanamaz: bir yöneticinin başka bir yönetici hesabını ele geçirmesi engellenir.
        # Tek yol, sunucu bilgisayarındaki kurtarma aracıdır (kimin çalıştırdığı günlüğe yazılır).
        if len(hedef) > 1 and hedef[1] == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail=YONETICI_PAROLASI_ENGEL_MESAJI
            )

        if not hedef[0]:
            raise HTTPException(
                status_code=409,
                detail="Pasif kullanıcının parolası sıfırlanamaz."
            )

        gecici_parola = gecici_parola_uret()
        yeni_hash = parola_hashle(gecici_parola)

        cursor.execute(
            f"""
            UPDATE kullanicilar
            SET parola_hash = %s,
                ilk_giris_mi = TRUE,
                basarisiz_giris_sayisi = 0,
                kilit_bitis_zamani = NULL,
                gecici_parola_bitis = {GECICI_PAROLA_BITIS_SQL}
            WHERE kullanici_id = %s;
            """,
            (yeni_hash, kullanici_id)
        )

        cursor.execute(
            """
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
            """,
            (
                islem_yapan_id,
                "PASSWORD_RESET",
                "kullanicilar",
                kullanici_id
            )
        )

        # Bu kullanıcının bekleyen parola sıfırlama talebi varsa karşılanmış olur.
        cursor.execute(
            """
            UPDATE parola_sifirlama_talepleri
            SET durum = 'TAMAMLANDI', kapanis_zamani = CURRENT_TIMESTAMP, kapatan_kullanici_id = %s
            WHERE kullanici_id = %s AND durum = 'ACIK';
            """,
            (islem_yapan_id, kullanici_id)
        )

        conn.commit()

        response.headers["Cache-Control"] = "no-store"

        return {
            "durum": "basarili",
            "mesaj": "Geçici parola oluşturuldu.",
            "kullanici_id": kullanici_id,
            "gecici_parola": gecici_parola,
            "gecici_parola_gecerlilik_saat": GECICI_PAROLA_GECERLILIK_SAAT
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Parola sıfırlama işlemi tamamlanamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# ==========================================
# PAROLA SIFIRLAMA TALEPLERI
# Kullanıcı giriş ekranından yöneticiye bildirir; yönetici bildirimden görüp parolayı sıfırlar.
# ==========================================
PAROLA_TALEBI_ACIK_UST_SINIR = 50
# Kapalı ofis ağında kullanıcı adları gizli değildir; kullanıcı, yazım hatasını hemen anlasın diye var olmayan ve pasif
# hesaplar açıkça söylenir. (Giriş ekranı ise bilerek "kullanıcı adı veya parola hatalı" der.)
PAROLA_TALEBI_ALINDI_MESAJI = "Talebiniz yöneticiye iletildi. Geçici parolanızı yöneticinizden alın."
PAROLA_TALEBI_ZATEN_VAR_MESAJI = "Bu hesap için zaten bekleyen bir talebiniz var. Yöneticinizin size dönmesini bekleyin."
PAROLA_TALEBI_KULLANICI_YOK_MESAJI = "Bu kullanıcı adıyla kayıtlı bir hesap bulunamadı. Yazımı kontrol edip tekrar deneyin."
PAROLA_TALEBI_HESAP_PASIF_MESAJI = "Bu hesap pasif. Lütfen yöneticinize başvurun."
PAROLA_TALEBI_HESAP_YONETICI_MESAJI = (
    "Bu bir yönetici hesabı; parolası uygulamadan sıfırlanamaz. Sunucu bilgisayarından sorumlu kişiye (sistem sorumlusu) başvurun."
)


@app.post("/api/parola-sifirlama-talebi")
def parola_sifirlama_talebi_olustur(talep: ParolaSifirlamaTalebiModeli):
    """Giriş yapmadan parola sıfırlama talebi açar.

    Var olmayan kullanıcı adı 404 (KULLANICI_BULUNAMADI), pasif hesap 403 (HESAP_PASIF) ile açıkça bildirilir; bu
    durumlarda talep kaydedilmez. Her kullanıcı için en fazla bir açık talep tutulur (varsa durum "zaten_var")."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT k.kullanici_id, k.aktif_mi, r.rol_adi
            FROM kullanicilar k
            LEFT JOIN roller r ON r.rol_id = k.rol_id
            WHERE LOWER(k.kullanici_adi) = LOWER(%s)
            ORDER BY (k.kullanici_adi = %s) DESC
            LIMIT 1;
            """,
            (talep.kullanici_adi, talep.kullanici_adi)      # girişle aynı kural: kullanıcı adı harf duyarsız
        )
        kullanici = cursor.fetchone()
        alindi = {"durum": "alindi", "mesaj": PAROLA_TALEBI_ALINDI_MESAJI}
        zaten_var = {"durum": "zaten_var", "mesaj": PAROLA_TALEBI_ZATEN_VAR_MESAJI}

        if kullanici is None:
            raise HTTPException(
                status_code=404,
                detail={"kod": "KULLANICI_BULUNAMADI", "mesaj": PAROLA_TALEBI_KULLANICI_YOK_MESAJI},
            )
        if not kullanici[1]:
            raise HTTPException(
                status_code=403,
                detail={"kod": "HESAP_PASIF", "mesaj": PAROLA_TALEBI_HESAP_PASIF_MESAJI},
            )
        if len(kullanici) > 2 and kullanici[2] == "ADMIN":
            # Yönetici hesapları uygulamadan sıfırlanamadığı için talep açmak anlamsızdır (kimse karşılayamaz): kaydedilmez.
            raise HTTPException(
                status_code=403,
                detail={"kod": "HESAP_YONETICI", "mesaj": PAROLA_TALEBI_HESAP_YONETICI_MESAJI},
            )

        cursor.execute(
            "SELECT 1 FROM parola_sifirlama_talepleri WHERE kullanici_id = %s AND durum = 'ACIK';",
            (kullanici[0],)
        )
        if cursor.fetchone() is not None:
            return zaten_var                           # zaten bekleyen talebi var

        cursor.execute("SELECT COUNT(*) FROM parola_sifirlama_talepleri WHERE durum = 'ACIK';")
        if cursor.fetchone()[0] >= PAROLA_TALEBI_ACIK_UST_SINIR:
            raise HTTPException(
                status_code=429,
                detail="Çok fazla bekleyen talep var. Lütfen yöneticinize doğrudan ulaşın."
            )

        cursor.execute(
            """
            INSERT INTO parola_sifirlama_talepleri (kullanici_id)
            VALUES (%s)
            ON CONFLICT (kullanici_id) WHERE durum = 'ACIK' DO NOTHING
            RETURNING talep_id;
            """,
            (kullanici[0],)
        )
        yeni = cursor.fetchone()
        if yeni is None:
            return zaten_var                           # eşzamanlı başka bir istek az önce açtı
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici[0],
            hedef_tablo="parola_sifirlama_talepleri", hedef_kayit_id=yeni[0], mevcut_cursor=cursor
        )
        conn.commit()
        return alindi

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Talep şu anda alınamadı. Lütfen daha sonra tekrar deneyin.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/api/parola-sifirlama-talepleri")
def parola_sifirlama_taleplerini_listele(
    response: Response,
    kullanici_id: int = Depends(izin_kontrol("KULLANICI_PAROLA_SIFIRLA"))
):
    """Bekleyen (açık) parola sıfırlama talepleri; en eski talep önce."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.talep_id, k.kullanici_id, k.kullanici_adi, r.rol_adi, t.talep_zamani,
                   FLOOR(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - t.talep_zamani)) / 60)::int
            FROM parola_sifirlama_talepleri t
            JOIN kullanicilar k ON k.kullanici_id = t.kullanici_id
            LEFT JOIN roller r ON r.rol_id = k.rol_id
            WHERE t.durum = 'ACIK' AND k.aktif_mi AND r.rol_adi IS DISTINCT FROM 'ADMIN'
            ORDER BY t.talep_zamani, t.talep_id;
            """
        )
        response.headers["Cache-Control"] = "no-store"
        return [
            {
                "talep_id": s[0], "kullanici_id": s[1], "kullanici_adi": s[2], "rol_adi": s[3],
                "talep_zamani": s[4].isoformat(), "bekleme_dakika": max(int(s[5] or 0), 0),
            }
            for s in cursor.fetchall()
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Parola sıfırlama talepleri alınamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.patch("/api/parola-sifirlama-talepleri/{talep_id}/kapat")
def parola_sifirlama_talebini_kapat(
    talep_id: int,
    islem_yapan_id: int = Depends(izin_kontrol("KULLANICI_PAROLA_SIFIRLA"))
):
    """Bekleyen bir talebi parolayı sıfırlamadan kapatır (örn. kullanıcı parolasını hatırladı)."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE parola_sifirlama_talepleri
            SET durum = 'KAPATILDI', kapanis_zamani = CURRENT_TIMESTAMP, kapatan_kullanici_id = %s
            WHERE talep_id = %s AND durum = 'ACIK'
            RETURNING talep_id;
            """,
            (islem_yapan_id, talep_id)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Bekleyen talep bulunamadı.")
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, olay_turu="UPDATE", kullanici_id=islem_yapan_id,
            hedef_tablo="parola_sifirlama_talepleri", hedef_kayit_id=talep_id, mevcut_cursor=cursor
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Talep kapatıldı."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="Talep kapatılamadı.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


from pydantic import BaseModel as _DurumBaseModel, Field as _DurumField


class DurumDegistirModeli(_DurumBaseModel):
    """Psikolog aktifleştirilirken görüşme odaları seçilir; diğer durumlarda gövde gerekmez."""
    oda_idleri: list[int] | None = _DurumField(default=None, max_length=100)


@app.patch("/api/kullanicilar/{kullanici_id}/durum-degistir")
def kullanici_durum_degistir(
    kullanici_id: int,
    veri: DurumDegistirModeli | None = None,
    islem_yapan_id: int = Depends(izin_kontrol("KULLANICI_PASIFLESTIR")),
):
    """Kullanıcıyı aktif/pasif yapar (geçiş).

    Psikolog pasife alınırken: bugün ve sonrası için planlı randevusu varsa işlem 409 ile reddedilir; yoksa kendi danışanları da pasife
    alınır (yanıtta pasife_alinan_danisan; yeniden aktifleşince yalnızca bu yüzden pasifleşenler geri açılır, aktif_edilen_danisan) ve oda atamaları kaldırılır
    (geçmiş randevular ve raporlar etkilenmez, çünkü oda bilgisi randevunun kendisinde durur). Psikolog aktife alınırken en az
    bir görüşme odası seçilmelidir (oda_idleri); seçilen odalar cihaz rezervasyonu için kullanılıyorsa 409 döner."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        if kullanici_id == islem_yapan_id:
            raise HTTPException(status_code=403, detail="Kendi hesabınızın durumunu değiştiremezsiniz.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()

        # KİLİT SIRASI (deadlock önleme): önce oda kilitleri, sonra kullanıcı satırı. Rezervasyon/randevu yolları oda kilidini alıp sonra
        # denetim kaydıyla kullanıcı satırını (FK) okur; burada tersi sıra (önce satır, sonra oda kilidi) karşılıklı beklemeye yol açıyordu.
        if veri is not None and veri.oda_idleri:
            etkinlik_oda_atama_kilitlerini_al(cursor, sorted(set(veri.oda_idleri)))

        cursor.execute("SELECT r.rol_adi, k.aktif_mi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef = cursor.fetchone()
        
        if hedef is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

        hedef_rol, mevcut_durum = hedef
        if hedef_rol == "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="ADMIN kullanıcısının aktiflik durumu değiştirilemez."
            )

        if hiyerarsi_ihlali_var_mi(islem_yapan[0] if islem_yapan else None, hedef_rol):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        # YENİ MANTIK: Mevcut durum neyse tam tersini yap (Toggle)
        yeni_durum = not mevcut_durum

        psikolog_mu = psikolog_rolu_mu(hedef_rol)
        istenen_odalar = sorted(set((veri.oda_idleri if veri is not None else None) or []))
        psikolog_aktiflesiyor = psikolog_mu and yeni_durum
        psikolog_pasiflesiyor = psikolog_mu and not yeni_durum

        if istenen_odalar and not psikolog_aktiflesiyor:
            raise HTTPException(status_code=422, detail="Oda seçimi yalnızca psikolog aktifleştirilirken yapılır.")

        if psikolog_aktiflesiyor:
            # Her psikologun en az bir (aktif) odası olmalı; pasife alınırken odalar kaldırıldığı için yeniden seçilir.
            if not istenen_odalar:
                raise HTTPException(status_code=422, detail="Psikolog aktifleştirilirken en az bir görüşme odası seçilmelidir.")
            cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;", (istenen_odalar,))
            if {k[0] for k in cursor.fetchall()} != set(istenen_odalar):
                raise HTTPException(status_code=422, detail="Seçilen odalardan biri bulunamadı veya aktif değil.")
            etkinlik_oda_atama_kilitlerini_al(
                cursor, istenen_odalar
            )
            cihaz_rezervasyonlu_odalari_denetle(cursor, istenen_odalar)
            oda_etkinlikli_odalari_denetle(cursor, istenen_odalar)
        elif psikolog_pasiflesiyor:
            # Oda boşa düşeceği için bugün ve sonrasındaki planlı randevular önce sonuçlandırılmalı ya da iptal edilmeli. Dünden önceki kayıtlar engellemez.
            cursor.execute(
                "SELECT COUNT(*) FROM randevular r JOIN personel p ON p.personel_id = r.psikolog_id "
                "WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani >= CURRENT_DATE;",
                (kullanici_id,),
            )
            planli = cursor.fetchone()[0]
            if planli:
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu psikologun bugün ve sonrası için {planli} planlı randevusu var. Pasife almadan önce {PLANLI_RANDEVU_COZUMU}",
                )

        # Tek aktiflik bilgisi kullanıcı satırındadır (personel görünümü bunu okur).
        cursor.execute("UPDATE kullanicilar SET aktif_mi = %s WHERE kullanici_id = %s;", (yeni_durum, kullanici_id))

        danisan_sayisi = 0
        if psikolog_mu:
            # Bir danışanın tek psikoloğu vardır: psikolog pasife alınınca kendi danışanları da pasife alınır (randevu geçmişi korunur).
            # Yeniden aktifleşince yalnızca BU YÜZDEN pasifleşenler geri açılır; daha önce elle pasife alınmış danışanlar pasif kalır.
            if psikolog_pasiflesiyor:
                cursor.execute(
                    "UPDATE danisan_kodlari SET aktif_mi = FALSE, psikolog_pasifligi_nedeniyle_pasif = TRUE "
                    "WHERE aktif_mi = TRUE AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s);",
                    (kullanici_id,),
                )
            else:
                cursor.execute(
                    "UPDATE danisan_kodlari SET aktif_mi = TRUE, psikolog_pasifligi_nedeniyle_pasif = FALSE "
                    "WHERE psikolog_pasifligi_nedeniyle_pasif = TRUE AND olusturan_psikolog_id IN (SELECT personel_id FROM personel WHERE kullanici_id = %s);",
                    (kullanici_id,),
                )
            danisan_sayisi = cursor.rowcount
            if danisan_sayisi:
                ayrintili_kayit_yaz(cursor, islem_yapan_id, "UPDATE", "danisan_kodlari", None, neden="psikolog pasife alındı" if psikolog_pasiflesiyor else "psikolog aktif edildi",
                                    etkilenen_danisan=danisan_sayisi, aktif_mi="pasif" if psikolog_pasiflesiyor else "aktif", psikolog_kullanici_id=kullanici_id)

            # Pasifte oda ataması kalkar; aktifleşirken seçilen odalar yazılır (eski artık kayıtlar varsa değiştirilir).
            onceki_odalar = psikolog_odalarini_oku(cursor, kullanici_id)
            cursor.execute("DELETE FROM psikolog_odalar WHERE kullanici_id = %s;", (kullanici_id,))
            for oda_id in istenen_odalar:
                cursor.execute("INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s);", (kullanici_id, oda_id))
            psikolog_oda_degisikligini_yaz(cursor, islem_yapan_id, kullanici_id, onceki_odalar)

        durum_ayrintisi = {"rol": hedef_rol}
        if psikolog_mu and danisan_sayisi:
            durum_ayrintisi["etkilenen_danisan"] = danisan_sayisi
        durum_degisikligi_yaz(cursor, islem_yapan_id, "UPDATE", "kullanicilar", kullanici_id, onceki={"aktif_mi": mevcut_durum}, yeni={"aktif_mi": yeni_durum}, **durum_ayrintisi)
        conn.commit()

        yanit = {"mesaj": "Durum başarıyla güncellendi.", "kullanici_id": kullanici_id, "yeni_durum": yeni_durum}
        if psikolog_pasiflesiyor:
            yanit["pasife_alinan_danisan"] = danisan_sayisi
        elif psikolog_aktiflesiyor:
            yanit["aktif_edilen_danisan"] = danisan_sayisi
        return yanit
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except DeadlockDetected:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=503, detail="İşlem eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/personel", status_code=201)
def personel_olustur(yeni_personel: PersonelOlusturModeli, islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    asama = "personel"
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Hedef kullanıcının durumu/rolü ve işlemi yapanın rolü tek sorguda alınır (rol hiyerarşisi denetimi için).
        cursor.execute(
            "SELECT k.aktif_mi, r.rol_adi, "
            "(SELECT ry.rol_adi FROM kullanicilar ky JOIN roller ry ON ry.rol_id = ky.rol_id WHERE ky.kullanici_id = %s) "
            "FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;",
            (islem_yapan_id, yeni_personel.kullanici_id),
        )
        kullanici = cursor.fetchone()
        if kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı hesabı bulunamadı.")
        # Kullanıcı yönetimindeki kural personel kaydında da geçerli: kendi seviyesindeki ya da üstündeki rolün kaydına dokunulamaz.
        if hiyerarsi_ihlali_var_mi(kullanici[2], kullanici[1]):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)
        if not kullanici[0]:
            raise HTTPException(status_code=422, detail="Pasif kullanıcı için personel kaydı oluşturulamaz.")

        # Danışma öğrencisi için aynı işlemde öğrenci kaydı da oluşturulur (Danışma Masası
        # ve faaliyet listeleri bu kaydı kullanır). Diğer roller için öğrenci bilgisi kabul edilmez.
        danisma_ogrencisi = kullanici[1] == "DANISMA_OGRENCISI"
        ogrenci_bilgisi_var = any([yeni_personel.ad_soyad, yeni_personel.ogrenci_numarasi, yeni_personel.telefon])
        if danisma_ogrencisi:
            if not yeni_personel.ad_soyad or not yeni_personel.ogrenci_numarasi:
                raise HTTPException(status_code=422, detail="Danışma öğrencisi için ad soyad ve öğrenci numarası zorunludur.")
        elif ogrenci_bilgisi_var:
            raise HTTPException(status_code=422, detail="Öğrenci bilgileri yalnızca danışma öğrencisi rolü için girilebilir.")

        personel_id = personel_kaydi_ata(cursor, yeni_personel.kullanici_id, yeni_personel.personel_kodu.strip())
        if personel_id is None:
            raise psycopg2.errors.UniqueViolation("Kullanıcının personel kaydı zaten mevcut.")

        ayrintili_kayit_yaz(cursor, islem_yapan_id, "UPDATE", "kullanicilar", yeni_personel.kullanici_id, neden="personel kaydı verildi", personel_kodu=yeni_personel.personel_kodu.strip())

        ogrenci_id = None
        if danisma_ogrencisi:
            cursor.execute("SELECT ogrenci_id FROM ogrenciler WHERE kullanici_id = %s;", (yeni_personel.kullanici_id,))
            mevcut_ogrenci = cursor.fetchone()
            if mevcut_ogrenci is not None:
                ogrenci_id = mevcut_ogrenci[0]
            else:
                asama = "ogrenci"
                cursor.execute(
                    "INSERT INTO ogrenciler (kullanici_id, ad_soyad, ogrenci_numarasi, telefon, tur) VALUES (%s, %s, %s, %s, 'DANISMA_MASASI') RETURNING ogrenci_id;",
                    (yeni_personel.kullanici_id, yeni_personel.ad_soyad, yeni_personel.ogrenci_numarasi, yeni_personel.telefon)
                )
                ogrenci_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "CREATE", "ogrenciler", ogrenci_id))
        conn.commit()

        return {
            "mesaj": "Personel başarıyla oluşturuldu.",
            "personel_id": personel_id,
            "kullanici_id": yeni_personel.kullanici_id,
            "personel_kodu": yeni_personel.personel_kodu.strip(),
            "aktif_mi": True,
            "ogrenci_id": ogrenci_id
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        if asama == "ogrenci":
            raise HTTPException(status_code=409, detail="Bu öğrenci numarası başka bir öğrenci kaydında kullanılıyor.")
        raise HTTPException(status_code=409, detail="Bu kullanıcıya ait personel kaydı veya personel kodu zaten mevcut.")
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/personel")
def personel_listele(islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, p.kullanici_id, k.kullanici_adi, p.personel_kodu, r.rol_adi, p.aktif_mi, p.olusturulma_tarihi, r.gorunen_ad
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id ORDER BY p.personel_id;
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "kullanici_id": k[1], "kullanici_adi": k[2], "personel_kodu": k[3], "rol_adi": k[4], "aktif_mi": k[5], "olusturulma_tarihi": k[6], "gorunen_ad": (k[7] if len(k) > 7 and k[7] else k[4])} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/kullanicilar/personel-olmayanlar")
def personel_olmayan_kullanicilari_listele(islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece henüz personel tablosunda kaydı OLMAYAN aktif kullanıcıları getirir
        cursor.execute("""
            SELECT k.kullanici_id, k.kullanici_adi, r.rol_adi 
            FROM kullanicilar k 
            JOIN roller r ON k.rol_id = r.rol_id 
            LEFT JOIN personel p ON k.kullanici_id = p.kullanici_id
            WHERE p.personel_id IS NULL AND k.aktif_mi = TRUE
            ORDER BY k.kullanici_adi;
        """)
        kayitlar = cursor.fetchall()
        return [{"kullanici_id": k[0], "kullanici_adi": k[1], "rol_adi": k[2]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/personel/{personel_id}")
def personel_detay(personel_id: int, islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    if personel_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Geçerli bir personel ID girilmelidir."
        )

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, p.kullanici_id, k.kullanici_adi, p.personel_kodu, r.rol_adi, p.aktif_mi, p.olusturulma_tarihi
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id WHERE p.personel_id = %s;
        """, (personel_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Personel bulunamadı.")
        return {"personel_id": kayit[0], "kullanici_id": kayit[1], "kullanici_adi": kayit[2], "personel_kodu": kayit[3], "rol_adi": kayit[4], "aktif_mi": kayit[5], "olusturulma_tarihi": kayit[6]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/personel/{personel_id}")
def personel_guncelle(personel_id: int, guncelleme: PersonelGuncelleModeli, islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    degisiklikler = guncelleme.model_dump(exclude_unset=True)
    if not degisiklikler or any(deger is None for deger in degisiklikler.values()):
        raise HTTPException(status_code=422, detail="En az bir geçerli güncelleme alanı gönderilmelidir.")
    if "personel_kodu" in degisiklikler:
        degisiklikler["personel_kodu"] = degisiklikler["personel_kodu"].strip()

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT k.personel_id, k.personel_kodu, k.aktif_mi, k.kullanici_id, r.rol_adi, "
            "(SELECT ry.rol_adi FROM kullanicilar ky JOIN roller ry ON ry.rol_id = ky.rol_id WHERE ky.kullanici_id = %s) "
            "FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id WHERE k.personel_id = %s FOR UPDATE OF k;",
            (islem_yapan_id, personel_id),
        )
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Personel bulunamadı.")
        # Örn. müdür, ADMIN'in ya da başka bir müdürün personel kodunu değiştiremez (ADMIN için hiyerarşi engel olmaz).
        if hiyerarsi_ihlali_var_mi(mevcut[5], mevcut[4]):
            raise HTTPException(status_code=403, detail=HIYERARSI_MESAJI)

        # Yalnızca personel kodu değişir; aktiflik kullanıcı durum ucundan yönetilir (kurallar atlanmasın).
        yeni_kod = degisiklikler.get("personel_kodu", mevcut[1])

        cursor.execute("UPDATE kullanicilar SET personel_kodu = %s WHERE personel_id = %s;", (yeni_kod, personel_id))
        durum_degisikligi_yaz(cursor, islem_yapan_id, "UPDATE", "kullanicilar", mevcut[3], onceki={"personel_kodu": mevcut[1]}, yeni={"personel_kodu": yeni_kod})
        conn.commit()
        return {"mesaj": "Personel başarıyla güncellendi.", "personel_id": personel_id, "personel_kodu": yeni_kod, "aktif_mi": mevcut[2]}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu personel kodu başka bir kayıtta kullanılıyor.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# RANDEVU & ODA MODÜLÜ
# ==========================================
def psikolog_odasina_atanmis_mi(cursor, psikolog_id: int, oda_id: int) -> bool:
    """Oda, seçilen psikoloğa (personel_id) atanmış mı? Yetki kuralı sunucuda da uygulanır."""
    cursor.execute(
        "SELECT 1 FROM psikolog_odalar po "
        "JOIN personel p ON p.kullanici_id = po.kullanici_id "
        "WHERE p.personel_id = %s AND po.oda_id = %s;",
        (psikolog_id, oda_id),
    )
    return cursor.fetchone() is not None

@app.get("/api/randevular/siradaki-kod")
def siradaki_danisan_kodunu_ver(kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        siradaki_kod = otomatik_danisan_kodu_uret(cursor, kilitle=False)     # önizleme: kilit ve sayaç tüketimi yok
        return {"siradaki_kod": siradaki_kod}
    except Exception:
        # Uydurma bir kod (DAN-yıl-0001) dönmek gerçek koda çarpabilir; kod alınamazsa açıkça hata verilir.
        raise HTTPException(status_code=503, detail="Sıradaki danışan kodu şu an alınamadı. Kod kayıt sırasında otomatik atanır.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

def randevu_deadlock_yeniden_dene(fonksiyon):
    """QA-001 #186: Randevu deadlock durumunda sinirli yeniden deneme."""
    from functools import wraps
    import time

    @wraps(fonksiyon)
    def sarmalayici(*args, **kwargs):
        maksimum_deneme = 3

        for deneme in range(maksimum_deneme):
            try:
                return fonksiyon(*args, **kwargs)

            except DeadlockDetected:
                if deneme == maksimum_deneme - 1:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Randevu işlemi eşzamanlı yoğunluk nedeniyle "
                            "tamamlanamadı. Lütfen tekrar deneyin."
                        )
                    )

                time.sleep(0.1 * (deneme + 1))

    return sarmalayici


@app.post("/api/randevular", status_code=201)
@randevu_deadlock_yeniden_dene
def randevu_olustur(randevu: RandevuOlusturModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    if randevu.baslangic_zamani >= randevu.bitis_zamani:
        raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")
    if hafta_sonuna_denk_mi(randevu.baslangic_zamani, randevu.bitis_zamani):
        raise HTTPException(status_code=422, detail=HAFTA_SONU_MESAJI)
    if gecmis_tarihe_mi(randevu.baslangic_zamani):
        raise HTTPException(status_code=422, detail=GECMIS_TARIH_MESAJI)

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. Psikolog yetki kontrolü
        # Rolü veritabanından çekiyoruz
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu.psikolog_id:
                raise HTTPException(status_code=403, detail="Yalnızca kendi adınıza randevu oluşturabilirsiniz.")

        # DİKKAT EDİN BURASI DEĞİŞTİ: Artık otomatik kod üretmiyoruz, frontend'den gelen kodu kontrol ediyoruz.
        cursor.execute("SELECT yas_grubu, olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = %s AND aktif_mi = TRUE FOR SHARE;", (randevu.danisan_kod_id,))
        danisan_kaydi = cursor.fetchone()
        if danisan_kaydi is None:
            raise HTTPException(status_code=422, detail="Seçilen danışan kodu bulunamadı veya aktif değil.")
        # Danışan başka bir psikoloğa aitse ona randevu verilemez (kodlar sıralı ve tahmin edilebilir olduğundan sunucuda da denetlenir)
        if not danisan_psikologa_ait_mi(danisan_kaydi[1] if len(danisan_kaydi) > 1 else None, randevu.psikolog_id):
            raise HTTPException(status_code=422, detail=DANISAN_PSIKOLOG_MESAJI)
        # Randevunun terapi türü danışanın yaş grubuna uymalıdır (yetişkin: bireysel terapi; çocuk: seçilmeli)
        try:
            terapi_turu = randevu_terapisini_belirle(danisan_kaydi[0], getattr(randevu, "terapi_turu", None))
        except ValueError as hata:
            raise HTTPException(status_code=422, detail=str(hata))

        # 2. Psikolog kontrolü
        cursor.execute(
            "SELECT 1 FROM personel p "
            "JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id "
            "JOIN roller r ON k.rol_id = r.rol_id "
            "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND r.rol_adi ILIKE 'Psikolog';", 
            (randevu.psikolog_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")

        # 3. Oda kontrolü
        cursor.execute("SELECT 1 FROM odalar WHERE oda_id = %s AND aktif_mi = TRUE;", (randevu.oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Oda bulunamadı veya aktif değil.")

        if not psikolog_odasina_atanmis_mi(cursor, randevu.psikolog_id, randevu.oda_id):
            raise HTTPException(status_code=422, detail="Seçilen oda bu psikoloğa atanmamış.")

        # Tüm oda kullanım türleriyle ortak transaction kontrolü.
        oda_kilidini_al(cursor, randevu.oda_id)
        cakisma = oda_cakismasi_bul(
            cursor,
            randevu.oda_id,
            randevu.baslangic_zamani,
            randevu.bitis_zamani,
        )
        if cakisma:
            raise HTTPException(
                status_code=409,
                detail=f"Oda bu saatlerde dolu (çakışan kayıt: {cakisma}).",
            )

        # 4. Çakışma kontrolü
        cursor.execute("SELECT 1 FROM randevular WHERE durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu.psikolog_id, randevu.oda_id, randevu.bitis_zamani, randevu.baslangic_zamani))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        # 5. Randevuyu kaydetme (ARTIK randevu.danisan_kod_id KULLANILIYOR)
        cursor.execute(
            "INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu) VALUES (%s, %s, %s, %s, %s, 'PLANLANDI', %s, %s) RETURNING randevu_id;", 
            (randevu.danisan_kod_id, randevu.psikolog_id, randevu.oda_id, randevu.baslangic_zamani, randevu.bitis_zamani, getattr(randevu, 'gorusme_tipi', 'YUZ_YUZE'), terapi_turu)
        )
        randevu_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "randevular", randevu_id))
        
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu oluşturuldu.", "randevu_id": randevu_id}
    except ExclusionViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Seçilen psikolog veya oda bu saatlerde dolu."
        )
    except DeadlockDetected:
        if conn is not None:
            conn.rollback()
        raise
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None:
            conn.rollback()
        # İç hata metni (SQL, tablo adı vb.) istemciye sızdırılmaz; ayrıntı yalnızca sunucu günlüğüne yazılır.
        logging.getLogger(__name__).exception("Randevu oluşturulurken beklenmeyen hata: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Randevu oluşturulurken bir hata oluştu. Lütfen daha sonra tekrar deneyin."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

RANDEVU_LISTE_SUTUNLARI = (
    "r.randevu_id, r.danisan_kod_id, r.psikolog_id, r.oda_id, r.baslangic_zamani, r.bitis_zamani, r.durum, "
    "r.olusturulma_tarihi, r.iptal_nedeni, r.iptal_notu, r.gorusme_tipi, r.terapi_turu"
)
RANDEVU_LISTE_ENCOK = 5000


@app.get("/api/randevular")
def randevulari_listele(
    baslangic: Optional[date] = None,
    bitis: Optional[date] = None,
    durum: Optional[str] = None,
    danisan_kod_id: Optional[str] = None,
    oda_id: Optional[int] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    response: Response = None,
    kullanici_id: int = Depends(izin_kontrol("TAKVIM_GORUNTULE")),
):
    """Randevu listesi. Süzgeçler isteğe bağlıdır; hiçbiri verilmezse eskisi gibi tüm kayıtlar döner.

    baslangic/bitis: başlangıç gününe göre (ikisi de dahil). limit verilirse en yeni randevular
    önce gelir ve toplam kayıt sayısı X-Toplam-Kayit başlığında bildirilir (liste kesilmişse
    istemci bunu kullanıcıya gösterebilsin diye).
    """
    if limit is not None:
        if limit < 1 or limit > RANDEVU_LISTE_ENCOK:
            raise HTTPException(status_code=422, detail=f"limit 1 ile {RANDEVU_LISTE_ENCOK} arasında olmalıdır.")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset negatif olamaz.")
    if baslangic is not None and bitis is not None and baslangic > bitis:
        raise HTTPException(status_code=422, detail="Başlangıç tarihi bitiş tarihinden sonra olamaz.")
    if durum is not None and durum not in ("PLANLANDI", "TAMAMLANDI", "GELMEDI", "IPTAL_EDILDI"):
        raise HTTPException(status_code=422, detail="Geçersiz randevu durumu.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Rol adını net bir şekilde string olarak almak için tablodaki sütun adını garantiye alıyoruz
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol_sonuc = cursor.fetchone()

        if not rol_sonuc:
            return []

        # Eğer rol_sonuc[0] sayı gelme ihtimaline karşı stringe çevirip .lower() yapıyoruz
        rol_adi = str(rol_sonuc[0]).lower() if rol_sonuc else ""

        # Serbest metin olan iptal notu yalnızca randevu düzenleme yetkisi olanlara gösterilir; diğerleri iptal NEDENİNİ (liste) görür.
        cursor.execute(
            "SELECT ri.izin_var FROM kullanicilar k JOIN rol_izinleri ri ON k.rol_id = ri.rol_id JOIN izinler i ON ri.izin_id = i.izin_id "
            "WHERE k.kullanici_id = %s AND i.izin_adi = 'RANDEVU_DUZENLE';",
            (kullanici_id,),
        )
        notu_gorebilir = (cursor.fetchone() or (0,))[0] == 1

        kosullar = []
        parametreler = []
        gelen = ""
        # Psikolog yalnızca kendi randevularını görür
        if psikolog_rolu_mu(rol_adi):
            gelen = "JOIN personel p ON p.personel_id = r.psikolog_id "
            kosullar.append("p.kullanici_id = %s")
            parametreler.append(kullanici_id)
        if baslangic is not None:
            kosullar.append("r.baslangic_zamani >= %s")
            parametreler.append(baslangic)
        if bitis is not None:
            kosullar.append("r.baslangic_zamani < %s::date + 1")
            parametreler.append(bitis)
        if durum is not None:
            kosullar.append("r.durum = %s")
            parametreler.append(durum)
        if danisan_kod_id is not None:
            kosullar.append("r.danisan_kod_id = %s")
            parametreler.append(danisan_kod_id)
        if oda_id is not None:
            kosullar.append("r.oda_id = %s")
            parametreler.append(oda_id)
        nerede = (" WHERE " + " AND ".join(kosullar)) if kosullar else ""

        # Hiçbir süzgeç ve limit verilmediyse (tüm geçmiş) liste en yeni RANDEVU_LISTE_ENCOK kayıtla sınırlanır: yıllar içinde tek istek onlarca MB
        # olup sunucuyu ve istemciyi kilitliyordu (10 yıllık veride 47 MB, 5 sn). Kesilmişse X-Toplam-Kayit başlığı gerçek toplamı bildirir; sıra eskisi gibi artandır.
        sinirsiz_istek = limit is None and not (baslangic or bitis or durum or danisan_kod_id or oda_id)
        if sinirsiz_istek:
            limit = RANDEVU_LISTE_ENCOK
        if limit is None:
            cursor.execute(
                f"SELECT {RANDEVU_LISTE_SUTUNLARI} FROM randevular r {gelen}{nerede} ORDER BY r.baslangic_zamani;",
                tuple(parametreler),
            )
        else:
            cursor.execute(f"SELECT COUNT(*) FROM randevular r {gelen}{nerede};", tuple(parametreler))
            toplam = (cursor.fetchone() or (0,))[0]
            if response is not None:
                response.headers["X-Toplam-Kayit"] = str(toplam)
            cursor.execute(
                f"SELECT {RANDEVU_LISTE_SUTUNLARI} FROM randevular r {gelen}{nerede} "
                "ORDER BY r.baslangic_zamani DESC, r.randevu_id DESC LIMIT %s OFFSET %s;",
                tuple(parametreler) + (limit, offset),
            )

        kayitlar = cursor.fetchall()
        if sinirsiz_istek:
            kayitlar = list(reversed(kayitlar))        # sınırlı sorgu en yeniden başlar; eski davranış gibi artan sırada döndür

        return [
            {
                "randevu_id": kayit[0],
                "danisan_kod_id": kayit[1],
                "psikolog_id": kayit[2],
                "oda_id": kayit[3],
                "baslangic_zamani": kayit[4],
                "bitis_zamani": kayit[5],
                "durum": kayit[6],
                "olusturma_tarihi": kayit[7] if len(kayit) > 7 else None,
                "iptal_nedeni": kayit[8] if len(kayit) > 8 else None,
                "iptal_notu": (kayit[9] if len(kayit) > 9 else None) if notu_gorebilir else None,
                "gorusme_tipi": kayit[10] if len(kayit) > 10 else "YUZ_YUZE",
                "terapi_turu": kayit[11] if len(kayit) > 11 else None
            } for kayit in kayitlar
        ]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# Danışanlar ekranı: danışan başına toplam randevu sayısı (tüm geçmişi indirmeden). Görünürlük /api/randevular ile aynıdır: psikolog yalnızca kendi randevularının sayısını görür.
@app.get("/api/danisan-randevu-sayilari")
def danisan_randevu_sayilari(kullanici_id: int = Depends(izin_kontrol("TAKVIM_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if not rol:
            return {}
        if psikolog_rolu_mu(str(rol[0]).lower()):
            cursor.execute(
                "SELECT r.danisan_kod_id, COUNT(*) FROM randevular r JOIN personel p ON p.personel_id = r.psikolog_id "
                "WHERE p.kullanici_id = %s GROUP BY r.danisan_kod_id;", (kullanici_id,))
        else:
            cursor.execute("SELECT r.danisan_kod_id, COUNT(*) FROM randevular r GROUP BY r.danisan_kod_id;")
        return {kod: int(sayi) for kod, sayi in cursor.fetchall()}
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Randevu sayıları alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


HAFTA_SONU_MESAJI = "Hafta sonu randevu verilemez. Lütfen hafta içi bir gün seçin."


def hafta_sonuna_denk_mi(*zamanlar) -> bool:
    """Verilen zamanlardan biri cumartesi ya da pazara denk geliyorsa True (kurum hafta sonu kapalıdır)."""
    return any(z.weekday() >= 5 for z in zamanlar)


GECMIS_TARIH_MESAJI = "Geçmiş bir tarihe randevu verilemez."


def gecmis_tarihe_mi(zaman) -> bool:
    """Başlangıç günü bugünden önceyse True. Bugünün geçmiş saatleri serbesttir (görüşme yapılıp sonradan girilebilir)."""
    return zaman.date() < datetime.now(zaman.tzinfo).date()


DANISAN_PSIKOLOG_MESAJI = "Seçilen danışan bu psikoloğa ait değil. Bir danışanın randevusu yalnızca kendi psikoloğuna verilebilir."


def danisan_psikologa_ait_mi(sahip_psikolog_id, psikolog_id) -> bool:
    """Danışanın kayıtlı psikoloğu varsa randevu o psikoloğa verilmelidir (eski kayıtlarda psikolog boş olabilir)."""
    return sahip_psikolog_id is None or sahip_psikolog_id == psikolog_id


def randevu_taraflarini_denetle(cursor, danisan_kod_id, psikolog_id):
    """Randevunun danışanı aktif mi, psikologu aktif bir psikolog mu ve danışan bu psikoloğa mı ait? Danışanın yaş grubunu döndürür."""
    cursor.execute("SELECT yas_grubu, olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = %s AND aktif_mi = TRUE FOR SHARE;", (danisan_kod_id,))
    danisan = cursor.fetchone()
    if danisan is None:
        raise HTTPException(status_code=422, detail="Seçilen danışan kodu bulunamadı veya aktif değil.")
    cursor.execute(
        "SELECT 1 FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id "
        "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';",
        (psikolog_id,),
    )
    if cursor.fetchone() is None:
        raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")
    if not danisan_psikologa_ait_mi(danisan[1] if len(danisan) > 1 else None, psikolog_id):
        raise HTTPException(status_code=422, detail=DANISAN_PSIKOLOG_MESAJI)
    return danisan[0]


@app.get("/api/randevular/doluluk")
def randevu_doluluk(
    tarih: date,
    oda_id: int | None = Query(None, gt=0),
    psikolog_id: int | None = Query(None, gt=0),
    haric_randevu_id: int | None = Query(None, gt=0),
    kullanici_id: int = Depends(izin_kontrol("TAKVIM_GORUNTULE")),
):
    """Seçilen gün için oda ve/veya psikologun dolu saat aralıklarını döndürür.

    Yalnızca zaman aralığı ve dolu olanın türü (oda / psikolog) döner; danışan kodu,
    psikolog adı gibi kimlik bilgisi içermez. Son karar yine randevu oluşturma ve
    güncelleme uçlarındadır (409 + veritabanı kısıtı).
    """
    if oda_id is None and psikolog_id is None:
        raise HTTPException(status_code=422, detail="oda_id veya psikolog_id gönderilmelidir.")

    gun_basi = datetime(tarih.year, tarih.month, tarih.day)
    gun_sonu = gun_basi + timedelta(days=1)

    sorgu = (
        "SELECT baslangic_zamani, bitis_zamani, oda_id = %s, psikolog_id = %s "
        "FROM randevular "
        "WHERE durum = 'PLANLANDI' AND (oda_id = %s OR psikolog_id = %s) "
        "AND baslangic_zamani < %s AND bitis_zamani > %s"
    )
    parametreler = [oda_id, psikolog_id, oda_id, psikolog_id, gun_sonu, gun_basi]
    if haric_randevu_id is not None:
        sorgu += " AND randevu_id <> %s"
        parametreler.append(haric_randevu_id)
    sorgu += " ORDER BY baslangic_zamani;"

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(sorgu, parametreler)
        kayitlar = cursor.fetchall()

        araliklar = []
        for baslangic, bitis, oda_dolu, psikolog_dolu in kayitlar:
            if oda_dolu and psikolog_dolu:
                sebep = "oda_ve_psikolog"
            elif oda_dolu:
                sebep = "oda"
            else:
                sebep = "psikolog"
            araliklar.append({
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
                "sebep": sebep,
            })
        return {"tarih": tarih.isoformat(), "dolu_araliklar": araliklar}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/randevular/{randevu_id}")
def randevu_guncelle(randevu_id: int, guncelleme: RandevuGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Satır kilidinden önce mevcut odayı belirle.
        cursor.execute(
            "SELECT oda_id FROM randevular WHERE randevu_id = %s;",
            (randevu_id,),
        )
        ilk_kayit = cursor.fetchone()

        if ilk_kayit is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        ilk_oda_id = ilk_kayit[0]
        istenen = guncelleme.model_dump(exclude_unset=True)

        # Boş/null güncellemeler oda kilidi alınmadan reddedilir.
        if not istenen or any(
            deger is None for deger in istenen.values()
        ):
            raise HTTPException(
                status_code=422,
                detail="Geçerli güncelleme alanları gönderilmelidir.",
            )

        hedef_oda_id = istenen.get("oda_id", ilk_oda_id)

        # Oda kilitleri her zaman sabit sırayla alınır.
        for kilit_oda_id in sorted({
            ilk_oda_id,
            hedef_oda_id,
        }):
            if kilit_oda_id is not None:
                oda_kilidini_al(cursor, kilit_oda_id)

        cursor.execute("SELECT danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum, gorusme_tipi, terapi_turu FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        mevcut = cursor.fetchone()

        if mevcut is not None and mevcut[2] != ilk_oda_id:
            raise HTTPException(
                status_code=409,
                detail="Randevunun odası başka bir işlemde değişti. "
                       "Listeyi yenileyip tekrar deneyiniz.",
            )
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")
        if mevcut[5] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Yalnızca planlanmış randevular güncellenebilir.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        psikolog_mu = rol is not None and psikolog_rolu_mu(rol[0])
        if psikolog_mu:
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != mevcut[1]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzu düzenleyebilirsiniz.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler or any(deger is None for deger in degisiklikler.values()):
            raise HTTPException(status_code=422, detail="Geçerli güncelleme alanları gönderilmelidir.")

        danisan_kod_id = degisiklikler.get("danisan_kod_id", mevcut[0])
        psikolog_id = degisiklikler.get("psikolog_id", mevcut[1])
        oda_id = degisiklikler.get("oda_id", mevcut[2])
        baslangic = degisiklikler.get("baslangic_zamani", mevcut[3])
        bitis = degisiklikler.get("bitis_zamani", mevcut[4])

        if psikolog_mu and psikolog_id != mevcut[1]:
            raise HTTPException(status_code=403, detail="Randevuyu başka psikoloğa devredemezsiniz.")
        if baslangic >= bitis:
            raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")

        # TKYS_RANDEVU_MESAI_0800_1800
        # Saat değiştiriliyorsa mevcut kayıtla birlikte doğrula.
        if (
            "baslangic_zamani" in degisiklikler
            or "bitis_zamani" in degisiklikler
        ):
            from server.modeller import randevu_mesai_dogrula

            try:
                randevu_mesai_dogrula(baslangic, bitis)
            except ValueError as hata:
                raise HTTPException(
                    status_code=422,
                    detail=str(hata),
                ) from hata
        # Zaman değişiyorsa hafta sonuna alınamaz (eskiden kalan hafta sonu randevusunun yalnızca oda/danışanı değişebilir)
        if ("baslangic_zamani" in degisiklikler or "bitis_zamani" in degisiklikler) and hafta_sonuna_denk_mi(baslangic, bitis):
            raise HTTPException(status_code=422, detail=HAFTA_SONU_MESAJI)
        # Başlangıç değişiyorsa geçmiş bir tarihe alınamaz (geçmiş randevunun terapi türü vb. yine düzeltilebilir).
        if "baslangic_zamani" in degisiklikler and baslangic != mevcut[3] and gecmis_tarihe_mi(baslangic):
            raise HTTPException(status_code=422, detail=GECMIS_TARIH_MESAJI)
        # Danışan ya da psikolog DEĞİŞİYORSA yeni taraf oluşturmadakiyle aynı kurallardan geçer: danışan aktif mi, psikolog aktif bir
        # psikolog mu, danışan bu psikoloğa mı ait. Değişmeyen taraf oluşturulurken doğrulanmıştı (planlı randevusu olan taraf pasife alınamaz).
        if danisan_kod_id != mevcut[0] or psikolog_id != mevcut[1]:
            randevu_taraflarini_denetle(cursor, danisan_kod_id, psikolog_id)
        if (psikolog_id != mevcut[1] or oda_id != mevcut[2]) and not psikolog_odasina_atanmis_mi(cursor, psikolog_id, oda_id):
            raise HTTPException(status_code=422, detail="Seçilen oda bu psikoloğa atanmamış.")

        # Oda kilitleri satır kilidinden önce alındı.
        cakisma = oda_cakismasi_bul(
            cursor,
            oda_id,
            baslangic,
            bitis,
            haric_randevu_id=randevu_id,
        )
        if cakisma:
            raise HTTPException(
                status_code=409,
                detail=f"Oda bu saatlerde dolu (çakışan kayıt: {cakisma}).",
            )

        cursor.execute("SELECT 1 FROM randevular WHERE randevu_id != %s AND durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu_id, psikolog_id, oda_id, bitis, baslangic))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        # Görüşme tipi / terapi türü değişiyorsa: terapi, danışanın yaş grubuna uymalıdır
        yeni_gorusme = yeni_terapi = None
        siniflar_degisiyor = "gorusme_tipi" in degisiklikler or "terapi_turu" in degisiklikler
        if siniflar_degisiyor:
            yeni_gorusme = degisiklikler.get("gorusme_tipi", mevcut[6] if len(mevcut) > 6 else "YUZ_YUZE")
            yeni_terapi = degisiklikler.get("terapi_turu", mevcut[7] if len(mevcut) > 7 else None)
            if "terapi_turu" in degisiklikler:
                cursor.execute("SELECT yas_grubu FROM danisan_kodlari WHERE danisan_kod_id = %s;", (danisan_kod_id,))
                yas_kaydi = cursor.fetchone()
                try:
                    yeni_terapi = randevu_terapisini_belirle(yas_kaydi[0] if yas_kaydi else None, yeni_terapi)
                except ValueError as hata:
                    raise HTTPException(status_code=422, detail=str(hata))

        cursor.execute("UPDATE randevular SET danisan_kod_id = %s, psikolog_id = %s, oda_id = %s, baslangic_zamani = %s, bitis_zamani = %s WHERE randevu_id = %s;", (danisan_kod_id, psikolog_id, oda_id, baslangic, bitis, randevu_id))
        if siniflar_degisiyor:
            cursor.execute("UPDATE randevular SET gorusme_tipi = %s, terapi_turu = %s WHERE randevu_id = %s;", (yeni_gorusme, yeni_terapi, randevu_id))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "UPDATE", "randevular", randevu_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu güncellendi.", "randevu_id": randevu_id}
    except ExclusionViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/randevular/{randevu_id}/iptal")
def randevu_iptal_et(randevu_id: int, iptal: RandevuIptalModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_IPTAL"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT psikolog_id, durum FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        randevu = cursor.fetchone()
        if randevu is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzu iptal edebilirsiniz.")

        if randevu[1] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Bu randevu iptal edilemez.")

        cursor.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI', iptal_nedeni = %s, iptal_notu = %s WHERE randevu_id = %s;", (iptal.iptal_nedeni, iptal.iptal_notu, randevu_id))
        durum_degisikligi_yaz(cursor, kullanici_id, "CANCEL", "randevular", randevu_id, onceki=randevu[1], yeni="IPTAL_EDILDI", iptal_nedeni=iptal.iptal_nedeni)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu iptal edildi.", "randevu_id": randevu_id}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/randevular/{randevu_id}/durum")
def randevu_durumunu_isaretle(
    randevu_id: int,
    isaret: RandevuDurumModeli,
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_DUZENLE")),
):
    """Başlangıcı geçmiş randevuyu Tamamlandı ya da Gelmedi olarak işaretler (ikisi arasında düzeltme yapılabilir).

    Psikolog yalnızca kendi randevusunu işaretler. İptal edilmiş ve henüz başlamamış randevu işaretlenemez.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT psikolog_id, durum, baslangic_zamani FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        randevu = cursor.fetchone()
        if randevu is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzun durumunu işaretleyebilirsiniz.")

        if randevu[1] == "IPTAL_EDILDI":
            raise HTTPException(status_code=409, detail="İptal edilmiş randevu Tamamlandı ya da Gelmedi olarak işaretlenemez.")
        if randevu[2] > datetime.now():
            raise HTTPException(status_code=409, detail="Henüz başlamamış randevu işaretlenemez. Randevu saatinden sonra tekrar deneyin.")
        if randevu[1] == isaret.durum:
            return {"durum": "basarili", "randevu_id": randevu_id, "randevu_durumu": isaret.durum, "mesaj": "Randevu zaten bu durumda."}

        cursor.execute("UPDATE randevular SET durum = %s WHERE randevu_id = %s;", (isaret.durum, randevu_id))
        durum_degisikligi_yaz(cursor, kullanici_id, "UPDATE", "randevular", randevu_id, onceki=randevu[1], yeni=isaret.durum)
        conn.commit()
        return {"durum": "basarili", "randevu_id": randevu_id, "randevu_durumu": isaret.durum, "mesaj": "Randevu durumu güncellendi."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# istisna_turu yalnızca bu üç değerden biri olabilir; serbest metin (ad, tanı vb.) kişisel veri sızıntısına yol açar.
IZINLI_ISTISNA_TURLERI = ("YOK", "KANSER", "SEHIT_GAZI")


@app.post("/api/danisan-kodlari", status_code=201)
def danisan_kodu_olustur(
    ucretli_mi: bool = True,
    istisna_turu: str = "YOK",
    psikolog_id: int | None = Query(None, gt=0),
    yas_grubu: str = Query(...),
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR")),
):
    """Yeni danışan kodu üretir.

    Psikolog hesabında danışan kendi adına açılır (psikolog_id yok sayılır). Diğer roller (admin, danışma vb.)
    danışanın hangi psikologa ait olduğunu psikolog_id ile belirtmek zorundadır; böylece danışan sahipsiz kalmaz.
    """
    # Doğrulama veritabanına bağlanmadan önce yapılır; gelen metin hata mesajına da yazılmaz.
    if istisna_turu not in IZINLI_ISTISNA_TURLERI:
        raise HTTPException(status_code=422, detail="Geçersiz istisna türü. İzinli değerler: " + ", ".join(IZINLI_ISTISNA_TURLERI) + ".")
    if ucretli_mi and istisna_turu != "YOK":
        raise HTTPException(status_code=422, detail="Ücretli danışan için istisna türü YOK olmalıdır.")
    if not ucretli_mi and istisna_turu == "YOK":
        raise HTTPException(status_code=422, detail="Ücretsiz danışan için istisna türü (Kanser / Şehit-Gazi) seçilmelidir.")
    # Kapalı listeler: gelen metin doğrulanır ve hata mesajına yazılmaz (FR-008)
    if yas_grubu not in YAS_GRUPLARI:
        raise HTTPException(status_code=422, detail="Geçersiz yaş grubu. İzinli değerler: " + ", ".join(YAS_GRUPLARI) + ".")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. İşlemi yapanın rolünü ve (varsa) aktif personel kaydını öğreniyoruz
        cursor.execute(
            "SELECT p.personel_id, UPPER(r.rol_adi) FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id "
            "LEFT JOIN personel p ON p.kullanici_id = k.kullanici_id AND p.aktif_mi = TRUE "
            "WHERE k.kullanici_id = %s;",
            (kullanici_id,),
        )
        kimlik = cursor.fetchone()
        personel_id, rol_adi = (kimlik[0], kimlik[1]) if kimlik else (None, "")

        if psikolog_rolu_mu(rol_adi):
            # Psikolog danışanı yalnızca kendi adına açabilir
            if personel_id is None:
                raise HTTPException(status_code=403, detail="Personel/Psikolog kaydınız bulunamadığı için danışan kodu oluşturamazsınız.")
            olusturan_psikolog_id = personel_id
        else:
            # Diğer roller danışanı hangi psikologa açtığını belirtmelidir
            if psikolog_id is None:
                raise HTTPException(status_code=422, detail="Danışan için bir psikolog seçilmelidir.")
            cursor.execute(
                "SELECT p.personel_id FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id "
                "JOIN roller r ON k.rol_id = r.rol_id "
                "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';",
                (psikolog_id,),
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=422, detail="Seçilen psikolog bulunamadı.")
            olusturan_psikolog_id = psikolog_id

        # 2. Otomatik danışan kodunu üret
        yeni_kod = otomatik_danisan_kodu_uret(cursor)

        # 3. Veritabanına oluşturan psikoloğun ID'siyle birlikte kaydediyoruz
        cursor.execute(
            """
            INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi, olusturan_psikolog_id, yas_grubu) 
            VALUES (%s, %s, %s, TRUE, %s, %s) 
            RETURNING danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi, olusturulma_tarihi, olusturan_psikolog_id, yas_grubu;
            """, 
            (yeni_kod, ucretli_mi, istisna_turu, olusturan_psikolog_id, yas_grubu)
        )
        kayit = cursor.fetchone()

        # 4. Denetim (Audit) kaydı oluştur
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo) VALUES (%s, %s, %s);", (kullanici_id, "CREATE", "danisan_kodlari"))
        conn.commit()

        return {
            "durum": "basarili", 
            "veri": {
                "danisan_kod_id": kayit[0],
                "ucretli_mi": kayit[1],
                "istisna_turu": kayit[2],
                "aktif_mi": kayit[3],
                "olusturulma_tarihi": kayit[4],
                "olusturan_psikolog_id": kayit[5],
                "yas_grubu": kayit[6] if len(kayit) > 6 else yas_grubu
            }
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

def izin_kontrol_tumu(*izin_adlari: str):
    """Listedeki izinlerin HEPSİNE sahip olmayı ister.

    Menüdeki "birden fazla kod varsa hepsi gerekir" kuralıyla aynıdır; sunucu, ekranı gören herkese
    izin verir (örn. Oda Yönetimi ekranı ODA_EKLE ve ODA_DUZENLE ister).
    """
    gerekli = sorted(set(izin_adlari))

    def kontrol(kullanici_id: int = Depends(mevcut_kullanici_id)):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(DISTINCT i.izin_adi) FROM kullanicilar k
                JOIN rol_izinleri ri ON k.rol_id = ri.rol_id
                JOIN izinler i ON ri.izin_id = i.izin_id
                WHERE k.kullanici_id = %s AND i.izin_adi = ANY(%s) AND ri.izin_var = 1;
                """, (kullanici_id, gerekli)
            )
            sonuc = cursor.fetchone()
            if sonuc is None or sonuc[0] != len(gerekli):
                raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz bulunmuyor.")
            return kullanici_id
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()
    return kontrol


from pydantic import BaseModel as _OdaYetkiBaseModel, Field as _OdaYetkiField


class OdaYetkileriModeli(_OdaYetkiBaseModel):
    oda_idleri: list[int] = _OdaYetkiField(min_length=1)


# "Planlı randevu" her yerde aynı anlama gelir: durumu PLANLANDI ve başlangıç günü bugün ya da sonrası. Bugünün geçmiş saatindeki
# ama sonucu girilmemiş randevu da sayılır; böylece unutulan "Tamamlandı / Gelmedi" işareti pasife almayı engelleyerek fark ettirilir.
PLANLI_RANDEVU_COZUMU = "bugünkü randevuların sonucunu (Tamamlandı / Gelmedi) girin, sonraki günlerin randevularını iptal edin."


def psikolog_planli_randevulari_denetle(cursor, kullanici_id, kalacak_oda_idleri=None):
    """Psikologun bugün ve sonrası için planlı (PLANLANDI) randevusu varken odası boşalacak bir işlem yapılamaz (409).

    kalacak_oda_idleri verilmezse (rol değiştirme: tüm odalar kalkar) tüm planlı randevular sayılır. Verilirse (oda yetkisi
    güncelleme) yalnızca psikologa şu an atanmış, yeni kümede olmayan ve aktif odalardaki planlı randevular sayılır.
    Tarihi geçmiş "Planlandı" kayıtlar ve iptal edilmiş randevular engellemez."""
    if kalacak_oda_idleri is None:
        cursor.execute(
            """
            SELECT o.oda_adi, COUNT(*)
            FROM randevular r
            JOIN personel p ON p.personel_id = r.psikolog_id
            JOIN odalar o ON o.oda_id = r.oda_id
            WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani >= CURRENT_DATE
            GROUP BY o.oda_id, o.oda_adi
            ORDER BY o.oda_adi;
            """,
            (kullanici_id,),
        )
    else:
        cursor.execute(
            """
            SELECT o.oda_adi, COUNT(*)
            FROM randevular r
            JOIN personel p ON p.personel_id = r.psikolog_id
            JOIN odalar o ON o.oda_id = r.oda_id
            WHERE p.kullanici_id = %s AND r.durum = 'PLANLANDI' AND r.baslangic_zamani >= CURRENT_DATE
              AND o.aktif_mi = TRUE AND r.oda_id <> ALL(%s)
              AND EXISTS (SELECT 1 FROM psikolog_odalar po WHERE po.kullanici_id = p.kullanici_id AND po.oda_id = r.oda_id)
            GROUP BY o.oda_id, o.oda_adi
            ORDER BY o.oda_adi;
            """,
            (kullanici_id, list(kalacak_oda_idleri)),
        )
    planlilar = cursor.fetchall()
    if not planlilar:
        return
    if kalacak_oda_idleri is None:
        toplam = sum(sayi for _, sayi in planlilar)
        detay = f"Bu psikologun bugün ve sonrası için {toplam} planlı randevusu var. Rolü değiştirmeden önce {PLANLI_RANDEVU_COZUMU}"
    else:
        ayrinti = ", ".join(f"{ad} ({sayi} randevu)" for ad, sayi in planlilar)
        detay = f"Kaldırılmak istenen odalarda bugün ve sonrası için planlı randevu var: {ayrinti}. Odayı kaldırmadan önce {PLANLI_RANDEVU_COZUMU}"
    raise HTTPException(status_code=409, detail=detay)


def etkinlik_oda_atama_kilitlerini_al(cursor, oda_idleri):
    """Oda etkinliği API'siyle aynı transaction kilitlerini kullan."""
    for oda_id in sorted(set(oda_idleri)):
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            (391284, oda_id),
        )


def oda_etkinlikli_odalari_denetle(
    cursor, oda_idleri, haric_kullanici_id=None
):
    """Süren veya gelecekteki etkinliği olan odaları psikolog atamasına kapat."""
    if not oda_idleri:
        return

    cursor.execute(
        """
        SELECT o.oda_adi, COUNT(DISTINCT e.etkinlik_id)
        FROM oda_etkinlikleri e
        JOIN oda_etkinlik_gunleri g
          ON g.etkinlik_id = e.etkinlik_id
        JOIN odalar o
          ON o.oda_id = e.oda_id
        WHERE e.oda_id = ANY(%s)
          AND COALESCE(e.iptal_edildi_mi, FALSE) = FALSE
          AND g.bitis_zamani > NOW()
          AND NOT EXISTS (
              SELECT 1
              FROM psikolog_odalar po
              WHERE po.oda_id = e.oda_id
                AND po.kullanici_id = %s
          )
        GROUP BY o.oda_id, o.oda_adi
        ORDER BY o.oda_adi
        """,
        (list(oda_idleri), haric_kullanici_id),
    )

    etkinlikli_odalar = cursor.fetchall()

    if etkinlikli_odalar:
        ayrinti = ", ".join(
            f"{ad} ({sayi} etkinlik)"
            for ad, sayi in etkinlikli_odalar
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Devam eden veya gelecekte planlanmış oda etkinliği "
                f"bulunan oda psikoloğa atanamaz: {ayrinti}. "
                "Önce ilgili etkinlikleri iptal edin veya "
                "başka bir oda seçin."
            ),
        )


def cihaz_rezervasyonlu_odalari_denetle(cursor, oda_idleri, haric_kullanici_id=None):
    """Cihaz rezervasyonu için kullanılan oda psikologa atanamaz (409).

    "Kullanılan" = iptal edilmemiş ve henüz bitmemiş (süren ya da gelecekteki) cihaz rezervasyonu olan oda. Geçmişte kalmış
    rezervasyonlar engellemez; kullanıcı gelecek rezervasyonları iptal ederek odayı serbest bırakabilir. haric_kullanici_id
    verilirse o psikologa zaten atanmış odalar denetlenmez (oda yetkisi güncellenirken mevcut atamalar korunur)."""
    if not oda_idleri:
        return
    cursor.execute(
        """
        SELECT o.oda_adi, COUNT(*)
        FROM cihaz_rezervasyonlari cr
        JOIN odalar o ON o.oda_id = cr.kullanilacak_oda_id
        WHERE cr.kullanilacak_oda_id = ANY(%s)
          AND COALESCE(cr.iptal_edildi_mi, FALSE) = FALSE
          AND cr.bitis_zamani > NOW()
          AND NOT EXISTS (SELECT 1 FROM psikolog_odalar po WHERE po.oda_id = cr.kullanilacak_oda_id AND po.kullanici_id = %s)
        GROUP BY o.oda_id, o.oda_adi
        ORDER BY o.oda_adi;
        """,
        (list(oda_idleri), haric_kullanici_id),
    )
    kullanilanlar = cursor.fetchall()
    if kullanilanlar:
        ayrinti = ", ".join(f"{ad} ({sayi} rezervasyon)" for ad, sayi in kullanilanlar)
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cihaz rezervasyonu için kullanılan oda psikologa atanamaz: {ayrinti}. "
                "Odayı psikologa atamak için önce bu odadaki süren ve gelecekteki cihaz rezervasyonlarını iptal edin."
            ),
        )


def _hedef_psikolog_kontrol(cursor, hedef_kullanici_id: int, kilitle: bool = False):
    """Hedef kullanıcı var mı ve psikolog mu? Değilse uygun hatayı fırlatır."""
    cursor.execute(
        "SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON r.rol_id = k.rol_id "
        "WHERE k.kullanici_id = %s" + (" FOR UPDATE OF k;" if kilitle else ";"),
        (hedef_kullanici_id,),
    )
    kayit = cursor.fetchone()
    if kayit is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    if not psikolog_rolu_mu(kayit[0]):
        raise HTTPException(status_code=422, detail="Oda yetkisi yalnızca psikolog rolündeki kullanıcılar için tanımlanabilir.")


@app.get("/api/kullanicilar/{hedef_kullanici_id}/odalar")
def psikolog_oda_yetkilerini_getir(hedef_kullanici_id: int, kullanici_id: int = Depends(izin_kontrol("ROL_ATAMA_DEGISTIRME"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        _hedef_psikolog_kontrol(cursor, hedef_kullanici_id)
        cursor.execute("SELECT oda_id FROM psikolog_odalar WHERE kullanici_id = %s ORDER BY oda_id;", (hedef_kullanici_id,))
        return {"kullanici_id": hedef_kullanici_id, "oda_idleri": [k[0] for k in cursor.fetchall()]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.put("/api/kullanicilar/{hedef_kullanici_id}/odalar")
def psikolog_oda_yetkilerini_guncelle(
    hedef_kullanici_id: int,
    yetki: OdaYetkileriModeli,
    kullanici_id: int = Depends(izin_kontrol("ROL_ATAMA_DEGISTIRME")),
):
    """Psikologun görüşme odalarını verilen kümeye eşitler. Her psikologun en az bir (aktif) odası olmalıdır."""
    oda_idleri = sorted(set(yetki.oda_idleri))

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # KİLİT SIRASI (deadlock önleme): önce oda kilitleri, sonra kullanıcı satırı. Rezervasyon/randevu yolları oda kilidini alıp sonra
        # denetim kaydıyla kullanıcı satırını (FK) okur; burada tersi sıra (önce satır, sonra oda kilidi) karşılıklı beklemeye yol açıyordu.
        etkinlik_oda_atama_kilitlerini_al(cursor, oda_idleri)
        _hedef_psikolog_kontrol(cursor, hedef_kullanici_id, kilitle=True)

        cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = ANY(%s) AND aktif_mi = TRUE;", (oda_idleri,))
        if {k[0] for k in cursor.fetchall()} != set(oda_idleri):
            raise HTTPException(status_code=422, detail="Seçilen odalardan biri bulunamadı veya aktif değil.")
        cihaz_rezervasyonlu_odalari_denetle(cursor, oda_idleri, haric_kullanici_id=hedef_kullanici_id)
        oda_etkinlikli_odalari_denetle(cursor, oda_idleri, haric_kullanici_id=hedef_kullanici_id)
        psikolog_planli_randevulari_denetle(cursor, hedef_kullanici_id, kalacak_oda_idleri=oda_idleri)

        # Pasif odalardaki atamalara dokunma (oda yeniden aktif olunca yetki geri gelir).
        onceki_odalar = psikolog_odalarini_oku(cursor, hedef_kullanici_id)
        cursor.execute(
            """
            DELETE FROM psikolog_odalar po USING odalar o
            WHERE po.oda_id = o.oda_id AND o.aktif_mi = TRUE
              AND po.kullanici_id = %s AND po.oda_id <> ALL(%s);
            """,
            (hedef_kullanici_id, oda_idleri),
        )
        for oda_id in oda_idleri:
            cursor.execute(
                "INSERT INTO psikolog_odalar (kullanici_id, oda_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                (hedef_kullanici_id, oda_id),
            )
        psikolog_oda_degisikligini_yaz(cursor, kullanici_id, hedef_kullanici_id, onceki_odalar)
        conn.commit()
        return {"durum": "basarili", "kullanici_id": hedef_kullanici_id, "oda_idleri": oda_idleri}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except DeadlockDetected:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=503, detail="Oda ataması eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def oda_planli_kayit_sayilari(cursor, oda_id=None):
    """Odayı pasife almayı engelleyen kayıtların sayıları: {oda_id: {"planli_randevu", "cihaz_rezervasyonu", "etkinlik"}}.

    Tanımlar tek yerde durur (pasife alma kuralı ile Oda Yönetimi listesi aynı sayıyı görür):
    - randevu: durum PLANLANDI ve başlangıç bugün ya da sonrası,
    - cihaz rezervasyonu: iptal edilmemiş ve henüz bitmemiş (süren ya da gelecekteki) rezervasyonda kullanılacak oda,
    - etkinlik: iptal edilmemiş ve en az bir günü henüz bitmemiş oda etkinliği.
    Kaydı olmayan oda sonuçta yer almaz. oda_id verilirse yalnız o oda sorgulanır."""
    filtre = " AND oda_id = %(oda)s" if oda_id is not None else ""
    parametre = {"oda": oda_id}
    sonuc = {}

    def isle(anahtar, satirlar):
        for satir_oda_id, sayi in satirlar:
            sonuc.setdefault(satir_oda_id, {"planli_randevu": 0, "cihaz_rezervasyonu": 0, "etkinlik": 0})[anahtar] = sayi

    cursor.execute(
        "SELECT oda_id, COUNT(*) FROM randevular WHERE durum = 'PLANLANDI' AND baslangic_zamani >= CURRENT_DATE"
        + filtre + " GROUP BY oda_id;", parametre)
    isle("planli_randevu", cursor.fetchall())
    cursor.execute(
        "SELECT kullanilacak_oda_id AS oda_id, COUNT(*) FROM cihaz_rezervasyonlari "
        "WHERE COALESCE(iptal_edildi_mi, FALSE) = FALSE AND bitis_zamani > NOW() AND kullanilacak_oda_id IS NOT NULL"
        + filtre.replace("oda_id", "kullanilacak_oda_id") + " GROUP BY kullanilacak_oda_id;", parametre)
    isle("cihaz_rezervasyonu", cursor.fetchall())
    cursor.execute(
        "SELECT e.oda_id, COUNT(DISTINCT e.etkinlik_id) FROM oda_etkinlikleri e "
        "JOIN oda_etkinlik_gunleri g ON g.etkinlik_id = e.etkinlik_id "
        "WHERE COALESCE(e.iptal_edildi_mi, FALSE) = FALSE AND g.bitis_zamani > NOW()"
        + filtre.replace("oda_id", "e.oda_id") + " GROUP BY e.oda_id;", parametre)
    isle("etkinlik", cursor.fetchall())
    return sonuc


@app.get("/api/oda-planli-randevu-sayilari")
def oda_planli_randevu_sayilari(kullanici_id: int = Depends(izin_kontrol_tumu("ODA_EKLE", "ODA_DUZENLE"))):
    """Oda Yönetimi ekranındaki "Planlı kayıt" sütunu için: odayı pasife almayı engelleyen kayıtların oda başına sayıları.

    Sayımlar pasife alma kuralıyla aynı yardımcıyı kullanır; kullanıcı pasife almayı denemeden önce engeli görür.
    Kaydı olmayan odalar listede yoktur."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        sayilar = oda_planli_kayit_sayilari(cursor)
        return [{"oda_id": oda, **sayilar[oda]} for oda in sorted(sayilar)]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.get("/api/oda-psikolog-atamalari")
def oda_psikolog_atamalari(kullanici_id: int = Depends(izin_kontrol_tumu("ODA_EKLE", "ODA_DUZENLE"))):
    """Oda Yönetimi ekranındaki "Psikologlar" sütunu için (bilgi amaçlı). Ekranı görenler görebilir."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT po.oda_id, k.kullanici_adi
            FROM psikolog_odalar po
            JOIN kullanicilar k ON k.kullanici_id = po.kullanici_id
            JOIN roller r ON r.rol_id = k.rol_id
            WHERE k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG'
            ORDER BY po.oda_id, k.kullanici_adi;
            """
        )
        atamalar = {}
        for oda_id, kullanici_adi in cursor.fetchall():
            atamalar.setdefault(oda_id, []).append(kullanici_adi)
        return [{"oda_id": oda_id, "psikologlar": adlar} for oda_id, adlar in atamalar.items()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.post("/api/odalar", status_code=201)
def oda_olustur(oda: OdaOlusturModeli, kullanici_id: int = Depends(izin_kontrol("ODA_EKLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        oda_adi = oda.oda_adi.strip()
        cursor.execute("INSERT INTO odalar (oda_adi, kapasite, aktif_mi) VALUES (%s, %s, %s) RETURNING oda_id;", (oda_adi, oda.kapasite, oda.aktif_mi))
        oda_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "odalar", oda_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Oda başarıyla oluşturuldu.", "oda_id": oda_id}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu isimde bir oda zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/psikologlar/{personel_id}/odalar")
def psikolog_odalarini_getir(
    personel_id: int,
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR")) 
):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        
        # personel tablosunu araya koyarak personel_id üzerinden 
        # doğru kullanici_id'ye ulaşıyor ve sadece ona ait odaları çekiyoruz.
        sorgu = """
            SELECT o.oda_id, o.oda_adi, o.aktif_mi
            FROM odalar o
            JOIN psikolog_odalar po ON o.oda_id = po.oda_id
            JOIN personel p ON p.kullanici_id = po.kullanici_id
            WHERE p.personel_id = %s AND o.aktif_mi = TRUE;
        """
        cursor.execute(sorgu, (personel_id,))
        odalar = cursor.fetchall()
        
        return [{"oda_id": oda[0], "oda_adi": oda[1], "aktif_mi": oda[2]} for oda in odalar]
    except Exception:
        raise HTTPException(status_code=500, detail="Psikoloğun odaları alınırken bir hata oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()
        
@app.get("/api/odalar")
def odalari_listele(kullanici_id: int = Depends(izin_kontrol("ODA_DURUMU_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar ORDER BY oda_id;")
        odalar = cursor.fetchall()
        return [{"oda_id": oda[0], "oda_adi": oda[1], "kapasite": oda[2], "aktif_mi": oda[3]} for oda in odalar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()



@app.get("/api/cihaz-odalari")
def cihaz_odalarini_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    """Cihaz rezervasyonunda seçilebilen odalar: aktif bir psikologa atanmamış aktif odalar.

    Psikologlara atanan görüşme odaları listeye girmez."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(CIHAZ_ODALARI_SORGUSU + ";")
        return [{"oda_id": k[0], "oda_adi": k[1], "aktif_mi": True} for k in cursor.fetchall()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/odalar/{oda_id}")
def oda_detay(oda_id: int, kullanici_id: int = Depends(izin_kontrol("ODA_DURUMU_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar WHERE oda_id = %s;", (oda_id,))
        oda = cursor.fetchone()
        if oda is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")
        return {"oda_id": oda[0], "oda_adi": oda[1], "kapasite": oda[2], "aktif_mi": oda[3]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/odalar/{oda_id}")
def oda_guncelle(oda_id: int, oda: OdaGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("ODA_DUZENLE"))):
    degisiklikler = oda.model_dump(exclude_unset=True)
    if not degisiklikler or any(deger is None for deger in degisiklikler.values()):
        raise HTTPException(status_code=422, detail="Güncellenecek geçerli bir alan gönderilmelidir.")

    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = %s FOR UPDATE;", (oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")

        if degisiklikler.get("aktif_mi") is False:
            # Her psikologun en az bir aktif odası olmalı: tek aktif odası bu oda olan psikolog varsa pasife alınamaz.
            cursor.execute(
                """
                SELECT k.kullanici_adi
                FROM psikolog_odalar po
                JOIN kullanicilar k ON k.kullanici_id = po.kullanici_id
                JOIN personel p ON p.kullanici_id = k.kullanici_id
                WHERE po.oda_id = %s AND k.aktif_mi = TRUE AND p.aktif_mi = TRUE
                  AND EXISTS (SELECT 1 FROM odalar o0 WHERE o0.oda_id = po.oda_id AND o0.aktif_mi = TRUE)
                  AND NOT EXISTS (
                      SELECT 1 FROM psikolog_odalar po2
                      JOIN odalar o2 ON o2.oda_id = po2.oda_id
                      WHERE po2.kullanici_id = po.kullanici_id
                        AND po2.oda_id <> po.oda_id AND o2.aktif_mi = TRUE
                  )
                ORDER BY k.kullanici_adi;
                """,
                (oda_id,),
            )
            etkilenenler = [k[0] for k in cursor.fetchall()]
            if etkilenenler:
                raise HTTPException(
                    status_code=409,
                    detail="Bu oda şu psikologların tek aktif odası: " + ", ".join(etkilenenler)
                           + ". Önce onlara başka bir oda atayın.",
                )

            # Odada bugün ve sonrası için planlı randevu varsa pasife alınamaz (randevu sahibi psikolog odasız kalır).
            cursor.execute(
                "SELECT COUNT(*) FROM randevular WHERE oda_id = %s AND durum = 'PLANLANDI' AND baslangic_zamani >= CURRENT_DATE;",
                (oda_id,),
            )
            planli = cursor.fetchone()[0]
            if planli:
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu odada bugün ve sonrası için {planli} planlı randevu var. Odayı pasife almadan önce {PLANLI_RANDEVU_COZUMU}",
                )

            # Gelecekteki cihaz rezervasyonu ya da oda etkinliği olan oda da pasife alınamaz.
            kayit = oda_planli_kayit_sayilari(cursor, oda_id).get(oda_id, {})
            if kayit.get("cihaz_rezervasyonu"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu odada henüz bitmemiş {kayit['cihaz_rezervasyonu']} cihaz rezervasyonu var. "
                           "Odayı pasife almadan önce bu rezervasyonları iptal edin.",
                )
            if kayit.get("etkinlik"):
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu odada henüz bitmemiş {kayit['etkinlik']} etkinlik var. "
                           "Odayı pasife almadan önce bu etkinlikleri iptal edin.",
                )

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE odalar SET {alanlar} WHERE oda_id = %s RETURNING oda_id, oda_adi, kapasite, aktif_mi;", (*degerler, oda_id))
        sonuc = cursor.fetchone()

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "UPDATE", "odalar", oda_id))
        conn.commit()

        return {"durum": "basarili", "mesaj": "Oda başarıyla güncellendi.", "oda": {"oda_id": sonuc[0], "oda_adi": sonuc[1], "kapasite": sonuc[2], "aktif_mi": sonuc[3]}}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu isimde başka bir oda zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/danisan-kodlari")
def danisan_kodlari_listele(
    psikolog_id: int | None = Query(None, gt=0),
    pasifler_dahil: bool = Query(False),
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR")),
):
    """Aktif danışan kodlarını (kişisel veri içermez) döndürür; pasifler_dahil=true ise pasifleri de ekler.

    Psikolog yalnızca kendi oluşturduğu danışanları görür (psikolog_id parametresi yok sayılır). Diğer roller
    tüm danışanları görür; psikolog_id verilirse yalnızca o psikologun (personel_id) oluşturduğu danışanlar döner.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. Kullanıcının rolünü öğreniyoruz
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol_kayit = cursor.fetchone()
        rol_adi = rol_kayit[0].upper() if rol_kayit else ""

        sutunlar = "danisan_kod_id, ucretli_mi, aktif_mi, istisna_turu, olusturulma_tarihi, olusturan_psikolog_id, yas_grubu"
        aktif_kosulu = "TRUE" if pasifler_dahil else "aktif_mi = TRUE"

        # 2. Psikolog yalnızca kendi oluşturduğu danışan kodlarını görür
        if psikolog_rolu_mu(rol_adi):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            pers = cursor.fetchone()
            if not pers:
                raise HTTPException(status_code=403, detail="Personel kaydınız bulunamadı.")
            cursor.execute(
                f"SELECT {sutunlar} FROM danisan_kodlari "
                f"WHERE {aktif_kosulu} AND olusturan_psikolog_id = %s ORDER BY olusturulma_tarihi DESC;",
                (pers[0],),
            )
        elif psikolog_id is not None:
            # 3. Üst roller seçilen psikologun danışanlarını görür
            cursor.execute(
                f"SELECT {sutunlar} FROM danisan_kodlari "
                f"WHERE {aktif_kosulu} AND olusturan_psikolog_id = %s ORDER BY olusturulma_tarihi DESC;",
                (psikolog_id,),
            )
        else:
            # 4. Üst roller psikolog seçmediyse tüm aktif danışan kodlarını görür
            cursor.execute(
                f"SELECT {sutunlar} FROM danisan_kodlari "
                f"WHERE {aktif_kosulu} ORDER BY olusturulma_tarihi DESC;"
            )

        return [
            {
                "danisan_kod_id": k[0],
                "ucretli_mi": k[1],
                "aktif_mi": k[2],
                "istisna_turu": k[3],
                "olusturulma_tarihi": k[4].isoformat() if hasattr(k[4], "isoformat") else k[4],
                "olusturan_psikolog_id": k[5],
                "yas_grubu": k[6] if len(k) > 6 else None,
            }
            for k in cursor.fetchall()
        ]

    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/danisan-kodlari/{danisan_kod_id}/durum")
def danisan_durumunu_degistir(
    danisan_kod_id: str,
    aktif_mi: bool,
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR")),
):
    """Danışanı pasife alır ya da yeniden aktif eder.

    Danışan silinmez; randevu geçmişi korunur. Pasif danışana yeni randevu verilemez. Psikolog yalnızca kendi danışanının
    durumunu değiştirebilir. Geleceğe dönük planlanmış randevusu olan danışan pasife alınamaz (önce randevular iptal edilir).
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT aktif_mi, olusturan_psikolog_id FROM danisan_kodlari WHERE danisan_kod_id = %s FOR UPDATE;",
            (danisan_kod_id,),
        )
        danisan = cursor.fetchone()
        if danisan is None:
            raise HTTPException(status_code=404, detail="Danışan bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != danisan[1]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi danışanınızın durumunu değiştirebilirsiniz.")

        if danisan[0] == aktif_mi:
            return {"durum": "basarili", "aktif_mi": aktif_mi, "mesaj": "Danışan zaten bu durumda."}

        if not aktif_mi:
            cursor.execute(
                "SELECT COUNT(*) FROM randevular WHERE danisan_kod_id = %s AND durum = 'PLANLANDI' AND baslangic_zamani >= CURRENT_DATE;",
                (danisan_kod_id,),
            )
            planli = cursor.fetchone()[0]
            if planli:
                raise HTTPException(
                    status_code=409,
                    detail=f"Bu danışanın bugün ve sonrası için {planli} planlı randevusu var. Pasife almadan önce {PLANLI_RANDEVU_COZUMU}",
                )
        elif danisan[1] is not None:
            # Danışanı aktifleştirmek için psikoloğu aktif bir psikolog olmalı; aksi halde danışan randevu alamaz (psikolog dönünce
            # psikolog pasifliği nedeniyle pasif olanlar zaten otomatik geri açılır).
            cursor.execute(
                "SELECT 1 FROM personel p JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id JOIN roller r ON r.rol_id = k.rol_id "
                "WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';",
                (danisan[1],),
            )
            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=409,
                    detail="Bu danışanın psikologu şu an pasif. Danışanı aktifleştirmeden önce psikoloğu aktifleştirin (danışan da otomatik açılır).",
                )

        # Elle yapılan durum değişikliği, "psikolog pasifliği nedeniyle pasif" işaretini temizler (psikolog dönünce otomatik geri açılmasın/kapanmasın).
        cursor.execute("UPDATE danisan_kodlari SET aktif_mi = %s, psikolog_pasifligi_nedeniyle_pasif = FALSE WHERE danisan_kod_id = %s;", (aktif_mi, danisan_kod_id))
        durum_degisikligi_yaz(cursor, kullanici_id, "UPDATE", "danisan_kodlari", None, onceki={"aktif_mi": danisan[0]}, yeni={"aktif_mi": aktif_mi}, danisan_kod_id=danisan_kod_id)
        conn.commit()
        return {"durum": "basarili", "aktif_mi": aktif_mi, "mesaj": "Danışan aktif edildi." if aktif_mi else "Danışan pasife alındı."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/danisan-kodlari/{danisan_kod_id}/bilgiler")
def danisan_bilgilerini_guncelle(
    danisan_kod_id: str,
    bilgi: DanisanBilgiModeli,
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR")),
):
    """Danışanın yaş grubunu günceller (kapalı liste; serbest metin yoktur). Terapi türü randevuda tutulur.

    Psikolog yalnızca kendi danışanını güncelleyebilir. Geçmiş randevuların terapi türü değişmez; yetişkin olarak kaydedilince
    gelecekteki planlı randevulardaki oyun terapisi bireysel terapiye çevrilir.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT olusturan_psikolog_id, yas_grubu FROM danisan_kodlari WHERE danisan_kod_id = %s FOR UPDATE;", (danisan_kod_id,))
        danisan = cursor.fetchone()
        if danisan is None:
            raise HTTPException(status_code=404, detail="Danışan bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is not None and psikolog_rolu_mu(rol[0]):
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != danisan[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi danışanınızın bilgilerini güncelleyebilirsiniz.")

        cursor.execute(
            "UPDATE danisan_kodlari SET yas_grubu = %s WHERE danisan_kod_id = %s;",
            (bilgi.yas_grubu, danisan_kod_id),
        )
        durum_degisikligi_yaz(cursor, kullanici_id, "UPDATE", "danisan_kodlari", None, onceki={"yas_grubu": danisan[1] if len(danisan) > 1 else None},
                              yeni={"yas_grubu": bilgi.yas_grubu}, danisan_kod_id=danisan_kod_id)
        guncellenen = 0
        if bilgi.yas_grubu == "YETISKIN":
            # Yetişkinde oyun terapisi yoktur: GELECEKTEKİ planlı randevular bireysel terapiye çevrilir.
            # Geçmiş (tamamlanan, gelmedi, iptal) randevular seansta yapılanın kaydı olduğu için değişmez.
            cursor.execute(
                "UPDATE randevular SET terapi_turu = 'BIREYSEL_TERAPI' WHERE danisan_kod_id = %s AND durum = 'PLANLANDI' "
                "AND baslangic_zamani > NOW() AND terapi_turu = 'OYUN_TERAPISI';",
                (danisan_kod_id,),
            )
            guncellenen = cursor.rowcount if isinstance(cursor.rowcount, int) and cursor.rowcount > 0 else 0
            if guncellenen:
                cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo) VALUES (%s, %s, %s);", (kullanici_id, "UPDATE", "randevular"))
        conn.commit()
        return {"durum": "basarili", "yas_grubu": bilgi.yas_grubu, "guncellenen_randevu_sayisi": guncellenen,
                "mesaj": "Danışan bilgileri güncellendi."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/psikologlar")
def aktif_psikologlari_listele(kullanici_id: int = Depends(izin_kontrol("TAKVIM_GORUNTULE")), pasifler_dahil: bool = False):
    """Aktif psikologlar (randevu formundaki psikolog seçimi bunu kullanır).

    pasifler_dahil=true: ad gösterimi içindir; randevusu ya da danışan kodu olan pasif ya da sonradan başka role geçmiş eski
    psikologlar da gelir ve her kayıtta aktif_mi bilgisi bulunur. Böylece eski randevularda "Psikolog #19" yerine gerçek ad görünür."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        if pasifler_dahil:
            cursor.execute("""
                SELECT p.personel_id, k.kullanici_adi, k.kullanici_id,
                       (p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG') AS aktif_mi
                FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id
                WHERE (p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG')
                   OR EXISTS (SELECT 1 FROM randevular x WHERE x.psikolog_id = p.personel_id)
                   OR EXISTS (SELECT 1 FROM danisan_kodlari d WHERE d.olusturan_psikolog_id = p.personel_id)
                ORDER BY k.kullanici_adi;
            """)
            return [{"personel_id": k[0], "ad_soyad": k[1], "kullanici_id": k[2], "aktif_mi": bool(k[3])} for k in cursor.fetchall()]
        cursor.execute("""
            SELECT p.personel_id, k.kullanici_adi, k.kullanici_id
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id
            WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "ad_soyad": k[1], "kullanici_id": k[2]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# ==========================================
# FAALİYET YÖNETİMİ MODÜLÜ API UÇLARI
# ==========================================



# --- Faaliyet formundaki öğrenci listesi ---
@app.get("/api/ogrenciler-liste")
def ogrencileri_getir(kullanici_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Ad Soyad, Öğrenci Numarası ve türü çek. Tüm öğrenciler listelenir;
        # her öğrencinin yanında türü (gönüllü, danışma masası, asistan) belirtilir.
        cursor.execute(
            "SELECT ogrenci_id, ad_soyad, ogrenci_numarasi, tur::text FROM ogrenciler WHERE aktif_mi = true "
            "ORDER BY ad_soyad, ogrenci_numarasi;"
        )

        liste = []
        for r in cursor.fetchall():
            metin = f"{r[1]} - [{r[2]}]"
            etiket = OGRENCI_TUR_ETIKETLERI.get(r[3])
            if etiket:
                metin += f" ({etiket})"
            liste.append({"id": r[0], "metin": metin, "tur": r[3]})
        return liste
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()



from pydantic import BaseModel, ConfigDict, StrictBool


class OgrenciAktiflikModeli(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aktif_mi: StrictBool



# ============================================================
# ÖĞRENCİ YÖNETİMİ: LİSTE, PUAN, 10 YIL, ERTELEME, SİLME
# ============================================================

from datetime import date as _ogr_date
from pydantic import BaseModel as _OgrBaseModel
from pydantic import ConfigDict as _OgrConfigDict
from pydantic import StrictBool as _OgrStrictBool
from psycopg2 import sql as _ogr_sql


class OgrenciErteleModeli(_OgrBaseModel):
    model_config = _OgrConfigDict(extra="forbid")
    yeni_uyari_tarihi: _ogr_date


class OgrenciSilOnayModeli(_OgrBaseModel):
    model_config = _OgrConfigDict(extra="forbid")
    onayla: _OgrStrictBool


@app.get("/api/ogrenciler-yonetim")
def ogrenciler_yonetim_listesi(
    yetkili_id: int = Depends(
        izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")
    )
):
    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT
                    o.ogrenci_id,
                    o.ad_soyad,
                    o.ogrenci_numarasi,
                    o.tur::text,
                    o.aktif_mi,
                    o.kullanici_id,
                    k.kullanici_adi,
                    r.rol_adi,
                    o.telefon,
                    o.olusturulma_tarihi,

                    (
                        o.tur::text = 'GONULLU'
                        AND NOT o.aktif_mi
                        AND o.pasife_alinma_tarihi::date
                            <= (
                                CURRENT_DATE
                                - INTERVAL '2 years'
                            )::date
                    ) AS kayit_suresi_doldu,

                    e.yeni_uyari_tarihi,

                    (
                        e.yeni_uyari_tarihi > CURRENT_DATE
                    ) AS ertelendi_mi,

                    o.pasife_alinma_tarihi

                FROM ogrenciler o

                LEFT JOIN kullanicilar k
                    ON k.kullanici_id = o.kullanici_id

                LEFT JOIN roller r
                    ON r.rol_id = k.rol_id

                LEFT JOIN LATERAL (
                    SELECT yeni_uyari_tarihi
                    FROM ogrenci_kayit_erteleme_gecmisi e
                    WHERE e.ogrenci_id = o.ogrenci_id
                    ORDER BY e.erteleme_id DESC
                    LIMIT 1
                ) e ON TRUE

                ORDER BY o.ogrenci_id DESC;
            """)

            sonuc = []

            for v in cursor.fetchall():
                sonuc.append({
                    "ogrenci_id": v[0],
                    "ad_soyad": v[1],
                    "ogrenci_numarasi": v[2],
                    "tur": v[3],
                    "tur_etiketi":
                        OGRENCI_TUR_ETIKETLERI.get(
                            v[3], v[3]
                        ),
                    "aktif_mi": v[4],
                    "kullanici_id": v[5],
                    "kullanici_adi": v[6],
                    "rol_adi": v[7],
                    "telefon": v[8],
                    "olusturulma_tarihi":
                        v[9].isoformat() if v[9] else None,
                    "kayit_suresi_doldu": bool(v[10]),
                    "ertelemeye_kadar":
                        v[11].isoformat() if v[11] else None,
                    "ertelendi_mi": bool(v[12]),
                    "pasife_alinma_tarihi":
                        v[13].isoformat() if v[13] else None,
                })

            return sonuc

    finally:
        conn.close()


@app.get("/api/ogrenciler/{ogrenci_id}/puanlar")
def ogrenci_puan_detayi(
    ogrenci_id: int,
    baslangic: _ogr_date,
    bitis: _ogr_date,
    yetkili_id: int = Depends(
        izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")
    )
):
    if baslangic > bitis:
        raise HTTPException(
            status_code=422,
            detail="Başlangıç tarihi bitişten büyük olamaz."
        )

    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM ogrenciler WHERE ogrenci_id=%s",
                (ogrenci_id,)
            )

            if cursor.fetchone() is None:
                raise HTTPException(
                    status_code=404,
                    detail="Öğrenci bulunamadı."
                )

            cursor.execute("""
                SELECT
                    t.faaliyet_tarihi,
                    f.faaliyet_adi,
                    t.adet,
                    COALESCE(b.birim_adi, ''),
                    t.kayit_puani,
                    (t.adet * t.kayit_puani)

                FROM ogrenci_faaliyet_takip t

                JOIN faaliyetler f
                    ON f.faaliyet_id = t.faaliyet_id

                LEFT JOIN faaliyet_birimleri b
                    ON b.birim_id = t.birim_id

                WHERE t.ogrenci_id = %s
                  AND t.faaliyet_tarihi BETWEEN %s AND %s

                ORDER BY
                    t.faaliyet_tarihi DESC,
                    t.takip_id DESC;
            """, (ogrenci_id, baslangic, bitis))

            faaliyetler = []

            for tarih, ad, adet, birim, puan, toplam in (
                cursor.fetchall()
            ):
                faaliyetler.append({
                    "tarih": tarih.isoformat(),
                    "faaliyet": ad,
                    "adet": adet,
                    "birim": birim,
                    "birim_puan": float(puan),
                    "toplam_puan": float(toplam),
                })

            return {
                "ogrenci_id": ogrenci_id,
                "baslangic": baslangic.isoformat(),
                "bitis": bitis.isoformat(),
                "toplam_puan": sum(
                    f["toplam_puan"] for f in faaliyetler
                ),
                "faaliyetler": faaliyetler,
            }

    finally:
        conn.close()








def _ogrenci_saklama_suresi_kontrol(cursor, ogrenci_id):
    """Gönüllü öğrencinin kaydı, pasife alındıktan 2 yıl geçmişse silinebilir ya da ertelenebilir (aktif öğrencinin süresi işlemez)."""
    cursor.execute("""
        SELECT
            tur::text,
            aktif_mi,
            pasife_alinma_tarihi,
            kullanici_id,
            ogrenci_numarasi
        FROM ogrenciler
        WHERE ogrenci_id = %s
        FOR UPDATE;
    """, (ogrenci_id,))

    ogrenci = cursor.fetchone()

    if ogrenci is None:
        raise HTTPException(
            status_code=404,
            detail="Öğrenci bulunamadı."
        )

    tur, aktif_mi, pasife_alinma, kullanici_id, ogrenci_no = ogrenci

    if tur != "GONULLU":
        raise HTTPException(
            status_code=409,
            detail=(
                "Saklama süresi işlemi yalnızca "
                "Gönüllü Öğrenciler içindir."
            )
        )

    if aktif_mi or pasife_alinma is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Saklama süresi yalnızca pasife alınmış "
                "öğrenciler için işler. Bu öğrenci aktif."
            )
        )

    cursor.execute("""
        SELECT (
            %s::date <= (
                CURRENT_DATE - INTERVAL '2 years'
            )::date
        );
    """, (pasife_alinma.date(),))

    if not cursor.fetchone()[0]:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu öğrencinin pasif kalma süresi "
                "(2 yıl) dolmadı."
            )
        )

    return kullanici_id, ogrenci_no


@app.patch("/api/ogrenciler/{ogrenci_id}/silme-ertele")
def ogrenci_silme_ertele(
    ogrenci_id: int,
    veri: OgrenciErteleModeli,
    yetkili_id: int = Depends(
        izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")
    )
):
    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            _, ogrenci_no = _ogrenci_saklama_suresi_kontrol(
                cursor, ogrenci_id
            )

            cursor.execute("SELECT CURRENT_DATE")
            bugun = cursor.fetchone()[0]

            if veri.yeni_uyari_tarihi <= bugun:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Erteleme tarihi bugünden sonra olmalıdır."
                    )
                )

            cursor.execute("""
                INSERT INTO ogrenci_kayit_erteleme_gecmisi
                (
                    ogrenci_id,
                    ogrenci_numarasi,
                    yeni_uyari_tarihi,
                    erteleyen_kullanici_id
                )
                VALUES (%s, %s, %s, %s)
                RETURNING erteleme_id;
            """, (
                ogrenci_id,
                ogrenci_no,
                veri.yeni_uyari_tarihi,
                yetkili_id
            ))

            erteleme_id = cursor.fetchone()[0]

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "CREATE",
                yetkili_id,
                "ogrenci_kayit_erteleme_gecmisi",
                erteleme_id,
                mevcut_cursor=cursor
            )

        conn.commit()

        return {
            "ogrenci_id": ogrenci_id,
            "yeni_uyari_tarihi":
                veri.yeni_uyari_tarihi.isoformat(),
        }

    except HTTPException:
        conn.rollback()
        raise

    except Exception:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Erteleme kaydedilemedi."
        )

    finally:
        conn.close()


@app.delete("/api/ogrenciler/{ogrenci_id}/saklama-suresi-sil")
def ogrenci_saklama_suresi_sil(
    ogrenci_id: int,
    veri: OgrenciSilOnayModeli,
    yetkili_id: int = Depends(
        # Kalıcı ve geri alınamaz işlem: öğrenci listeleme/ekleme iznine (FAALIYET_KAYITLARI_DUZENLE) değil, ayrı bir izne bağlıdır.
        izin_kontrol("OGRENCI_KAYDI_SIL")
    )
):
    if not veri.onayla:
        raise HTTPException(
            status_code=422,
            detail="Silme işlemi açık onay gerektirir."
        )

    conn = vt_baglan(VT_AYARLARI)

    try:
        with conn.cursor() as cursor:
            kullanici_id, _ = _ogrenci_saklama_suresi_kontrol(
                cursor, ogrenci_id
            )

            if kullanici_id is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Öğrenciye bağlı kullanıcı hesabı var. "
                        "Bu ekrandan silinemez."
                    )
                )

            cursor.execute("""
                SELECT yeni_uyari_tarihi
                FROM ogrenci_kayit_erteleme_gecmisi
                WHERE ogrenci_id = %s
                ORDER BY erteleme_id DESC
                LIMIT 1;
            """, (ogrenci_id,))

            erteleme = cursor.fetchone()

            cursor.execute("SELECT CURRENT_DATE")
            bugun = cursor.fetchone()[0]

            if erteleme and erteleme[0] > bugun:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Bu kaydın erteleme tarihi "
                        "henüz gelmedi."
                    )
                )

            # Faaliyet kayıtları öğrenciyle birlikte silinecek.
            # Diğer beklenmedik FK ilişkilerinde silme engellenir.
            cursor.execute("""
                SELECT
                    n.nspname,
                    t.relname,
                    a.attname
                FROM pg_constraint c

                JOIN pg_class t
                    ON t.oid = c.conrelid

                JOIN pg_namespace n
                    ON n.oid = t.relnamespace

                JOIN LATERAL
                    unnest(c.conkey) AS k(attnum)
                    ON TRUE

                JOIN pg_attribute a
                    ON a.attrelid = t.oid
                   AND a.attnum = k.attnum

                WHERE c.contype = 'f'
                  AND c.confrelid = 'ogrenciler'::regclass
                  AND t.relname NOT IN (
                      'ogrenci_kayit_erteleme_gecmisi',
                      'ogrenci_faaliyet_takip'
                  );
            """)

            baglantilar = cursor.fetchall()

            for schema, tablo, sutun in baglantilar:
                sorgu = _ogr_sql.SQL(
                    "SELECT 1 FROM {}.{} "
                    "WHERE {} = %s LIMIT 1"
                ).format(
                    _ogr_sql.Identifier(schema),
                    _ogr_sql.Identifier(tablo),
                    _ogr_sql.Identifier(sutun)
                )

                cursor.execute(sorgu, (ogrenci_id,))

                if cursor.fetchone():
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Öğrencinin faaliyet dışındaki "
                            "ilişkili kayıtları nedeniyle "
                            "silme işlemi engellendi."
                        )
                    )

            # Yalnızca seçilen öğrencinin faaliyetlerini sil.
            cursor.execute(
                """
                DELETE FROM ogrenci_faaliyet_takip
                WHERE ogrenci_id = %s;
                """,
                (ogrenci_id,)
            )
            silinen_faaliyet_sayisi = cursor.rowcount

            # Erteleme geçmişi öğrenci numarasını taşır (öğrenciye bağlı kimlik bilgisi). Öğrenciyle birlikte imha edilir;
            # kimin ne zaman erteleme yaptığı denetim kayıtlarında (kimliksiz) zaten durur.
            cursor.execute(
                "DELETE FROM ogrenci_kayit_erteleme_gecmisi WHERE ogrenci_id = %s;",
                (ogrenci_id,)
            )
            silinen_erteleme_sayisi = cursor.rowcount

            # Saklama süresi (pasife alındıktan 2 yıl) sonunda yapılan imha: denetim kaydına kişisel veri (ad, telefon...) YAZILMAZ;
            # yalnızca kimliksiz alanlar ve silinen faaliyet sayısı tutulur.
            silinen = satiri_sil_ve_ayrintisini_al(cursor, "ogrenciler", ogrenci_id)
            if silinen is not None:
                silinen["silinen_faaliyet_kaydi_sayisi"] = silinen_faaliyet_sayisi
                silinen["silinen_erteleme_kaydi_sayisi"] = silinen_erteleme_sayisi

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "DELETE",
                yetkili_id,
                "ogrenciler",
                ogrenci_id,
                mevcut_cursor=cursor,
                ayrinti=silinen,
            )

        conn.commit()

        return {
            "durum": "silindi",
            "ogrenci_id": ogrenci_id,
        }

    except HTTPException:
        conn.rollback()
        raise

    except psycopg2.errors.ForeignKeyViolation:
        conn.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Bağlı kayıtlar nedeniyle silinemedi. "
                "İşlem iptal edildi."
            )
        )

    except Exception:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Öğrenci kaydı silinemedi."
        )

    finally:
        conn.close()


@app.patch("/api/ogrenciler/{ogrenci_id}/aktiflik")
def ogrenci_aktiflik_duzenle(
    ogrenci_id: int,
    veri: OgrenciAktiflikModeli,
    yetkili_id: int = Depends(
        izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")
    )
):
    conn = None

    try:
        conn = vt_baglan(VT_AYARLARI)

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT kullanici_id FROM ogrenciler "
                "WHERE ogrenci_id = %s;",
                (ogrenci_id,)
            )

            kayit = cursor.fetchone()

            if kayit is None:
                raise HTTPException(
                    status_code=404,
                    detail="Öğrenci bulunamadı."
                )

            kullanici_id = kayit[0]
            rol = None

            if kullanici_id is not None:
                cursor.execute("""
                    SELECT r.rol_adi
                    FROM kullanicilar k
                    JOIN roller r ON r.rol_id = k.rol_id
                    WHERE k.kullanici_id = %s
                    FOR UPDATE OF k;
                """, (kullanici_id,))

                rol_kaydi = cursor.fetchone()

                if rol_kaydi is None:
                    raise HTTPException(
                        status_code=409,
                        detail="Bağlı kullanıcı bulunamadı."
                    )

                rol = rol_kaydi[0]

            cursor.execute("""
                SELECT tur::text, aktif_mi
                FROM ogrenciler
                WHERE ogrenci_id = %s
                FOR UPDATE;
            """, (ogrenci_id,))

            tur, eski_durum = cursor.fetchone()

            if tur == "DANISMA_MASASI" and not veri.aktif_mi:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Danışma Masası Öğrencileri "
                        "bu ekrandan pasife alınamaz."
                    )
                )

            if (
                veri.aktif_mi
                and tur == "DANISMA_MASASI"
                and kullanici_id is not None
                and rol != "DANISMA_OGRENCISI"
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Bu kullanıcı artık Danışma Öğrencisi "
                        "rolünde değil. Önce rolünü güncelleyin."
                    )
                )

            if not veri.aktif_mi:
                cursor.execute("""
                    SELECT 1
                    FROM danisma_masasi_oturumlari
                    WHERE ogrenci_id = %s
                      AND bitis_zamani IS NULL
                    LIMIT 1;
                """, (ogrenci_id,))

                if cursor.fetchone() is not None:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            "Öğrencinin açık görevi var. "
                            "Önce görevi bitirin."
                        )
                    )

            hesap_guncellenecek = (
                tur == "DANISMA_MASASI"
                and rol == "DANISMA_OGRENCISI"
                and kullanici_id is not None
            )

            personel_id = None

            if hesap_guncellenecek:
                cursor.execute("""
                    SELECT personel_id
                    FROM personel
                    WHERE kullanici_id = %s
                    FOR UPDATE;
                """, (kullanici_id,))

                personel = cursor.fetchone()

                if personel is None:
                    raise HTTPException(
                        status_code=409,
                        detail="Bağlı personel kaydı bulunamadı."
                    )

                personel_id = personel[0]

            cursor.execute(
                "UPDATE ogrenciler SET aktif_mi = %s "
                "WHERE ogrenci_id = %s;",
                (veri.aktif_mi, ogrenci_id)
            )

            if hesap_guncellenecek:
                cursor.execute(
                    "UPDATE kullanicilar SET aktif_mi = %s "
                    "WHERE kullanici_id = %s;",
                    (veri.aktif_mi, kullanici_id)
                )

            if eski_durum != veri.aktif_mi:
                aktiflik_degisimi = {
                    "onceki": {"aktif_mi": eski_durum},
                    "yeni": {"aktif_mi": veri.aktif_mi},
                }
                denetim_kaydi_olustur(
                    VT_AYARLARI,
                    "UPDATE",
                    yetkili_id,
                    "ogrenciler",
                    ogrenci_id,
                    mevcut_cursor=cursor,
                    ayrinti=aktiflik_degisimi
                )

                if hesap_guncellenecek:
                    denetim_kaydi_olustur(
                        VT_AYARLARI,
                        "UPDATE",
                        yetkili_id,
                        "kullanicilar",
                        kullanici_id,
                        mevcut_cursor=cursor,
                        ayrinti={
                            **aktiflik_degisimi,
                            "neden": "danışma öğrencisinin aktifliği ile birlikte değişti",
                        }
                    )

                    denetim_kaydi_olustur(
                        VT_AYARLARI,
                        "UPDATE",
                        yetkili_id,
                        "personel",
                        personel_id,
                        mevcut_cursor=cursor
                    )

            conn.commit()

        return {
            "ogrenci_id": ogrenci_id,
            "aktif_mi": veri.aktif_mi,
            "hesap_guncellendi": hesap_guncellenecek,
        }

    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Öğrenci aktifliği güncellenemedi."
        )

    finally:
        if conn is not None:
            conn.close()



@app.post("/api/ogrenci-ekle")
def ogrenci_ekle(ogr: OgrenciEkleModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ogrenciler
            (ad_soyad, ogrenci_numarasi, telefon, tur, bolum, sinif)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING ogrenci_id;
        """, (ogr.ad_soyad, ogr.ogrenci_numarasi, ogr.telefon, ogr.tur, ogr.bolum, ogr.sinif))

        yeni_id = cursor.fetchone()[0]

        # Ad, numara ve telefon kişisel veridir (FR-008): denetime yalnızca öğrencinin türü yazılır.
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=yetkili_id,
            hedef_tablo="ogrenciler",
            hedef_kayit_id=yeni_id,
            mevcut_cursor=cursor,
            ayrinti={"yeni": {"tur": ogr.tur}}
        )

        conn.commit()
        return {"durum": "basarili", "mesaj": "Öğrenci başarıyla sisteme eklendi.", "ogrenci_id": yeni_id}

    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail="Bu öğrenci numarası sistemde zaten kayıtlı!")
    except Exception:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()



# --- 1. YENİ İZİN EKLEME (POST) ---
@app.post("/api/izinler", status_code=201)
def izin_ekle(izin_verisi: dict, kullanici_id: int = Depends(izin_kontrol("ROL_DUZENLE"))):
    izin_adi = izin_verisi.get("izin_adi")
    if not isinstance(izin_adi, str) or not izin_adi.strip() or len(izin_adi) > 100:
        raise HTTPException(status_code=422, detail="İzin adı zorunludur ve en fazla 100 karakter olabilir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT INTO izinler (izin_adi) VALUES (%s) RETURNING izin_id",
            (izin_adi,)
        )
        yeni_id = cursor.fetchone()[0]
        # Yeni izin "kimsede yok" durumunda kalmasın: ADMIN otomatik sahip olur, diğer roller kapalı başlar.
        cursor.execute(
            """
            INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
            SELECT r.rol_id, %s, CASE WHEN UPPER(r.rol_adi) = 'ADMIN' THEN 1 ELSE 0 END
            FROM roller r
            ON CONFLICT (rol_id, izin_id) DO NOTHING;
            """,
            (yeni_id,),
        )
        ayrintili_kayit_yaz(cursor, kullanici_id, "CREATE", "izinler", yeni_id, yeni={"izin_adi": izin_adi, "verilen_roller": ["ADMIN"]})
        conn.commit()
        return {"mesaj": "İzin başarıyla eklendi", "izin_id": yeni_id}
    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=409, detail="Bu izin adı zaten tanımlı.")
    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İzin eklenirken beklenmeyen bir hata oluştu."
        )
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


# --- 2. İZİN VE ROL İLİŞKİLERİNİ GÜNCELLEME (PUT) ---

@app.put("/api/izinler/{izin_id}")
def izin_duzenle(izin_id: int, veri: IzinDuzenleModeli, kullanici_id: int = Depends(izin_kontrol("IZIN_DUZENLE"))):
    """Bir iznin GÖRÜNEN ADINI ve hangi rollere verildiğini günceller.
 
    Teknik ad (izin_adi) değiştirilmez: izin_kontrol("...") bu adla çalışır.
    """
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
 
        cursor.execute("SELECT izin_id, izin_adi, gorunen_ad FROM izinler WHERE izin_id = %s FOR UPDATE;", (izin_id,))
        izin_kaydi = cursor.fetchone()
        if izin_kaydi is None:
            raise HTTPException(status_code=404, detail="İzin bulunamadı.")
 
        cursor.execute("SELECT rol_id, rol_adi FROM roller;")
        roller = {r[0]: r[1] for r in cursor.fetchall()}
        cursor.execute("SELECT rol_id FROM rol_izinleri WHERE izin_id = %s AND izin_var = 1;", (izin_id,))
        onceki_roller = {r[0] for r in cursor.fetchall()}
 
        secilenler = set(veri.verilen_rol_idleri)
        if not secilenler.issubset(roller.keys()):
            raise HTTPException(status_code=422, detail="Geçersiz rol seçildi.")
 
        # ADMIN rolünden izin kaldırılamaz (sistemden kilitlenmeyi önler).
        admin_idleri = [rid for rid, ad in roller.items() if ad == "ADMIN"]
        if any(rid not in secilenler for rid in admin_idleri):
            raise HTTPException(status_code=422, detail="ADMIN rolünden izin kaldırılamaz.")
 
        cursor.execute(
            "UPDATE izinler SET gorunen_ad = %s WHERE izin_id = %s;",
            (veri.gorunen_ad.strip(), izin_id),
        )
 
        for rid in roller:
            deger = 1 if rid in secilenler else 0
            cursor.execute(
                "UPDATE rol_izinleri SET izin_var = %s WHERE rol_id = %s AND izin_id = %s;",
                (deger, rid, izin_id),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO rol_izinleri (rol_id, izin_id, izin_var) VALUES (%s, %s, %s);",
                    (rid, izin_id, deger),
                )
 
        # Kim, hangi izni, hangi rollere verdi/aldı: önceki ve yeni değer (rol adlarıyla) denetim kaydına yazılır.
        adlar = lambda kimlikler: sorted(roller[r] for r in kimlikler)
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="izinler",
            hedef_kayit_id=izin_id,
            mevcut_cursor=cursor,
            ayrinti={
                "izin": izin_kaydi[1] if len(izin_kaydi) > 1 else None,
                "onceki": {"gorunen_ad": izin_kaydi[2] if len(izin_kaydi) > 2 else None, "verilen_roller": adlar(onceki_roller & set(roller))},
                "yeni": {"gorunen_ad": veri.gorunen_ad.strip(), "verilen_roller": adlar(secilenler)},
                "eklenen_roller": adlar(secilenler - onceki_roller),
                "kaldirilan_roller": adlar((onceki_roller & set(roller)) - secilenler),
            },
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "İzin güncellendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=500, detail="İzin güncellenirken bir hata oluştu.")
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# --- server/sunucu.py parçalama: cihaz, rezervasyon, bölüm ve proje türü uçları (kendi dosyalarında) ---
from server import bolum_proje_api, cihaz_api, rezervasyon_api  # noqa: E402
app.include_router(cihaz_api.router_olustur(izin_kontrol))
app.include_router(rezervasyon_api.router_olustur(izin_kontrol))
app.include_router(bolum_proje_api.router_olustur(izin_kontrol))
from server.cihaz_api import (  # noqa: E402  (geriye dönük adlar)
    cihaz_ekle,
    cihaz_guncelle,
    cihazin_acik_arizasi_var_mi,
    cihazlari_listele,
    GECMIS_OLAY_SINIRI,
    _gun_metni,
    _iso,
    cihaz_gecmisi_getir,
    cihaz_detayi_getir,
)
from server.rezervasyon_api import (  # noqa: E402  (geriye dönük adlar)
    rezervasyon_uygunlugunu_denetle,
    cihaz_rezervasyonu_yap,
    REZERVASYON_YONETIM_YETKISI_SQL,
    REZERVASYON_YETKI_MESAJI,
    rezervasyon_iptal,
    rezervasyon_guncelle,
    rezervasyon_gorunen_durumu,
    rezervasyonlari_listele,
)
from server.bolum_proje_api import (  # noqa: E402  (geriye dönük adlar)
    bolumleri_listele,
    bolum_olustur,
    proje_turu_anahtari,
    proje_turlerini_listele,
    proje_turu_olustur,
)


# --- server/sunucu.py parçalama: arıza, bakım, kalibrasyon ve bakım planı uçları (kendi dosyalarında) ---
from server import ariza_api, bakim_kalibrasyon_api, bakim_plani_api  # noqa: E402
app.include_router(ariza_api.router_olustur(izin_kontrol))
app.include_router(bakim_kalibrasyon_api.router_olustur(izin_kontrol, izin_kontrol_biri))
app.include_router(bakim_plani_api.router_olustur(mevcut_kullanici_id))
from server.ariza_api import (  # noqa: E402  (geriye dönük adlar)
    ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR,
    arizadan_sonra_cihaz_durumu,
    arizalari_listele,
    ariza_bildir,
    ariza_guncelle,
)
from server.bakim_kalibrasyon_api import (  # noqa: E402  (geriye dönük adlar)
    bakimlari_listele,
    bakim_kaydi_ekle,
    bakim_guncelle,
    bakim_kaydi_sil,
    kalibrasyonlari_listele,
    kalibrasyon_kaydi_ekle,
    kalibrasyon_guncelle,
    kalibrasyon_kaydi_sil,
)
from server.bakim_plani_api import (  # noqa: E402  (geriye dönük adlar)
    bakim_plani_durumu,
    _plan_yetkileri,
    _plan_turu_yetkisini_dogrula,
    bakim_planlarini_listele,
    plani_ilerlet,
    plan_periyodu,
    _ayni_planli_aktif_kayit_var_mi,
    bakim_plani_ekle,
    bakim_plani_guncelle,
    bakim_plani_sil,
)


# --- server/sunucu.py parçalama: Danışma Masası uçları (kendi dosyasında) ---
from server import danisma_masasi_api  # noqa: E402
app.include_router(danisma_masasi_api.router_olustur(izin_kontrol))
from server.danisma_masasi_api import (  # noqa: E402  (geriye dönük adlar)
    danisma_oturumu_baslat,
    danisma_oturumu_bitir,
    danisma_aktif_oturum,
    danisma_oturum_gecmisi,
    danisma_onay_bildirimleri,
    DANISMA_GOREV_EN_UZUN_SAAT,
    DANISMA_GOREV_COK_UZUN_MESAJI,
    danisma_gorevi_cok_uzun_mu,
    DANISMA_LISTE_EN_FAZLA,
    danisma_yonetim_oturumlari,
    danisma_yonetim_oturum_onayla,
    danisma_yonetim_onay_geri_al,
    danisma_yonetim_ogrencileri,
    danisma_yonetim_oturum_olustur,
    danisma_yonetim_oturum_duzenle,
)


# Oda Etkinlikleri API
from server.oda_etkinlikleri_api import router_olustur

app.include_router(router_olustur(izin_kontrol, VT_AYARLARI))

# Ayrılan modüller (server/sunucu.py'nin parçalanması): uçlar kendi dosyalarında; yetki bağımlılığı buradan verilir.
# Fonksiyon adları geriye dönük olarak burada da erişilebilir kalır (testler `server.sunucu.<ad>` ile içe aktarır).
from server import (
    anasayfa_api, audit_api, bildirim_ozeti_api, cihaz_raporlari_api, cihaz_uygunluk_api, danisma_raporlari_api, faaliyet_birimleri_api,
    faaliyet_kayitlari_api, faaliyet_turleri_api, puan_raporu_api, randevu_oda_raporlari_api, surum_api, yonetim_raporlari_api,
)

app.include_router(audit_api.router_olustur(izin_kontrol))
app.include_router(cihaz_raporlari_api.router_olustur(izin_kontrol))
app.include_router(yonetim_raporlari_api.router_olustur(izin_kontrol))
app.include_router(danisma_raporlari_api.router_olustur(izin_kontrol))
app.include_router(cihaz_uygunluk_api.router_olustur(izin_kontrol))
app.include_router(randevu_oda_raporlari_api.router_olustur(izin_kontrol))
app.include_router(puan_raporu_api.router_olustur(izin_kontrol))
app.include_router(surum_api.router_olustur(izin_kontrol, mevcut_kullanici_id))
app.include_router(anasayfa_api.router_olustur(izin_kontrol, izin_kontrol_biri, mevcut_kullanici_id))
app.include_router(bildirim_ozeti_api.router_olustur(izin_kontrol))
app.include_router(faaliyet_turleri_api.router_olustur(izin_kontrol))
app.include_router(faaliyet_birimleri_api.router_olustur(izin_kontrol))
app.include_router(faaliyet_kayitlari_api.router_olustur(izin_kontrol))
audit_kayitlarini_getir = audit_api.audit_kayitlarini_getir
cihaz_raporlari = cihaz_raporlari_api.cihaz_raporlari
danisma_raporlari = danisma_raporlari_api.danisma_raporlari
from server.cihaz_uygunluk_api import (  # noqa: E402  (geriye dönük adlar)
    UYGUNLUK_EN_FAZLA_GUN,
    UYGUNLUK_ACIK_UCLU_DURUMLAR,
    _uygunluk_uyari,
    cihaz_uygunluk_hazirla,
    cihaz_uygunluk_getir,
)
from server.randevu_oda_raporlari_api import (  # noqa: E402  (geriye dönük adlar)
    randevu_raporu_secenekleri,
    oda_kullanimi,
    randevu_raporu,
)
from server.puan_raporu_api import (  # noqa: E402  (geriye dönük adlar)
    PUAN_RAPORU_DURUMLARI,
    puan_raporu,
)
from server.faaliyet_turleri_api import (  # noqa: E402  (geriye dönük adlar)
    faaliyetleri_getir,
    FAALIYET_PUANI_EN_FAZLA,
    FaaliyetTuruEkleModeli,
    FAALIYET_ADI_KAYITLI_MESAJI,
    _faaliyet_adi_kayitli_mi,
    faaliyet_turu_ekle,
    FaaliyetTuruDuzenleModeli,
    faaliyet_turu_duzenle,
)
from server.faaliyet_birimleri_api import (  # noqa: E402  (geriye dönük adlar)
    faaliyet_birimleri_getir,
    BIRIM_ADI_KAYITLI_MESAJI,
    faaliyet_birimi_ekle,
    faaliyet_birimi_guncelle,
    faaliyet_birimi_sil,
)
from server.faaliyet_kayitlari_api import (  # noqa: E402  (geriye dönük adlar)
    faaliyet_kaydi_ekle,
    faaliyet_kayitlarini_getir,
    faaliyet_kaydi_guncelle,
    faaliyet_kaydi_sil,
)
from server.anasayfa_api import (  # noqa: E402  (geriye dönük adlar)
    dashboard_ozet_getir,
    _tarih_kisa,
    dashboard_bugunku_randevular,
    dashboard_bugunku_rezervasyonlar,
    dashboard_bugunku_etkinlikler,
    _benim_islerim,
    dashboard_benim_gunum,
    duyurulari_getir,
    duyurulari_okundu_isaretle,
    duyuruyu_okundu_isaretle,
    duyuruyu_tekrar_goster,
    duyuru_yayinla,
    duyuru_kaldir,
    yaklasan_islemler_getir,
    DASHBOARD_ARALIKLARI,
    ARALIK_SORGU_DESENI,
    BUGUNKU_ETKINLIK_UST_SINIR,
    ISLER_IZINLERI,
    DUYURU_UST_SINIR,
    DUYURU_YENI_GUN,
    YAKLASAN_ISLEM_UST_SINIR,
)
from server.surum_api import (  # noqa: E402  (geriye dönük adlar)
    _sistem_durumu,
    _SURUM,
    _UYGULAMA_ADI,
    surum_bilgisi,
    sistem_durumu_getir,
)
from server.yonetim_raporlari_api import (  # noqa: E402  (geriye dönük adlar: testler `server.sunucu.<ad>` ile içe aktarır)
    _yonetim_onceki_donem,
    _rapor_donemi_dogrula,
    yonetim_randevu_ozet,
    yonetim_cihaz_ozet,
    yonetim_ogrenci_ozet,
    yonetim_proje_etkinlik_ozet,
    yonetim_kullanim_ozet,
    cihaz_rezervasyon_raporu,
    oda_kullanim_raporu,
    yetki_raporu_getir,
    ogrenci_raporu_getir,
    faaliyet_raporu_getir,
    bakim_plani_raporu_getir,
    yonetim_bugun_merkezde,
    yonetim_gunluk_detay,
)


# ==========================================
# SÜRÜM / SİSTEM DURUMU / LİSTE AKTARIM KAYDI
# ==========================================
from typing import Literal as _Literal





# Liste ekranlarındaki "Excel'e Aktar" işleminin denetim kaydı: kim, ne zaman, hangi liste, kaç satır.
# Kayıt için, o listeyi görme yetkisinin aynısı gerekir (listeyi göremeyen kişi aktarım kaydı da yazamaz).
# liste -> (listeyi görmek için gereken izin(ler) [birinin olması yeter], denetim kaydındaki hedef tablo)
LISTE_AKTARIM_HEDEFLERI = {
    "CIHAZ": ("CIHAZ_UYGUNLUK_GORUNTULE", "cihazlar"),
    "OGRENCI": ("FAALIYET_KAYITLARI_DUZENLE", "ogrenciler"),
    "DANISAN": ("RANDEVU_OLUSTUR", "danisan_kodlari"),
    "REZERVASYON": ("CIHAZ_REZERVASYON", "cihaz_rezervasyonlari"),
    "BAKIM": (("BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET"), "cihaz_bakimlari"),
    "KALIBRASYON": (("KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET"), "cihaz_kalibrasyonlari"),
    "ARIZA": ("ARIZA_KAYITLARI_YONET", "cihaz_arizalari"),
    "BAKIM_PLANI": (("BAKIM_KAYITLARI_YONET", "KALIBRASYON_KAYITLARI_YONET", "BAKIM_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_GORUNTULE"), "cihaz_bakim_planlari"),
    "DENETIM": ("AUDIT_KAYITLARI_INCELE", "denetim_kayitlari"),
}


class ListeAktarimModeli(_DurumBaseModel):
    liste: _Literal["CIHAZ", "OGRENCI", "DANISAN", "REZERVASYON", "BAKIM", "KALIBRASYON", "ARIZA", "BAKIM_PLANI", "DENETIM"]
    satir_sayisi: int = _DurumField(ge=0, le=1_000_000)
    bicim: _Literal["EXCEL", "PDF"] = "EXCEL"                 # dosya türü; eski istemciler göndermez (Excel sayılır)


@app.post("/api/liste-aktarim-kaydi")
def liste_aktarim_kaydi(veri: ListeAktarimModeli, kullanici_id: int = Depends(mevcut_kullanici_id)):
    izin_adi, tablo = LISTE_AKTARIM_HEDEFLERI[veri.liste]
    izin_adlari = list(izin_adi) if isinstance(izin_adi, (tuple, list)) else [izin_adi]
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT ri.izin_var FROM kullanicilar k
            JOIN rol_izinleri ri ON k.rol_id = ri.rol_id
            JOIN izinler i ON ri.izin_id = i.izin_id
            WHERE k.kullanici_id = %s AND i.izin_adi = ANY(%s) AND ri.izin_var = 1
            LIMIT 1;
            """, (kullanici_id, izin_adlari),
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=403, detail="Bu işlem için yetkiniz bulunmuyor.")
        denetim_kaydi_olustur(
            VT_AYARLARI, olay_turu="EXPORT", kullanici_id=kullanici_id, hedef_tablo=tablo,
            ayrinti={"liste": veri.liste, "satir_sayisi": veri.satir_sayisi, **({"bicim": "PDF"} if veri.bicim == "PDF" else {})},
        )
        return {"durum": "basarili"}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()
