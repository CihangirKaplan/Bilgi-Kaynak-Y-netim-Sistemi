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


from server.ortak_sabitler import ETKIN_CIHAZ_DURUMU_SQL, OGRENCI_TUR_ETIKETLERI
from server.ortak_yardimcilar import plan_kalibrasyon_mu, psikolog_rolu_mu
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

# Cihaz odası = aktif ve AKTİF bir psikologa atanmamış oda. Psikologlara atanan görüşme odaları cihaz rezervasyonuna kapalıdır;
# pasif psikolog odayı tutmaz (atama kaydı kalmış olsa bile), yani oda cihaz rezervasyonuna açılır.
CIHAZ_ODALARI_SORGUSU = (
    "SELECT o.oda_id, o.oda_adi FROM odalar o WHERE o.aktif_mi = TRUE "
    "AND NOT EXISTS (SELECT 1 FROM psikolog_odalar po JOIN kullanicilar k ON k.kullanici_id = po.kullanici_id "
    "JOIN roller r ON r.rol_id = k.rol_id "
    "WHERE po.oda_id = o.oda_id AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG') ORDER BY o.oda_adi"
)


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
# CİHAZ & REZERVASYON MODÜLÜ
# ==========================================
@app.post("/api/cihazlar", status_code=201)
def cihaz_ekle(cihaz: CihazOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_EKLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Envanter kodu büyük/küçük harf ayırt etmeden benzersiz olmalı (EEG-01 ile eeg-01 aynı cihazdır).
        cursor.execute("SELECT 1 FROM cihazlar WHERE lower(envanter_kodu) = lower(%s) OR (%s IS NOT NULL AND seri_no = %s);", (cihaz.envanter_kodu, cihaz.seri_no, cihaz.seri_no))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Bu envanter kodu veya seri no zaten kullanımda.")

        cursor.execute(
            "INSERT INTO cihazlar (envanter_kodu, cihaz_adi, marka_model, seri_no, durum) VALUES (%s, %s, %s, %s, %s) RETURNING cihaz_id;",
            (cihaz.envanter_kodu, cihaz.cihaz_adi, cihaz.marka_model, cihaz.seri_no, cihaz.durum.value)
        )
        cihaz_id = cursor.fetchone()[0]
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="cihazlar",
            hedef_kayit_id=cihaz_id,
            mevcut_cursor=cursor
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Cihaz başarıyla eklendi.", "cihaz_id": cihaz_id}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/cihazlar/{cihaz_id}")
def cihaz_guncelle(
    cihaz_id: int,
    guncelleme: CihazGuncelleModeli,
    kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        degisiklikler = guncelleme.model_dump(exclude_unset=True)

        if not degisiklikler:
            raise HTTPException(
                status_code=422,
                detail="Güncellenecek alan bulunamadı."
            )

        if "durum" in degisiklikler and hasattr(degisiklikler["durum"], "value"):
            degisiklikler["durum"] = degisiklikler["durum"].value

        # Mevcut cihaz durumunu oku ve satırı kilitle.
        cursor.execute(
            "SELECT durum FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;",
            (cihaz_id,)
        )
        kayit = cursor.fetchone()

        if kayit is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        eski_durum = kayit[0]

        # Açık arızası olan cihazın durumu elle değiştirilemez: etkin durum zaten arıza kaydından "Arızalı" çıkar ve elle girilen değer
        # bir şeyi değiştirmeden başarılı görünürdü. Kullanım dışına alma (cihaz hizmetten çıkarılıyor) her zaman yapılabilir.
        yeni_durum = degisiklikler.get("durum")
        if yeni_durum is not None and yeni_durum != eski_durum and yeni_durum != "Kullanim_Disi" and cihazin_acik_arizasi_var_mi(cursor, cihaz_id):
            raise HTTPException(
                status_code=409,
                detail="Bu cihazın çözülmemiş arıza kaydı var; durumu elle değiştirilemez. "
                       "Önce Arıza Kayıtları sayfasından arızayı çözüldü olarak işaretleyin.",
            )

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(
            f"UPDATE cihazlar SET {alanlar} WHERE cihaz_id = %s RETURNING cihaz_id;",
            (*degerler, cihaz_id)
        )

        # Cihazın diğer bilgilerinin güncellenmesi.
        if any(alan != "durum" for alan in degisiklikler):
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="UPDATE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=cihaz_id,
                mevcut_cursor=cursor
            )

        # Cihaz durumu gerçekten değiştiyse ayrıca audit kaydı oluştur.
        if "durum" in degisiklikler and eski_durum != degisiklikler["durum"]:
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=cihaz_id,
                mevcut_cursor=cursor
            )

        conn.commit()

        return {"durum": "basarili", "mesaj": "Cihaz güncellendi."}

    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(status_code=409, detail="Bu seri no başka bir cihazda kullanımda.")

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()



def cihazin_acik_arizasi_var_mi(cursor, cihaz_id) -> bool:
    """Cihazın çözülmemiş (açık) arıza kaydı var mı? Cihaz durumunu elle değiştirmeden önce denetlenir."""
    cursor.execute("SELECT EXISTS (SELECT 1 FROM cihaz_arizalari WHERE cihaz_id = %s AND cozuldu_mu IS NOT TRUE);", (cihaz_id,))
    return bool(cursor.fetchone()[0])



@app.get("/api/cihazlar")
def cihazlari_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_UYGUNLUK_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.cihaz_id, c.envanter_kodu, c.cihaz_adi, c.marka_model, c.seri_no, c.durum, c.kayit_tarihi, "
            + ETKIN_CIHAZ_DURUMU_SQL + " AS etkin_durum FROM cihazlar c ORDER BY c.cihaz_id;"
        )
        kayitlar = cursor.fetchall()
        return [{"cihaz_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2], "marka_model": k[3], "seri_no": k[4], "durum": k[5], "kayit_tarihi": k[6],
                 "etkin_durum": k[7] if len(k) > 7 else k[5]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

GECMIS_OLAY_SINIRI = 300             # her tür için en fazla bu kadar en yeni kayıt döner (özet sayıları sınırsızdır)


def _gun_metni(deger):
    """date/datetime -> 'gg.aa.yyyy' (boşsa '—')."""
    return deger.strftime("%d.%m.%Y") if hasattr(deger, "strftime") else "—"


def _iso(deger):
    return deger.isoformat() if hasattr(deger, "isoformat") else (str(deger) if deger else None)


@app.get("/api/cihazlar/{cihaz_id}/gecmis")
def cihaz_gecmisi_getir(cihaz_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    """Bir cihazın yaşam döngüsü: bakım, kalibrasyon, arıza ve rezervasyon kayıtları tek zaman çizgisinde (en yeni önce) ve özet sayılar."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT c.cihaz_id, c.envanter_kodu, c.cihaz_adi, c.marka_model, c.seri_no, c.durum, c.kayit_tarihi, "
            + ETKIN_CIHAZ_DURUMU_SQL + " FROM cihazlar c WHERE c.cihaz_id = %s;", (cihaz_id,))
        c = cursor.fetchone()
        if c is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        cihaz = {"cihaz_id": c[0], "envanter_kodu": c[1], "cihaz_adi": c[2], "marka_model": c[3], "seri_no": c[4], "durum": c[5],
                 "kayit_tarihi": _iso(c[6]), "etkin_durum": c[7]}

        olaylar = []
        cursor.execute(
            """
            SELECT bakim_id, COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date), COALESCE(bakim_bitis_tarihi, bakim_tarihi::date),
                   yapilan_islem, bakim_yapan_kisi, maliyet, sonraki_bakim_tarihi
            FROM cihaz_bakimlari WHERE cihaz_id = %s
            ORDER BY COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date) DESC, bakim_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            ayrinti = [f"Yapan: {k[4] or '—'}"]
            if k[5] is not None:
                ayrinti.append(f"Maliyet: {float(k[5]):,.2f} ₺".replace(",", "X").replace(".", ",").replace("X", "."))
            if k[6]:
                ayrinti.append(f"Sonraki bakım: {_gun_metni(k[6])}")
            olaylar.append({"tur": "Bakım", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]), "baslik": k[3] or "Bakım",
                            "ayrinti": " · ".join(ayrinti), "durum": None})

        cursor.execute(
            """
            SELECT kalibrasyon_id, COALESCE(kalibrasyon_baslangic_tarihi, islem_tarihi::date), COALESCE(kalibrasyon_bitis_tarihi, islem_tarihi::date),
                   sertifika_no, kalibrasyon_yapan_kurum, gecerlilik_tarihi
            FROM cihaz_kalibrasyonlari WHERE cihaz_id = %s
            ORDER BY COALESCE(kalibrasyon_baslangic_tarihi, islem_tarihi::date) DESC, kalibrasyon_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            olaylar.append({"tur": "Kalibrasyon", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]),
                            "baslik": f"Sertifika {k[3] or '—'}",
                            "ayrinti": f"Kurum: {k[4] or '—'} · Geçerlilik: {_gun_metni(k[5])}", "durum": None})

        cursor.execute(
            """
            SELECT ariza_id, bildirim_tarihi, cozum_tarihi, ariza_baslik, ariza_aciklamasi, aciliyet, cozuldu_mu, bildiren_personel, cozum_notu
            FROM cihaz_arizalari WHERE cihaz_id = %s ORDER BY bildirim_tarihi DESC, ariza_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            ayrinti = [f"Aciliyet: {k[5] or '—'}", f"Bildiren: {k[7] or '—'}"]
            if k[6] and k[8]:
                ayrinti.append(f"Çözüm: {k[8]}")
            olaylar.append({"tur": "Arıza", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]) if k[6] else None,
                            "baslik": k[3] or "Arıza", "ayrinti": " · ".join(ayrinti), "durum": "Çözüldü" if k[6] else "Açık"})

        cursor.execute(
            """
            SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, r.iptal_edildi_mi, b.bolum_adi, o.oda_adi, r.proje_turu,
                   r.proje_adi_aciklamasi, ky.kullanici_adi
            FROM cihaz_rezervasyonlari r
            LEFT JOIN bolumler b ON b.bolum_id = r.bolum_id
            LEFT JOIN odalar o ON o.oda_id = r.kullanilacak_oda_id
            LEFT JOIN kullanicilar ky ON ky.personel_id = r.rezervasyonu_yapan_personel_id
            WHERE r.cihaz_id = %s ORDER BY r.baslangic_zamani DESC, r.rezervasyon_id DESC LIMIT %s;
            """, (cihaz_id, GECMIS_OLAY_SINIRI))
        for k in cursor.fetchall():
            ayrinti = [f"Oda: {k[5] or '—'}"]
            if k[6]:
                ayrinti.append(f"Proje: {k[6]}")
            if k[8]:
                ayrinti.append(f"Yapan: {k[8]}")
            if k[7]:
                ayrinti.append(str(k[7]))
            olaylar.append({"tur": "Rezervasyon", "kayit_id": k[0], "baslangic": _iso(k[1]), "bitis": _iso(k[2]),
                            "baslik": k[4] or "Rezervasyon", "ayrinti": " · ".join(ayrinti),
                            "durum": rezervasyon_gorunen_durumu(k[3], k[2])})

        olaylar.sort(key=lambda o: (o["baslangic"] or ""), reverse=True)

        cursor.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM cihaz_bakimlari WHERE cihaz_id = %(c)s),
              (SELECT COALESCE(SUM(maliyet), 0) FROM cihaz_bakimlari WHERE cihaz_id = %(c)s),
              (SELECT COUNT(*) FROM cihaz_kalibrasyonlari WHERE cihaz_id = %(c)s),
              (SELECT MAX(gecerlilik_tarihi) FROM cihaz_kalibrasyonlari WHERE cihaz_id = %(c)s),
              (SELECT COUNT(*) FROM cihaz_arizalari WHERE cihaz_id = %(c)s),
              (SELECT COUNT(*) FROM cihaz_arizalari WHERE cihaz_id = %(c)s AND cozuldu_mu = FALSE),
              (SELECT COUNT(*) FROM cihaz_rezervasyonlari WHERE cihaz_id = %(c)s AND iptal_edildi_mi = FALSE),
              (SELECT COALESCE(SUM(EXTRACT(EPOCH FROM (bitis_zamani - baslangic_zamani)) / 3600), 0)
                 FROM cihaz_rezervasyonlari WHERE cihaz_id = %(c)s AND iptal_edildi_mi = FALSE)
            """, {"c": cihaz_id})
        o = cursor.fetchone()
        ozet = {"bakim_sayisi": o[0], "toplam_bakim_maliyeti": float(o[1] or 0), "kalibrasyon_sayisi": o[2],
                "kalibrasyon_gecerlilik": _iso(o[3]), "ariza_sayisi": o[4], "acik_ariza_sayisi": o[5],
                "rezervasyon_sayisi": o[6], "rezervasyon_saati": round(float(o[7] or 0), 1)}
        return {"cihaz": cihaz, "ozet": ozet, "olaylar": olaylar, "sinir": GECMIS_OLAY_SINIRI}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.get("/api/cihazlar/{cihaz_id}")
def cihaz_detayi_getir(cihaz_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_UYGUNLUK_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, seri_no, durum, kayit_tarihi FROM cihazlar WHERE cihaz_id = %s;", (cihaz_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        return {"cihaz_id": kayit[0], "envanter_kodu": kayit[1], "cihaz_adi": kayit[2], "marka_model": kayit[3], "seri_no": kayit[4], "durum": kayit[5], "kayit_tarihi": kayit[6]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()



def rezervasyon_uygunlugunu_denetle(cursor, rez, haric_rezervasyon_id=None):
    """Cihaz rezervasyonunun (yeni ya da düzenlenen) uygun olup olmadığını denetler; sorun varsa HTTPException (403/409/422) fırlatır.

    `rez`: cihaz_id, kullanilacak_oda_id, bolum_id, baslangic_zamani, bitis_zamani alanlarına sahip nesne.
    `haric_rezervasyon_id`: düzenlemede rezervasyonun KENDİSİ çakışma sayılmasın diye çakışma sorgularından çıkarılır."""
    haric_sql = " AND r.rezervasyon_id <> %s" if haric_rezervasyon_id is not None else ""
    haric_param = (haric_rezervasyon_id,) if haric_rezervasyon_id is not None else ()
    # Çözülmemiş arızası olan cihaz, kayıtlı durum sütunu ne derse desin "Arızalı" sayılır (tek doğruluk kaynağı: arıza kaydı).
    cursor.execute(
        "SELECT CASE WHEN durum::text <> 'Kullanim_Disi' AND EXISTS ("
        "SELECT 1 FROM cihaz_arizalari a WHERE a.cihaz_id = cihazlar.cihaz_id AND a.cozuldu_mu IS NOT TRUE) "
        "THEN 'Arizali' ELSE durum::text END FROM cihazlar WHERE cihaz_id = %s;", (rez.cihaz_id,))
    cihaz = cursor.fetchone()
    if cihaz is None:
        raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
    if cihaz[0] not in ["Kullanima_Hazir", "Rezerve"]:
        raise HTTPException(status_code=403, detail=f"Cihaz şu anda {cihaz[0]} durumunda olduğu için rezerve edilemez!")

    # Bakım/kalibrasyon kaydı cihaz durumunu değiştirmediğinden, seçilen saat aralığı
    # planlı bir bakım veya kalibrasyonla kesişiyorsa da rezervasyon reddedilir.
    # Bakım/kalibrasyon günleri başlangıç ve bitiş dahil tam gün sayılır.
    cursor.execute(
        """
        SELECT tur, baslangic, bitis FROM (
            SELECT 'Bakım' AS tur,
                   COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date) AS baslangic,
                   COALESCE(bakim_bitis_tarihi, bakim_tarihi::date) AS bitis
            FROM cihaz_bakimlari
            WHERE cihaz_id = %s
            UNION ALL
            SELECT 'Kalibrasyon', kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi
            FROM cihaz_kalibrasyonlari
            WHERE cihaz_id = %s
        ) planlar
        WHERE baslangic IS NOT NULL AND bitis IS NOT NULL
          AND baslangic < %s AND bitis + 1 > %s
        ORDER BY baslangic
        LIMIT 1;
        """,
        (rez.cihaz_id, rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani),
    )
    plan = cursor.fetchone()
    if plan is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cihaz {plan[1].strftime('%d.%m.%Y')} - {plan[2].strftime('%d.%m.%Y')} "
                f"tarihleri arasında {plan[0].lower()} planında olduğu için "
                "seçilen saat aralığında rezerve edilemez."
            ),
        )

    cursor.execute("SELECT 1 FROM cihaz_rezervasyonlari WHERE cihaz_id = %s AND iptal_edildi_mi = FALSE AND baslangic_zamani < %s AND bitis_zamani > %s" + haric_sql.replace("r.", "") + " LIMIT 1;", (rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani, *haric_param))
    if cursor.fetchone():
        cursor.execute(
            """
            SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, COALESCE(k.kullanici_adi, '-')
            FROM cihaz_rezervasyonlari r
            LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
            LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            WHERE r.cihaz_id = %s AND r.iptal_edildi_mi = FALSE
              AND r.baslangic_zamani < %s AND r.bitis_zamani > %s""" + haric_sql + """
            ORDER BY r.baslangic_zamani;
            """,
            (rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani, *haric_param),
        )
        raise HTTPException(
            status_code=409,
            detail=rezervasyon_cakisma_detayi(
                "Cihaz seçilen saat aralığında zaten başka bir iş için rezerve edilmiş.",
                cursor.fetchall(),
            ),
        )

    if rez.kullanilacak_oda_id is not None:
        # Oda uygunluğu, aynı transaction kilidi altında kontrol edilmeli.
        oda_kilidini_al(cursor, rez.kullanilacak_oda_id)
        cursor.execute("SELECT 1 FROM (" + CIHAZ_ODALARI_SORGUSU + ") d WHERE d.oda_id = %s;", (rez.kullanilacak_oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Seçilen oda cihaz rezervasyonu için uygun değil (psikologa atanmış ya da aktif değil).")

    if rez.bolum_id is not None:
        cursor.execute("SELECT 1 FROM bolumler WHERE bolum_id = %s AND aktif_mi IS NOT FALSE;", (rez.bolum_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Bölüm bulunamadı veya aktif değil.")

    if rez.kullanilacak_oda_id is not None:
        # Oda kilidi, uygunluk kontrolünden önce alındı.
        cakisma = oda_cakismasi_bul(
            cursor,
            rez.kullanilacak_oda_id,
            rez.baslangic_zamani,
            rez.bitis_zamani,
            haric_cihaz_rezervasyon_id=haric_rezervasyon_id,
        )
        if cakisma:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Oda bu saatlerde dolu "
                    f"(çakışan kayıt: {cakisma})."
                ),
            )

        # Aynı oda aynı saatte yalnızca tek rezervasyona verilir (başka bir CİHAZ için de olsa).
        cursor.execute(
            """
            SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, COALESCE(k.kullanici_adi, '-')
            FROM cihaz_rezervasyonlari r
            LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
            LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            WHERE r.kullanilacak_oda_id = %s AND r.iptal_edildi_mi = FALSE
              AND r.baslangic_zamani < %s AND r.bitis_zamani > %s""" + haric_sql + """
            ORDER BY r.baslangic_zamani;
            """,
            (rez.kullanilacak_oda_id, rez.bitis_zamani, rez.baslangic_zamani, *haric_param),
        )
        oda_cakismalari = cursor.fetchall()
        if oda_cakismalari:
            raise HTTPException(
                status_code=409,
                detail=rezervasyon_cakisma_detayi(
                    "Oda seçilen saat aralığında başka bir cihaz rezervasyonu için ayrılmış.",
                    oda_cakismalari,
                ),
            )


@app.post("/api/rezervasyonlar", status_code=201)
def cihaz_rezervasyonu_yap(rez: RezervasyonOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    if rez.baslangic_zamani >= rez.bitis_zamani:
        raise HTTPException(status_code=422, detail="Bitiş zamanı, başlangıçtan sonra olmalıdır.")
    # Geçmiş bir zamana yeni cihaz rezervasyonu oluşturulamaz (mesai kuralından önce söylenir: saatten bağımsız, açık mesaj).
    if rez.baslangic_zamani < datetime.now(rez.baslangic_zamani.tzinfo):
        raise HTTPException(
            status_code=422,
            detail="Rezervasyon başlangıç zamanı geçmişte olamaz."
        )
    zaman_sorunu = rezervasyon_zaman_sorunu(rez.baslangic_zamani, rez.bitis_zamani)
    if zaman_sorunu:
        raise HTTPException(status_code=422, detail=zaman_sorunu)

    maksimum_deneme = 3
    for deneme in range(maksimum_deneme):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            rezervasyon_uygunlugunu_denetle(cursor, rez)

            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici_id,))
            pers = cursor.fetchone()
            personel_id = pers[0] if pers else None

            cursor.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, bolum_id, rezervasyonu_yapan_personel_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani, proje_turu, proje_adi_aciklamasi) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING rezervasyon_id;", (rez.cihaz_id, rez.bolum_id, personel_id, rez.kullanilacak_oda_id, rez.baslangic_zamani, rez.bitis_zamani, rez.proje_turu, rez.proje_adi_aciklamasi))
            rez_id = cursor.fetchone()[0]

            cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "cihaz_rezervasyonlari", rez_id))
            conn.commit()
            return {"durum": "basarili", "mesaj": "Rezervasyon başarıyla oluşturuldu.", "rezervasyon_id": rez_id}
        except DeadlockDetected:
            if conn is not None: conn.rollback()
            if deneme == maksimum_deneme - 1:
                raise HTTPException(status_code=503, detail="Rezervasyon işlemi eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
            time.sleep(0.1 * (deneme + 1))
        except ExclusionViolation as hata:
            if conn is not None: conn.rollback()
            if getattr(getattr(hata, "diag", None), "constraint_name", None) == "cihaz_rezervasyon_oda_cakisma":
                raise HTTPException(status_code=409, detail="Oda seçilen saat aralığında başka bir cihaz rezervasyonu için ayrılmış.")
            raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten rezerve edilmiş.")
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()

# Rezervasyonu değiştirme/iptal yetkisi: rezervasyonu yapan kişi YA DA cihaz envanterini yöneten (yönetici) rol.
# SQL parçası `r` takma adını bekler ve iki kez kullanıcı kimliği (sırayla) ister.
REZERVASYON_YONETIM_YETKISI_SQL = """(
    r.rezervasyonu_yapan_personel_id = (SELECT personel_id FROM kullanicilar WHERE kullanici_id = %s)
    OR EXISTS (
        SELECT 1 FROM kullanicilar ky
        JOIN rol_izinleri ri ON ri.rol_id = ky.rol_id
        JOIN izinler iz ON iz.izin_id = ri.izin_id
        WHERE ky.kullanici_id = %s AND iz.izin_adi = 'CIHAZ_ENVANTER_YONET' AND ri.izin_var = 1
    )
)"""
REZERVASYON_YETKI_MESAJI = "Bu rezervasyonu yalnızca oluşturan kişi ya da cihaz yöneticisi değiştirebilir."


@app.patch("/api/rezervasyonlar/{rezervasyon_id}/iptal")
def rezervasyon_iptal(rezervasyon_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Yalnızca iptal edilmemiş, süresi dolmamış VE (oluşturan kişi ya da yönetici için) rezervasyon iptal edilir
        # (biten rezervasyonun geçmiş kullanım kaydı ve raporlardaki saati değişmesin).
        cursor.execute(
            "UPDATE cihaz_rezervasyonlari AS r SET iptal_edildi_mi = TRUE WHERE r.rezervasyon_id = %s AND r.iptal_edildi_mi = FALSE "
            "AND r.bitis_zamani > CURRENT_TIMESTAMP AND " + REZERVASYON_YONETIM_YETKISI_SQL + " RETURNING r.rezervasyon_id;",
            (rezervasyon_id, kullanici_id, kullanici_id))
        if cursor.fetchone() is None:
            # Nedeni kullanıcıya söyle: hiç yok mu, zaten iptal mi, süresi mi dolmuş, yoksa yetkisi mi yok?
            cursor.execute(
                "SELECT r.iptal_edildi_mi, r.bitis_zamani <= CURRENT_TIMESTAMP, " + REZERVASYON_YONETIM_YETKISI_SQL +
                " FROM cihaz_rezervasyonlari r WHERE r.rezervasyon_id = %s;", (kullanici_id, kullanici_id, rezervasyon_id))
            mevcut = cursor.fetchone()
            if mevcut is None:
                raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı.")
            if mevcut[0]:
                raise HTTPException(status_code=409, detail="Bu rezervasyon zaten iptal edilmiş.")
            if mevcut[1]:
                raise HTTPException(status_code=409, detail="Süresi dolmuş (tamamlanmış) rezervasyon iptal edilemez.")
            raise HTTPException(status_code=403, detail=REZERVASYON_YETKI_MESAJI)
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CANCEL",
            kullanici_id=kullanici_id,
            hedef_tablo="cihaz_rezervasyonlari",
            hedef_kayit_id=rezervasyon_id,
            mevcut_cursor=cursor
        )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Rezervasyon iptal edildi."}
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/rezervasyonlar/{rezervasyon_id}")
def rezervasyon_guncelle(rezervasyon_id: int, rez: RezervasyonGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    """Rezervasyonu düzenler (cihaz değişmez). Yalnızca oluşturan kişi ya da cihaz yöneticisi; iptal edilmiş/bitmiş rezervasyon düzenlenemez.
    Başlamış rezervasyonda başlangıç saati ve oda değişmez. Saat/oda değişirse yeni aralık için tüm uygunluk kuralları yeniden denetlenir
    (rezervasyonun kendisi çakışma sayılmaz); yalnızca açıklama/proje/bölüm değişirse cihaz durumu ya da bakım planı engel olmaz."""
    maksimum_deneme = 3
    for deneme in range(maksimum_deneme):
        conn = None
        cursor = None
        try:
            conn = vt_baglan(VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT r.cihaz_id, r.iptal_edildi_mi, r.baslangic_zamani, r.bitis_zamani, r.kullanilacak_oda_id, " + REZERVASYON_YONETIM_YETKISI_SQL +
                " FROM cihaz_rezervasyonlari r WHERE r.rezervasyon_id = %s FOR UPDATE OF r;", (kullanici_id, kullanici_id, rezervasyon_id))
            mevcut = cursor.fetchone()
            if mevcut is None:
                raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı.")
            cihaz_id, iptal, mevcut_bas, mevcut_bit, mevcut_oda, yetkili = mevcut
            if iptal:
                raise HTTPException(status_code=409, detail="İptal edilmiş rezervasyon düzenlenemez.")
            simdi = datetime.now(rez.baslangic_zamani.tzinfo)
            if mevcut_bit <= simdi.replace(tzinfo=None):
                raise HTTPException(status_code=409, detail="Süresi dolmuş (tamamlanmış) rezervasyon düzenlenemez.")
            if not yetkili:
                raise HTTPException(status_code=403, detail=REZERVASYON_YETKI_MESAJI)

            bas, bit = rez.baslangic_zamani.replace(tzinfo=None), rez.bitis_zamani.replace(tzinfo=None)
            zaman_oda_degisti = (bas, bit, rez.kullanilacak_oda_id) != (mevcut_bas, mevcut_bit, mevcut_oda)
            basladi = mevcut_bas <= simdi.replace(tzinfo=None)
            if basladi:
                if bas != mevcut_bas or rez.kullanilacak_oda_id != mevcut_oda:
                    raise HTTPException(status_code=409, detail="Başlamış rezervasyonun başlangıç saati ve odası değiştirilemez; yalnızca bitiş saati, bölüm ve proje bilgileri düzenlenebilir.")
                if bit <= simdi.replace(tzinfo=None):
                    raise HTTPException(status_code=422, detail="Bitiş zamanı şu andan sonra olmalıdır.")
            elif bas < simdi.replace(tzinfo=None):
                raise HTTPException(status_code=422, detail="Rezervasyon başlangıç zamanı geçmişte olamaz.")

            if (bas, bit) != (mevcut_bas, mevcut_bit):
                # Saatler değişiyorsa mesai ve süre kuralı yeniden uygulanır (yalnızca açıklama/bölüm değişirse eski kayıtlar engellenmez).
                zaman_sorunu = rezervasyon_zaman_sorunu(rez.baslangic_zamani, rez.bitis_zamani)
                if zaman_sorunu:
                    raise HTTPException(status_code=422, detail=zaman_sorunu)

            if zaman_oda_degisti:
                from types import SimpleNamespace
                rezervasyon_uygunlugunu_denetle(
                    cursor,
                    SimpleNamespace(cihaz_id=cihaz_id, kullanilacak_oda_id=rez.kullanilacak_oda_id, bolum_id=rez.bolum_id,
                                    baslangic_zamani=rez.baslangic_zamani, bitis_zamani=rez.bitis_zamani),
                    haric_rezervasyon_id=rezervasyon_id,
                )
            elif rez.bolum_id is not None:
                cursor.execute("SELECT 1 FROM bolumler WHERE bolum_id = %s AND aktif_mi IS NOT FALSE;", (rez.bolum_id,))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=422, detail="Bölüm bulunamadı veya aktif değil.")

            cursor.execute(
                "UPDATE cihaz_rezervasyonlari SET bolum_id = %s, kullanilacak_oda_id = %s, baslangic_zamani = %s, bitis_zamani = %s, "
                "proje_turu = %s, proje_adi_aciklamasi = %s WHERE rezervasyon_id = %s;",
                (rez.bolum_id, rez.kullanilacak_oda_id, rez.baslangic_zamani, rez.bitis_zamani, rez.proje_turu, rez.proje_adi_aciklamasi, rezervasyon_id),
            )
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_rezervasyonlari",
                                  hedef_kayit_id=rezervasyon_id, mevcut_cursor=cursor)
            conn.commit()
            return {"durum": "basarili", "mesaj": "Rezervasyon güncellendi.", "rezervasyon_id": rezervasyon_id}
        except DeadlockDetected:
            if conn is not None: conn.rollback()
            if deneme == maksimum_deneme - 1:
                raise HTTPException(status_code=503, detail="Rezervasyon işlemi eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
            time.sleep(0.1 * (deneme + 1))
        except ExclusionViolation as hata:
            if conn is not None: conn.rollback()
            if getattr(getattr(hata, "diag", None), "constraint_name", None) == "cihaz_rezervasyon_oda_cakisma":
                raise HTTPException(status_code=409, detail="Oda seçilen saat aralığında başka bir cihaz rezervasyonu için ayrılmış.")
            raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten rezerve edilmiş.")
        except Exception:
            if conn is not None: conn.rollback()
            raise
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()


def rezervasyon_gorunen_durumu(iptal_edildi_mi, bitis_zamani, simdi=None):
    """Rezervasyonun gorunen durumunu hesaplar; veritabanini degistirmez."""
    if iptal_edildi_mi:
        return "İptal Edildi"

    if bitis_zamani is None:
        return "Aktif"

    if simdi is None:
        simdi = datetime.now(bitis_zamani.tzinfo)

    if bitis_zamani <= simdi:
        return "Tamamlandı"

    return "Aktif"


# Zamanla büyüyen kayıt listeleri (rezervasyon, arıza, bakım, kalibrasyon) en yeni bu kadar kaydı döndürür. Normal kullanımda yıllarca sınıra
# ulaşılmaz; ulaşılırsa gerçek toplam X-Toplam-Kayit başlığında gönderilir ve ekran "en yeni N / toplam M" der (randevu listesindeki gibi).
LISTE_UST_SINIRI = 5000


def liste_siniri_coz(limit) -> int:
    """İstemcinin istediği kayıt sayısı (1..LISTE_UST_SINIRI); verilmediyse üst sınır. Uç fonksiyonları doğrudan çağrıldığında
    (testler) varsayılan olarak bir Query nesnesi gelir; o da "verilmedi" sayılır."""
    return limit if isinstance(limit, int) and not isinstance(limit, bool) and 1 <= limit <= LISTE_UST_SINIRI else LISTE_UST_SINIRI


def liste_toplamini_bildir(cursor, response, gelen_satir_sayisi: int, sayim_sql: str, sinir: int | None = None) -> None:
    """Liste istenen sınıra (verilmediyse üst sınıra) ulaştıysa gerçek toplamı X-Toplam-Kayit başlığına yazar; ulaşmadıysa ek sorgu yapmaz."""
    if response is None or gelen_satir_sayisi < (LISTE_UST_SINIRI if sinir is None else sinir):
        return
    cursor.execute(sayim_sql)
    response.headers["X-Toplam-Kayit"] = str(cursor.fetchone()[0])


@app.get("/api/rezervasyonlar")
def rezervasyonlari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rezervasyon_id, c.envanter_kodu, c.cihaz_adi, r.baslangic_zamani, r.bitis_zamani, r.iptal_edildi_mi, o.oda_adi, r.proje_turu, r.proje_adi_aciklamasi, r.bolum_id, b.bolum_adi, "
                       "ky.kullanici_adi, " + REZERVASYON_YONETIM_YETKISI_SQL + ", r.cihaz_id, r.kullanilacak_oda_id "
                       "FROM cihaz_rezervasyonlari r JOIN cihazlar c ON r.cihaz_id = c.cihaz_id LEFT JOIN odalar o ON r.kullanilacak_oda_id = o.oda_id LEFT JOIN bolumler b ON r.bolum_id = b.bolum_id "
                       "LEFT JOIN kullanicilar ky ON ky.personel_id = r.rezervasyonu_yapan_personel_id ORDER BY r.baslangic_zamani DESC LIMIT %s;", (kullanici_id, kullanici_id, sinir))
        kayitlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(kayitlar), "SELECT COUNT(*) FROM cihaz_rezervasyonlari;", sinir)
        return [{"rezervasyon_id": k[0], "cihaz_id": f"{k[1]} - {k[2]}", "baslangic_zamani": k[3].isoformat() if hasattr(k[3], 'isoformat') else str(k[3]), "bitis_zamani": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]), "durum": rezervasyon_gorunen_durumu(k[5], k[4]), "envanter_kodu": k[1], "cihaz_adi": k[2], "oda_adi": k[6], "proje_turu": k[7], "proje_adi_aciklamasi": k[8], "bolum_id": k[9], "bolum_adi": k[10],
                 "rezerve_eden": k[11] if len(k) > 11 else None,
                 "yonetebilir": bool(k[12]) if len(k) > 12 else False,
                 "cihaz_numarasi": k[13] if len(k) > 13 else None,
                 "oda_id": k[14] if len(k) > 14 else None} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/bolumler")
def bolumleri_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    """Rezervasyon formundaki bölüm listesi (yalnızca aktif bölümler)."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT bolum_id, bolum_adi, sorumlu_ad_soyad FROM bolumler WHERE aktif_mi IS NOT FALSE ORDER BY bolum_adi;")
        return [{"bolum_id": k[0], "bolum_adi": k[1], "sorumlu_ad_soyad": k[2]} for k in cursor.fetchall()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/bolumler", status_code=201)
def bolum_olustur(bolum: BolumOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO bolumler (bolum_adi, sorumlu_ad_soyad, iletisim_bilgisi, aktif_mi) VALUES (%s, %s, %s, TRUE) RETURNING bolum_id;", (bolum.bolum_adi, bolum.sorumlu_ad_soyad, bolum.iletisim_bilgisi))
        bolum_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "bolumler", bolum_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Bölüm eklendi.", "bolum_id": bolum_id, "bolum_adi": bolum.bolum_adi}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu isimde bir bölüm zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

def proje_turu_anahtari(ad):
    """Proje türü karşılaştırma anahtarı: Türkçe büyük/küçük harf farkı (İ/i, I/ı) ve kenar boşlukları yok sayılır."""
    return str(ad).strip().replace("İ", "i").replace("I", "ı").lower()


@app.get("/api/proje-turleri")
def proje_turlerini_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    """Rezervasyon formundaki proje türü listesi."""
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT proje_turu_id, ad FROM proje_turleri WHERE aktif_mi ORDER BY ad;")
        return [{"proje_turu_id": k[0], "ad": k[1]} for k in cursor.fetchall()]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/proje-turleri", status_code=201)
def proje_turu_olustur(tur: ProjeTuruOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT ad FROM proje_turleri;")
        if proje_turu_anahtari(tur.ad) in {proje_turu_anahtari(k[0]) for k in cursor.fetchall()}:     # büyük/küçük harf (İ/ı dahil) farkı yok sayılır
            raise HTTPException(status_code=409, detail="Bu proje türü zaten mevcut.")
        cursor.execute("INSERT INTO proje_turleri (ad) VALUES (%s) RETURNING proje_turu_id;", (tur.ad,))
        tur_id = cursor.fetchone()[0]
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "proje_turleri", tur_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Proje türü eklendi.", "proje_turu_id": tur_id, "ad": tur.ad}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu proje türü zaten mevcut.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# ARIZA YÖNETİMİ MODÜLÜ
# ==========================================

# Arıza açılınca cihazın "Arızalı" olabileceği durumlar. Bakımda, kalibrasyonda veya kullanım
# dışı bir cihazın durumu arıza kaydıyla ezilmez (arıza kaydı yine de tutulur).
ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR = ("Kullanima_Hazir", "Rezerve", "Kullanimda", "Arizali")


def arizadan_sonra_cihaz_durumu(eski_durum, cozuldu_mu, baska_acik_ariza_var):
    """Arıza kaydı açıldığında/çözüldüğünde cihazın yeni durumunu belirler.

    - Çözüldü: cihaz yalnızca "Arızalı" durumdaysa ve başka açık arızası yoksa "Kullanıma Hazır" olur.
      Başka açık arıza varsa ya da cihaz bakımda/kalibrasyonda/kullanım dışıysa durumu korunur.
    - Açık: cihaz "Arızalı" olur; ancak bakımda/kalibrasyonda/kullanım dışı cihazın durumu değişmez.
    """
    if cozuldu_mu:
        if eski_durum == "Arizali" and not baska_acik_ariza_var:
            return "Kullanima_Hazir"
        return eski_durum
    if eski_durum in ARIZA_ILE_ARIZALI_OLABILEN_DURUMLAR:
        return "Arizali"
    return eski_durum


@app.get("/api/arizalar")
def arizalari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int = Depends(izin_kontrol("ARIZA_KAYITLARI_YONET"))):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.ariza_id, c.cihaz_adi, a.ariza_baslik, a.ariza_aciklamasi, a.aciliyet,
                   a.cozuldu_mu, a.bildirim_tarihi, c.envanter_kodu, a.cozum_tarihi, a.cozum_notu, a.cihaz_id
            FROM cihaz_arizalari a
            JOIN cihazlar c ON a.cihaz_id = c.cihaz_id
            ORDER BY a.bildirim_tarihi DESC
            LIMIT %s;
        """, (sinir,))
        satirlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(satirlar), "SELECT COUNT(*) FROM cihaz_arizalari;", sinir)
        return [
            {
                "ariza_id": k[0],
                "cihaz_adi": k[1],
                "ariza_baslik": k[2],
                "ariza_aciklama": k[3],
                "aciliyet": k[4],
                "durum": "Çözüldü" if k[5] else "Açık",
                "bildirim_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                "envanter_kodu": k[7] if len(k) > 7 else None,
                "cozum_tarihi": (k[8].isoformat() if hasattr(k[8], "isoformat") else k[8]) if len(k) > 8 else None,
                "cozum_notu": k[9] if len(k) > 9 else None,
                "cihaz_id": k[10] if len(k) > 10 else None,          # cihaz geçmişine bağlantı için
            }
            for k in satirlar
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/arizalar", status_code=201)
def ariza_bildir(ariza: ArizaBildirimModeli, kullanici_id: int = Depends(izin_kontrol("ARIZA_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 1. Cihaz var mı ve durumu uygun mu kontrolü
        cursor.execute("SELECT durum FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;", (ariza.cihaz_id,))
        cihaz = cursor.fetchone()
        if cihaz is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        # 2. Bildiren personelin adını (kullanıcı adını) bulalım (DB varchar bekliyor)
        cursor.execute("SELECT kullanici_adi FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
        kullanici = cursor.fetchone()
        bildiren_kisi = kullanici[0] if kullanici else f"Kullanıcı-{kullanici_id}"

        # 3. Arıza kaydını ekle (başlık ve aciliyet kendi sütunlarında tutulur)
        cursor.execute("""
            INSERT INTO cihaz_arizalari (cihaz_id, bildiren_personel, ariza_baslik, ariza_aciklamasi, aciliyet,
                                         bildirim_tarihi, cozuldu_mu)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, FALSE) RETURNING ariza_id;
        """, (ariza.cihaz_id, bildiren_kisi, ariza.ariza_baslik.strip(), ariza.ariza_aciklama.strip(), ariza.aciliyet))
        ariza_id = cursor.fetchone()[0]

        # 5. Cihazı 'Arizali' yap; bakımda/kalibrasyonda/kullanım dışı cihazın durumu korunur.
        yeni_durum = arizadan_sonra_cihaz_durumu(cihaz[0], False, True)
        if yeni_durum != cihaz[0]:
            cursor.execute("UPDATE cihazlar SET durum = %s WHERE cihaz_id = %s;", (yeni_durum, ariza.cihaz_id))
        # 6. Denetim (Audit) logları
        # Arıza oluşturma kaydını aynı transaction içinde tut.
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="cihaz_arizalari",
            hedef_kayit_id=ariza_id,
            mevcut_cursor=cursor
        )

        # Cihazın durumu gerçekten değiştiyse ayrıca kaydet.
        if yeni_durum != cihaz[0]:
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=ariza.cihaz_id,
                mevcut_cursor=cursor
            )
        conn.commit()
        if yeni_durum == "Arizali":
            mesaj = "Arıza bildirimi alındı ve cihaz arızalı konuma çekildi."
        else:
            mesaj = f"Arıza bildirimi alındı. Cihaz '{cihaz[0]}' durumunda olduğu için cihaz durumu değiştirilmedi."
        return {"durum": "basarili", "mesaj": mesaj, "ariza_id": ariza_id}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İşlem sırasında bir sunucu hatası oluştu."
        )
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/arizalar/{ariza_id}")
def ariza_guncelle(ariza_id: int, ariza: ArizaGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("ARIZA_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Cihaz IDsini bulalım
        cursor.execute("SELECT cihaz_id FROM cihaz_arizalari WHERE ariza_id = %s FOR UPDATE;", (ariza_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Arıza kaydı bulunamadı.")
        cihaz_id = kayit[0]

        # Çözüldüyse çözüm tarihini anlık at, çözülmediyse NULL (Boş) yap. Çözüm notu: çözüldüyse yazılan not (gönderilmediyse eskisi
        # korunur), yeniden açıldıysa temizlenir.
        cozum_sql = "CURRENT_TIMESTAMP" if ariza.cozuldu_mu else "NULL"
        not_sql = "COALESCE(%s, cozum_notu)" if ariza.cozuldu_mu else "NULL"
        not_parametresi = (ariza.cozum_notu,) if ariza.cozuldu_mu else ()

        # Arıza Tablosunu Güncelle
        cursor.execute(f"""
            UPDATE cihaz_arizalari
            SET ariza_baslik = %s, ariza_aciklamasi = %s, aciliyet = %s,
                cozuldu_mu = %s, cozum_tarihi = {cozum_sql}, cozum_notu = {not_sql}
            WHERE ariza_id = %s;
        """, (ariza.ariza_baslik.strip(), ariza.ariza_aciklama.strip(), ariza.aciliyet, ariza.cozuldu_mu, *not_parametresi, ariza_id))

        # Cihazın mevcut durumunu oku, satırı kilitle ve cihazın BAŞKA açık arızası var mı bak.
        cursor.execute(
            """
            SELECT durum,
                   EXISTS (SELECT 1 FROM cihaz_arizalari
                           WHERE cihaz_id = %s AND cozuldu_mu = FALSE AND ariza_id <> %s)
            FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;
            """,
            (cihaz_id, ariza_id, cihaz_id)
        )
        cihaz_kaydi = cursor.fetchone()

        if cihaz_kaydi is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        eski_cihaz_durum, baska_acik_ariza_var = cihaz_kaydi
        yeni_cihaz_durum = arizadan_sonra_cihaz_durumu(
            eski_cihaz_durum, ariza.cozuldu_mu, baska_acik_ariza_var
        )

        # Arıza güncellemesini audit'e kaydet.
        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="cihaz_arizalari",
            hedef_kayit_id=ariza_id,
            mevcut_cursor=cursor
        )

        # Yalnızca gerçek durum değişikliğinde cihazı güncelle ve audit oluştur.
        if eski_cihaz_durum != yeni_cihaz_durum:
            cursor.execute(
                "UPDATE cihazlar SET durum = %s WHERE cihaz_id = %s;",
                (yeni_cihaz_durum, cihaz_id)
            )

            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=cihaz_id,
                mevcut_cursor=cursor
            )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Arıza başarıyla güncellendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İşlem sırasında bir sunucu hatası oluştu."
        )
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()
# ==========================================
# BAKIM YÖNETİMİ MODÜLÜ (MNT-001, MNT-002)
# ==========================================

# ==========================================
# REZERVASYON ÇAKIŞMASI (bakım/kalibrasyon ve yeni rezervasyon)
# ==========================================
REZERVASYON_CAKISMA_KODU = "REZERVASYON_CAKISMASI"


def rezervasyon_cakisma_detayi(mesaj, kayitlar):
    """409 yanıtı gövdesi: istemci çakışan rezervasyonları tek tek gösterip iptal ettirebilsin."""
    return {
        "kod": REZERVASYON_CAKISMA_KODU,
        "mesaj": mesaj,
        "rezervasyonlar": [
            {
                "rezervasyon_id": k[0],
                "baslangic": k[1].isoformat(),
                "bitis": k[2].isoformat(),
                "rezerve_eden": k[3],
            }
            for k in kayitlar
        ],
    }


def cakisan_rezervasyonlari_denetle(cursor, cihaz_id, baslangic, bitis):
    """Bakım/kalibrasyon tarih aralığıyla (başlangıç ve bitiş günü dahil) kesişen, henüz bitmemiş
    aktif cihaz rezervasyonu varsa 409 + rezervasyon listesi döner.

    Rezervasyonları sunucu kendiliğinden iptal etmez; istemci her birini kullanıcıya gösterir,
    kullanıcı tek tek iptal eder (iptal ucu denetim kaydı yazar) ve işlemi yeniden dener.
    Geçmişte kalmış rezervasyonlar çakışma sayılmaz.
    """
    cursor.execute(
        """
        SELECT r.rezervasyon_id, r.baslangic_zamani, r.bitis_zamani, COALESCE(k.kullanici_adi, '-')
        FROM cihaz_rezervasyonlari r
        LEFT JOIN personel p ON r.rezervasyonu_yapan_personel_id = p.personel_id
        LEFT JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
        WHERE r.cihaz_id = %s
          AND COALESCE(r.iptal_edildi_mi, FALSE) = FALSE
          AND r.bitis_zamani > NOW()
          AND r.baslangic_zamani < (%s::date + 1)
          AND r.bitis_zamani > %s::date
        ORDER BY r.baslangic_zamani;
        """,
        (cihaz_id, bitis, baslangic),
    )
    kayitlar = cursor.fetchall()
    if kayitlar:
        raise HTTPException(
            status_code=409,
            detail=rezervasyon_cakisma_detayi(
                f"Bu tarihlerde cihaz için {len(kayitlar)} aktif rezervasyon var.", kayitlar
            ),
        )


@app.get("/api/bakimlar")
def bakimlari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int = Depends(izin_kontrol_biri("BAKIM_KAYITLARI_GORUNTULE", "BAKIM_KAYITLARI_YONET"))):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # EKSİK OLAN KISIM: SQL sorgusuna b.bakim_baslangic_tarihi ve b.bakim_bitis_tarihi EKLENDİ
        cursor.execute("""
            SELECT b.bakim_id, c.cihaz_adi, c.envanter_kodu,
                   b.bakim_yapan_kisi, b.yapilan_islem, b.maliyet,
                   b.bakim_tarihi, b.sonraki_bakim_tarihi,
                   b.bakim_baslangic_tarihi, b.bakim_bitis_tarihi, b.uyari_suresi_gun,
                   b.plan_id, p.gorev_turu
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            LEFT JOIN cihaz_bakim_planlari p ON p.plan_id = b.plan_id
            ORDER BY b.bakim_tarihi DESC
            LIMIT %s;
        """, (sinir,))
        kayitlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(kayitlar), "SELECT COUNT(*) FROM cihaz_bakimlari;", sinir)

        return [
            {
                "bakim_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "bakim_yapan_kisi": k[3],
                "yapilan_islem": k[4],
                "maliyet": float(k[5]) if k[5] else 0.0,
                "bakim_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                "sonraki_bakim_tarihi": k[7].isoformat() if k[7] and hasattr(k[7], 'isoformat') else (str(k[7]) if k[7] else "Belirtilmedi"),

                # EKSİK OLAN KISIM: JSON sözlüğüne başlangıç ve bitiş eklendi (eski kayıtlarda null gelirse bakim_tarihi kurtarır)
                "bakim_baslangic_tarihi": k[8].isoformat() if k[8] and hasattr(k[8], 'isoformat') else (str(k[6]) if k[6] else "Belirtilmedi"),
                "bakim_bitis_tarihi": k[9].isoformat() if k[9] and hasattr(k[9], 'isoformat') else (str(k[6]) if k[6] else "Belirtilmedi"),
                "uyari_suresi_gun": k[10],
                "plan_id": k[11],          # kaydın yerine getirdiği plan (yoksa None)
                "plan_adi": k[12]
            }
            for k in kayitlar
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/bakimlar", status_code=201)
def bakim_kaydi_ekle(bakim: BakimOlusturModeli, kullanici_id: int = Depends(izin_kontrol("BAKIM_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cakisan_rezervasyonlari_denetle(
            cursor, bakim.cihaz_id, bakim.bakim_baslangic_tarihi, bakim.bakim_bitis_tarihi
        )

        sonraki_bakim = bakim.sonraki_bakim_tarihi
        if bakim.plan_id is not None:
            # Tarih boş bırakıldıysa plan periyoduna göre otomatik doldurulur.
            if sonraki_bakim is None:
                periyot = plan_periyodu(cursor, bakim.plan_id)
                if periyot is not None:
                    sonraki_bakim = bakim.bakim_bitis_tarihi + timedelta(days=periyot)
            if sonraki_bakim is not None:
                plani_ilerlet(cursor, bakim.plan_id, bakim.cihaz_id, False, sonraki_bakim)
            else:
                raise HTTPException(status_code=404, detail="Plan bulunamadı.")

        cursor.execute("""
            INSERT INTO cihaz_bakimlari (
                cihaz_id, bakim_yapan_kisi, yapilan_islem, maliyet,
                bakim_tarihi, bakim_baslangic_tarihi, bakim_bitis_tarihi, sonraki_bakim_tarihi, uyari_suresi_gun,
                plan_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING bakim_id;
        """, (
            bakim.cihaz_id,
            bakim.bakim_yapan_kisi,
            bakim.yapilan_islem,
            bakim.maliyet,
            bakim.bakim_tarihi,
            bakim.bakim_baslangic_tarihi,
            bakim.bakim_bitis_tarihi,
            sonraki_bakim,
            bakim.uyari_suresi_gun,
            bakim.plan_id
        ))
        bakim_id = cursor.fetchone()[0]

        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", kullanici_id, "cihaz_bakimlari", bakim_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "bakim_id": bakim_id,
                "sonraki_bakim_tarihi": sonraki_bakim.isoformat() if sonraki_bakim else None}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/bakimlar/{bakim_id}")
def bakim_guncelle(bakim_id: int, guncelleme: BakimGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("BAKIM_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_bakimlari WHERE bakim_id = %s FOR UPDATE;", (bakim_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Bakım kaydı bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Güncellenecek veri bulunamadı.")

        # Bakım tarihi ayrı bir alan değildir: her zaman bakım başlangıç tarihine eşit tutulur.
        degisiklikler.pop("bakim_tarihi", None)
        if degisiklikler.get("bakim_baslangic_tarihi") is not None:
            degisiklikler["bakim_tarihi"] = degisiklikler["bakim_baslangic_tarihi"]

        # Tarih aralığı değiştiyse, yeni aralıkla kesişen rezervasyonlar kullanıcıya gösterilir.
        if "bakim_baslangic_tarihi" in degisiklikler or "bakim_bitis_tarihi" in degisiklikler or "sonraki_bakim_tarihi" in degisiklikler:
            cursor.execute(
                """
                SELECT cihaz_id, COALESCE(bakim_baslangic_tarihi, bakim_tarihi::date),
                       COALESCE(bakim_bitis_tarihi, bakim_tarihi::date), sonraki_bakim_tarihi
                FROM cihaz_bakimlari WHERE bakim_id = %s;
                """,
                (bakim_id,),
            )
            cihaz_id, mevcut_bas, mevcut_bit, mevcut_sonraki = cursor.fetchone()
            baslangic = degisiklikler.get("bakim_baslangic_tarihi") or mevcut_bas
            bitis = degisiklikler.get("bakim_bitis_tarihi") or mevcut_bit
            sonraki = degisiklikler["sonraki_bakim_tarihi"] if "sonraki_bakim_tarihi" in degisiklikler else mevcut_sonraki
            sorun = bakim_tarihi_sorunu(baslangic, bitis, sonraki)            # eksik gönderilen alan için kayıtlı değerle birlikte denetlenir
            if sorun:
                raise HTTPException(status_code=422, detail=sorun)
            # Yalnızca tarih aralığı gerçekten değiştiyse kontrol edilir (not/maliyet düzenlemesinde değil).
            if baslangic is not None and bitis is not None and (baslangic, bitis) != (mevcut_bas, mevcut_bit):
                cakisan_rezervasyonlari_denetle(cursor, cihaz_id, baslangic, bitis)

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_bakimlari SET {alanlar} WHERE bakim_id = %s;", (*degerler, bakim_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_bakimlari", hedef_kayit_id=bakim_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Bakım kaydı başarıyla güncellendi."}
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



@app.delete("/api/bakimlar/{bakim_id}")
def bakim_kaydi_sil(bakim_id: int, kullanici_id: int = Depends(izin_kontrol("BAKIM_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        silinen = satiri_sil_ve_ayrintisini_al(cursor, "cihaz_bakimlari", bakim_id)
        if silinen is None:
            raise HTTPException(status_code=404, detail="Bakım kaydı bulunamadı.")

        # Silme ile denetim kaydı (silinen içerikle birlikte) aynı işlemde (transaction) yazılır.
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", kullanici_id, "cihaz_bakimlari", bakim_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Bakım kaydı silindi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Bakım kaydı silinemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# KALİBRASYON YÖNETİMİ MODÜLÜ (CALB-001, CALB-002)
# ==========================================

@app.get("/api/kalibrasyonlar")
def kalibrasyonlari_listele(response: Response = None, limit: int | None = Query(None, ge=1, le=LISTE_UST_SINIRI), kullanici_id: int = Depends(izin_kontrol_biri("KALIBRASYON_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_YONET"))):
    sinir = liste_siniri_coz(limit)
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # SQL Sorgusuna yeni sütunlar eklendi
        cursor.execute("""
            SELECT k.kalibrasyon_id, c.cihaz_adi, c.envanter_kodu,
                   k.kalibrasyon_yapan_kurum, k.gecerlilik_tarihi, k.sertifika_no, k.islem_tarihi,
                   k.kalibrasyon_baslangic_tarihi, k.kalibrasyon_bitis_tarihi, k.uyari_suresi_gun,
                   k.plan_id, p.gorev_turu
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            LEFT JOIN cihaz_bakim_planlari p ON p.plan_id = k.plan_id
            ORDER BY k.islem_tarihi DESC
            LIMIT %s;
        """, (sinir,))
        kayitlar = cursor.fetchall()
        liste_toplamini_bildir(cursor, response, len(kayitlar), "SELECT COUNT(*) FROM cihaz_kalibrasyonlari;", sinir)

        return [
            {
                "kalibrasyon_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "kalibrasyon_yapan_kurum": k[3],
                "gecerlilik_tarihi": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]),
                "sertifika_no": k[5],
                "islem_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                # Yeni alanlar ve Fallback mantığı (Eski kayıtlarda null gelirse işlem tarihi baz alınır)
                "kalibrasyon_baslangic_tarihi": k[7].isoformat() if k[7] and hasattr(k[7], 'isoformat') else (str(k[6])[:10] if k[6] else "Belirtilmedi"),
                "kalibrasyon_bitis_tarihi": k[8].isoformat() if k[8] and hasattr(k[8], 'isoformat') else (str(k[6])[:10] if k[6] else "Belirtilmedi"),
                "uyari_suresi_gun": k[9],
                "plan_id": k[10],          # kaydın yerine getirdiği plan (yoksa None)
                "plan_adi": k[11]
            }
            for k in kayitlar
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.post("/api/kalibrasyonlar", status_code=201)
def kalibrasyon_kaydi_ekle(kalib: KalibrasyonOlusturModeli, kullanici_id: int = Depends(izin_kontrol("KALIBRASYON_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cakisan_rezervasyonlari_denetle(
            cursor, kalib.cihaz_id, kalib.kalibrasyon_baslangic_tarihi, kalib.kalibrasyon_bitis_tarihi
        )

        if kalib.plan_id is not None:
            plani_ilerlet(cursor, kalib.plan_id, kalib.cihaz_id, True, kalib.gecerlilik_tarihi)

        # INSERT sorgusuna ve VALUES kısmına yeni sütunlar eklendi
        cursor.execute("""
            INSERT INTO cihaz_kalibrasyonlari (
                cihaz_id, kalibrasyon_yapan_kurum, gecerlilik_tarihi, sertifika_no, islem_tarihi,
                kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi, uyari_suresi_gun, plan_id
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s) RETURNING kalibrasyon_id;
        """, (
            kalib.cihaz_id, 
            kalib.kalibrasyon_yapan_kurum, 
            kalib.gecerlilik_tarihi, 
            kalib.sertifika_no,
            kalib.kalibrasyon_baslangic_tarihi, # EKLENDİ
            kalib.kalibrasyon_bitis_tarihi,     # EKLENDİ
            kalib.uyari_suresi_gun,
            kalib.plan_id
        ))
        kalibrasyon_id = cursor.fetchone()[0]

        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kalibrasyon başarıyla eklendi.", "kalibrasyon_id": kalibrasyon_id}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/kalibrasyonlar/{kalibrasyon_id}")
def kalibrasyon_guncelle(kalibrasyon_id: int, guncelleme: KalibrasyonGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("KALIBRASYON_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_kalibrasyonlari WHERE kalibrasyon_id = %s FOR UPDATE;", (kalibrasyon_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Değişiklik yok.")

        # Tarih aralığı değiştiyse, yeni aralıkla kesişen rezervasyonlar kullanıcıya gösterilir.
        if "kalibrasyon_baslangic_tarihi" in degisiklikler or "kalibrasyon_bitis_tarihi" in degisiklikler:
            cursor.execute(
                """
                SELECT cihaz_id, kalibrasyon_baslangic_tarihi, kalibrasyon_bitis_tarihi
                FROM cihaz_kalibrasyonlari WHERE kalibrasyon_id = %s;
                """,
                (kalibrasyon_id,),
            )
            cihaz_id, mevcut_bas, mevcut_bit = cursor.fetchone()
            baslangic = degisiklikler.get("kalibrasyon_baslangic_tarihi") or mevcut_bas
            bitis = degisiklikler.get("kalibrasyon_bitis_tarihi") or mevcut_bit
            if baslangic is not None and bitis is not None and bitis < baslangic:
                raise HTTPException(status_code=422, detail="Kalibrasyon bitiş tarihi, başlangıç tarihinden önce olamaz.")
            if baslangic is not None and bitis is not None and (baslangic, bitis) != (mevcut_bas, mevcut_bit):
                cakisan_rezervasyonlari_denetle(cursor, cihaz_id, baslangic, bitis)

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_kalibrasyonlari SET {alanlar} WHERE kalibrasyon_id = %s;", (*degerler, kalibrasyon_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili"}
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


@app.delete("/api/kalibrasyonlar/{kalibrasyon_id}")
def kalibrasyon_kaydi_sil(kalibrasyon_id: int, kullanici_id: int = Depends(izin_kontrol("KALIBRASYON_KAYITLARI_YONET"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        silinen = satiri_sil_ve_ayrintisini_al(cursor, "cihaz_kalibrasyonlari", kalibrasyon_id)
        if silinen is None:
            raise HTTPException(status_code=404, detail="Kalibrasyon kaydı bulunamadı.")

        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", kullanici_id, "cihaz_kalibrasyonlari", kalibrasyon_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kalibrasyon kaydı silindi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Kalibrasyon kaydı silinemedi.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# ==========================================
# DASHBOARD VE RAPORLAMA MODÜLÜ (DASH-001)
# ==========================================

# ==========================================
# BAKIM / KALİBRASYON PLANLARI (müdür konfigürasyonu)
# ==========================================
def bakim_plani_durumu(kalan_gun, uyari_suresi_gun, aktif_mi):
    if not aktif_mi:
        return "Pasif"
    if kalan_gun < 0:
        return "Gecikmiş"
    if kalan_gun <= uyari_suresi_gun:
        return "Yaklaşıyor"
    return "Planlı"



def _plan_yetkileri(cursor, kullanici_id):
    """Giriş yapan kişinin bakım ve kalibrasyon izinlerini DB'den al."""
    cursor.execute("""
        SELECT i.izin_adi
        FROM kullanicilar k
        JOIN rol_izinleri ri ON ri.rol_id = k.rol_id
        JOIN izinler i ON i.izin_id = ri.izin_id
        WHERE k.kullanici_id = %s
          AND ri.izin_var = 1
          AND i.izin_adi = ANY(%s);
    """, (
        kullanici_id,
        ["BAKIM_KAYITLARI_YONET", "KALIBRASYON_KAYITLARI_YONET", "BAKIM_KAYITLARI_GORUNTULE", "KALIBRASYON_KAYITLARI_GORUNTULE"]
    ))
    return {satir[0] for satir in cursor.fetchall()}


def _plan_turu_yetkisini_dogrula(izinler, gorev_turu):
    gerekli = (
        "KALIBRASYON_KAYITLARI_YONET"
        if plan_kalibrasyon_mu(gorev_turu)
        else "BAKIM_KAYITLARI_YONET"
    )
    if gerekli not in izinler:
        raise HTTPException(
            status_code=403,
            detail="Bu plan türü için yetkiniz bulunmuyor."
        )


@app.get("/api/bakim-planlari")
def bakim_planlarini_listele(
    cihaz_id: int | None = None,
    aktif_mi: bool | None = None,
    kullanici_id: int = Depends(mevcut_kullanici_id),
):
    """Cihazların tekrarlayan bakım/kalibrasyon planları (en yakın tarih önce)."""
    if cihaz_id is not None and cihaz_id <= 0:
        raise HTTPException(status_code=422, detail="Geçerli bir cihaz seçilmelidir.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        izinler = _plan_yetkileri(cursor, kullanici_id)
        # Planları görmek için görüntüleme YA DA yönetme izni yeter; ekleme/düzenleme/silme yalnızca yönetme ister
        # (_plan_turu_yetkisini_dogrula *_YONET arar).
        bakim = bool(izinler & {"BAKIM_KAYITLARI_YONET", "BAKIM_KAYITLARI_GORUNTULE"})
        kalibrasyon = bool(izinler & {"KALIBRASYON_KAYITLARI_YONET", "KALIBRASYON_KAYITLARI_GORUNTULE"})

        if not bakim and not kalibrasyon:
            raise HTTPException(
                status_code=403,
                detail="Planları görüntüleme yetkiniz bulunmuyor."
            )

        kosullar, parametreler = [], []

        if bakim and not kalibrasyon:
            kosullar.append(
                "LOWER(BTRIM(p.gorev_turu)) NOT LIKE 'kalibrasyon%%'"
            )
        elif kalibrasyon and not bakim:
            kosullar.append(
                "LOWER(BTRIM(p.gorev_turu)) LIKE 'kalibrasyon%%'"
            )
        if cihaz_id is not None:
            kosullar.append("p.cihaz_id = %s")
            parametreler.append(cihaz_id)
        if aktif_mi is not None:
            kosullar.append("COALESCE(p.aktif_mi, TRUE) = %s")
            parametreler.append(aktif_mi)
        where = "WHERE " + " AND ".join(kosullar) if kosullar else ""
        cursor.execute(
            f"""
            SELECT p.plan_id, p.cihaz_id, c.envanter_kodu, c.cihaz_adi, p.gorev_turu, p.periyot_gun,
                   COALESCE(p.uyari_suresi_gun, 0), p.sonraki_gorev_tarihi,
                   (p.sonraki_gorev_tarihi - CURRENT_DATE), COALESCE(p.aktif_mi, TRUE)
            FROM cihaz_bakim_planlari p
            JOIN cihazlar c ON c.cihaz_id = p.cihaz_id
            {where}
            ORDER BY p.sonraki_gorev_tarihi, p.plan_id;
            """,
            parametreler,
        )
        return [
            {
                "plan_id": k[0], "cihaz_id": k[1], "envanter_kodu": k[2], "cihaz_adi": k[3],
                "gorev_turu": k[4], "periyot_gun": k[5], "uyari_suresi_gun": k[6],
                "sonraki_gorev_tarihi": k[7].isoformat(), "kalan_gun": k[8], "aktif_mi": k[9],
                "durum": bakim_plani_durumu(k[8], k[6], k[9]),
            }
            for k in cursor.fetchall()
        ]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Bakım planları alınamadı.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


def plani_ilerlet(cursor, plan_id, cihaz_id, kalibrasyon_mi, sonraki_tarih):
    """Kayıt bir plana bağlıysa planın 'sonraki tarihini' ilerletir ve o tarihi döndürür.

    sonraki_tarih verilmişse (kullanıcının girdiği) o kullanılır; yoksa kayıt bitişi + periyot
    ayrıca hesaplanıp çağıran tarafından verilir. Plan başka cihaza ait, pasif ya da türü
    uyumsuzsa (bakım kaydı ile kalibrasyon planı gibi) kayıt hiç eklenmeden hata verilir.
    """
    cursor.execute(
        "SELECT cihaz_id, gorev_turu, COALESCE(aktif_mi, TRUE) FROM cihaz_bakim_planlari WHERE plan_id = %s FOR UPDATE;",
        (plan_id,),
    )
    plan = cursor.fetchone()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan bulunamadı.")
    if plan[0] != cihaz_id:
        raise HTTPException(status_code=422, detail="Seçilen plan bu cihaza ait değil.")
    if not plan[2]:
        raise HTTPException(status_code=422, detail="Seçilen plan pasif durumda.")
    if plan_kalibrasyon_mu(plan[1]) != kalibrasyon_mi:
        raise HTTPException(status_code=422, detail="Plan türü bu kayıt türüyle uyuşmuyor.")
    cursor.execute("UPDATE cihaz_bakim_planlari SET sonraki_gorev_tarihi = %s WHERE plan_id = %s;", (sonraki_tarih, plan_id))
    return sonraki_tarih




def plan_periyodu(cursor, plan_id):
    cursor.execute("SELECT periyot_gun FROM cihaz_bakim_planlari WHERE plan_id = %s;", (plan_id,))
    satir = cursor.fetchone()
    return satir[0] if satir else None


def _ayni_planli_aktif_kayit_var_mi(cursor, cihaz_id, gorev_turu, haric_plan_id=None):
    cursor.execute(
        """
        SELECT 1 FROM cihaz_bakim_planlari
        WHERE cihaz_id = %s AND LOWER(gorev_turu) = LOWER(%s) AND COALESCE(aktif_mi, TRUE) = TRUE
          AND (%s::int IS NULL OR plan_id <> %s::int)
        LIMIT 1;
        """,
        (cihaz_id, gorev_turu, haric_plan_id, haric_plan_id),
    )
    return cursor.fetchone() is not None


@app.post("/api/bakim-planlari", status_code=201)
def bakim_plani_ekle(plan: BakimPlaniOlusturModeli, kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        izinler = _plan_yetkileri(cursor, kullanici_id)
        _plan_turu_yetkisini_dogrula(izinler, plan.gorev_turu)
        cursor.execute("SELECT 1 FROM cihazlar WHERE cihaz_id = %s;", (plan.cihaz_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        if _ayni_planli_aktif_kayit_var_mi(cursor, plan.cihaz_id, plan.gorev_turu):
            raise HTTPException(status_code=409, detail="Bu cihaz için aynı türde aktif bir plan zaten var.")
        sonraki = plan.sonraki_gorev_tarihi or (date.today() + timedelta(days=plan.periyot_gun))
        cursor.execute(
            """
            INSERT INTO cihaz_bakim_planlari (cihaz_id, gorev_turu, periyot_gun, uyari_suresi_gun, sonraki_gorev_tarihi, aktif_mi)
            VALUES (%s, %s, %s, %s, %s, TRUE) RETURNING plan_id;
            """,
            (plan.cihaz_id, plan.gorev_turu, plan.periyot_gun, plan.uyari_suresi_gun, sonraki),
        )
        plan_id = cursor.fetchone()[0]
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici_id,
                              hedef_tablo="cihaz_bakim_planlari", hedef_kayit_id=plan_id, mevcut_cursor=cursor)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Plan eklendi.", "plan_id": plan_id,
                "sonraki_gorev_tarihi": sonraki.isoformat()}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.put("/api/bakim-planlari/{plan_id}")
def bakim_plani_guncelle(plan_id: int, guncelleme: BakimPlaniGuncelleModeli,
                         kullanici_id: int = Depends(mevcut_kullanici_id)):
    degisiklikler = guncelleme.model_dump(exclude_unset=True)
    if not degisiklikler:
        raise HTTPException(status_code=422, detail="Güncellenecek veri bulunamadı.")
    if any(deger is None for deger in degisiklikler.values()):
        raise HTTPException(status_code=422, detail="Alanlar boş bırakılamaz.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT cihaz_id, gorev_turu, periyot_gun, COALESCE(uyari_suresi_gun, 0), COALESCE(aktif_mi, TRUE)
            FROM cihaz_bakim_planlari WHERE plan_id = %s FOR UPDATE;
            """,
            (plan_id,),
        )
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Plan bulunamadı.")
        cihaz_id, tur, periyot, uyari, aktif = mevcut
        izinler = _plan_yetkileri(cursor, kullanici_id)
        _plan_turu_yetkisini_dogrula(izinler, tur)
        yeni_tur = degisiklikler.get("gorev_turu", tur)
        _plan_turu_yetkisini_dogrula(izinler, yeni_tur)
        tur = yeni_tur
        periyot = degisiklikler.get("periyot_gun", periyot)
        uyari = degisiklikler.get("uyari_suresi_gun", uyari)
        aktif = degisiklikler.get("aktif_mi", aktif)
        if uyari > periyot:
            raise HTTPException(status_code=422, detail="Uyarı süresi periyottan uzun olamaz.")
        if aktif and _ayni_planli_aktif_kayit_var_mi(cursor, cihaz_id, tur, plan_id):
            raise HTTPException(status_code=409, detail="Bu cihaz için aynı türde aktif bir plan zaten var.")
        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        cursor.execute(f"UPDATE cihaz_bakim_planlari SET {alanlar} WHERE plan_id = %s;",
                       (*degisiklikler.values(), plan_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id,
                              hedef_tablo="cihaz_bakim_planlari", hedef_kayit_id=plan_id, mevcut_cursor=cursor)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Plan güncellendi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.delete("/api/bakim-planlari/{plan_id}")
def bakim_plani_sil(plan_id: int, kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT gorev_turu FROM cihaz_bakim_planlari "
            "WHERE plan_id = %s FOR UPDATE;",
            (plan_id,)
        )
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(
                status_code=404, detail="Plan bulunamadı."
            )
        izinler = _plan_yetkileri(cursor, kullanici_id)
        _plan_turu_yetkisini_dogrula(izinler, mevcut[0])
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "cihaz_bakim_planlari", plan_id)
        if silinen is None:
            raise HTTPException(status_code=404, detail="Plan bulunamadı.")
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="DELETE", kullanici_id=kullanici_id,
                              hedef_tablo="cihaz_bakim_planlari", hedef_kayit_id=plan_id, mevcut_cursor=cursor,
                              ayrinti=silinen)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Plan silindi."}
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()



# ==========================================
# FAALİYET YÖNETİMİ MODÜLÜ API UÇLARI
# ==========================================

@app.get("/api/faaliyetler")
def faaliyetleri_getir(kullanici_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece aktif olan faaliyetleri listele
        cursor.execute("SELECT faaliyet_id, faaliyet_adi, puan FROM faaliyetler WHERE aktif_mi = true ORDER BY faaliyet_id;")

        faaliyetler = []
        for kayit in cursor.fetchall():
            faaliyetler.append({
                "id": kayit[0],
                "ad": kayit[1],
                "puan": kayit[2]
            })
        return faaliyetler
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/faaliyet-birimleri")
def faaliyet_birimleri_getir(kullanici_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece aktif olan birimleri listele
        cursor.execute("SELECT birim_id, birim_adi FROM faaliyet_birimleri WHERE aktif_mi = true ORDER BY birim_id;")

        birimler = []
        for kayit in cursor.fetchall():
            birimler.append({
                "id": kayit[0],
                "ad": kayit[1]
            })
        return birimler
    except Exception:
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

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


# --- GÜNCELLENEN: YENİ TABLOYA (ÖĞRENCİ TAKİP) KAYIT ATAR ---
@app.post("/api/faaliyet-kayitlari")
def faaliyet_kaydi_ekle(kayit: FaaliyetKayitModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kayıt ogrenci_faaliyet_takip tablosuna yazılır (miktar "adet" sütununa gider).
        cursor.execute("""
            INSERT INTO ogrenci_faaliyet_takip
            (ogrenci_id, faaliyet_id, birim_id, adet,
             faaliyet_tarihi, kayit_puani)
            SELECT %s, f.faaliyet_id, %s, %s, CURRENT_DATE, f.puan
            FROM faaliyetler AS f
            WHERE f.faaliyet_id = %s AND f.aktif_mi = TRUE
            RETURNING takip_id;
        """, (
            kayit.ogrenci_id,
            kayit.birim_id,
            kayit.miktar,
            kayit.faaliyet_id
        ))
        if cursor.rowcount != 1:
            raise HTTPException(
                status_code=400,
                detail="Aktif faaliyet türü bulunamadı."
            )

        yeni_id = cursor.fetchone()[0]

        # Denetim kaydı
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", yetkili_id, "ogrenci_faaliyet_takip", yeni_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Öğrenci faaliyeti başarıyla sisteme işlendi."}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu."
        )
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

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

# --- Faaliyet kayıtları listesi ---
@app.get("/api/faaliyet-kayitlari")
def faaliyet_kayitlarini_getir(
    limit: Optional[int] = None,
    offset: int = 0,
    response: Response = None,
    kullanici_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")),
):
    """Faaliyet kayıtları (en yeni önce). limit verilirse toplam sayı X-Toplam-Kayit başlığında döner."""
    if limit is not None and (limit < 1 or limit > 5000):
        raise HTTPException(status_code=422, detail="limit 1 ile 5000 arasında olmalıdır.")
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset negatif olamaz.")
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # 4 tabloyu birleştirir; toplam puan = adet x kaydın puanı
        sorgu = """
        SELECT
            t.takip_id,
            o.ad_soyad,
            o.ogrenci_numarasi,
            f.faaliyet_adi,
            t.adet,
            b.birim_adi,
            (t.adet * t.kayit_puani) AS toplam_puan,
            t.faaliyet_tarihi,
            t.ogrenci_id,
            t.faaliyet_id,
            t.birim_id
        FROM ogrenci_faaliyet_takip t
        JOIN ogrenciler o ON t.ogrenci_id = o.ogrenci_id
        JOIN faaliyetler f ON t.faaliyet_id = f.faaliyet_id
        JOIN faaliyet_birimleri b ON t.birim_id = b.birim_id
        ORDER BY t.olusturulma_tarihi DESC, t.takip_id DESC
        """
        if limit is None:
            cursor.execute(sorgu + ";")
        else:
            cursor.execute("SELECT COUNT(*) FROM ogrenci_faaliyet_takip;")
            if response is not None:
                response.headers["X-Toplam-Kayit"] = str((cursor.fetchone() or (0,))[0])
            cursor.execute(sorgu + " LIMIT %s OFFSET %s;", (limit, offset))

        kayitlar = []
        for row in cursor.fetchall():
            kayitlar.append({
                "id": row[0],
                "ad_soyad": row[1],
                "ogrenci_no": row[2],
                "faaliyet_adi": row[3],
                "miktar": f"{row[4]} {row[5]}", # Örn: "3 KISI" veya "5 SAAT"
                "toplam_puan": row[6],
                "tarih": row[7].strftime("%d.%m.%Y") if row[7] else "",
                "ogrenci_id": row[8],
                "faaliyet_id": row[9],
                "birim_id": row[10],
            })
        return kayitlar
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()
# --- Faaliyet kaydı düzenleme (PUT) ---
@app.put("/api/faaliyet-kayitlari/{takip_id}")
def faaliyet_kaydi_guncelle(takip_id: int, kayit: FaaliyetKayitModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kaydı kilitleyip önceki değerlerini al (denetim kaydına "neyden neye" yazılır).
        alanlar = ("ogrenci_id", "faaliyet_id", "birim_id", "adet", "kayit_puani")
        cursor.execute(
            "SELECT ogrenci_id, faaliyet_id, birim_id, adet, kayit_puani "
            "FROM ogrenci_faaliyet_takip WHERE takip_id = %s FOR UPDATE;",
            (takip_id,)
        )
        eski_satir = cursor.fetchone()
        if not eski_satir:
            raise HTTPException(status_code=404, detail="Güncellenecek kayıt bulunamadı.")
        onceki = dict(zip(alanlar, eski_satir))

        # Faaliyet türü değişmediyse kayıttaki puan korunur (sonradan değişen tür puanı eski kaydı etkilemez).
        # Değiştiyse yeni tür aktif olmalı ve kayıt o türün güncel puanını alır.
        kayit_puani = onceki.get("kayit_puani")
        if onceki.get("faaliyet_id") != kayit.faaliyet_id:
            cursor.execute(
                "SELECT puan FROM faaliyetler WHERE faaliyet_id = %s AND aktif_mi = TRUE;",
                (kayit.faaliyet_id,)
            )
            puan = cursor.fetchone()
            if puan is None:
                raise HTTPException(status_code=400, detail="Aktif faaliyet türü bulunamadı.")
            kayit_puani = puan[0]

        yeni = {
            "ogrenci_id": kayit.ogrenci_id,
            "faaliyet_id": kayit.faaliyet_id,
            "birim_id": kayit.birim_id,
            "adet": kayit.miktar,
            "kayit_puani": kayit_puani,
        }
        if all(onceki.get(alan) == yeni[alan] for alan in alanlar):
            conn.commit()
            return {"durum": "basarili", "mesaj": "Kayıtta değişiklik yapılmadı."}

        cursor.execute("""
            UPDATE ogrenci_faaliyet_takip
            SET ogrenci_id = %s,
                faaliyet_id = %s,
                birim_id = %s,
                adet = %s,
                kayit_puani = %s
            WHERE takip_id = %s;
        """, (
            kayit.ogrenci_id,
            kayit.faaliyet_id,
            kayit.birim_id,
            kayit.miktar,
            kayit_puani,
            takip_id
        ))

        # Denetim kaydı: yalnızca değişen alanların önceki ve yeni değeri (kimlik ve sayı; kişisel veri yok).
        degisen = [alan for alan in alanlar if onceki.get(alan) != yeni[alan]]
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, "UPDATE", yetkili_id, "ogrenci_faaliyet_takip", takip_id, mevcut_cursor=cursor,
            ayrinti={
                "onceki": {alan: onceki.get(alan) for alan in degisen},
                "yeni": {alan: yeni[alan] for alan in degisen},
            },
        )

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla güncellendi."}
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

# --- Faaliyet kaydı silme (DELETE) ---
@app.delete("/api/faaliyet-kayitlari/{takip_id}")
def faaliyet_kaydi_sil(takip_id: int, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Silinmeden önce kaydın var olup olmadığını kontrol edelim
        cursor.execute("SELECT * FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Silinecek kayıt zaten yok veya bulunamadı.")

        # Kaydı veritabanından siliyoruz; silinen içerik denetim kaydına yazılır (kim, neyi sildi).
        silinen = satiri_sil_ve_ayrintisini_al(cursor, "ogrenci_faaliyet_takip", takip_id)
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", yetkili_id, "ogrenci_faaliyet_takip", takip_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla silindi!"}
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

# DANIŞMA MASASI OTURUM ENDPOINTLERİ

@app.post("/api/danisma/oturum/baslat", status_code=201)
def danisma_oturumu_baslat(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONET")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Öğrencinin kaydını kilitle.
        # Eşzamanlı başlatma işlemlerini sıraya alır.
        cursor.execute(
            """
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE
            FOR UPDATE;
            """,
            (kullanici_id,)
        )

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        ogrenci_id = ogrenci[0]

        # Açık oturum kontrolü
        cursor.execute(
            """
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NULL;
            """,
            (ogrenci_id,)
        )

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Zaten devam eden bir göreviniz bulunuyor."
            )

        # Yeni görev başlat
        cursor.execute(
            """
            INSERT INTO danisma_masasi_oturumlari
                (ogrenci_id, baslangic_zamani)
            VALUES (%s, CURRENT_TIMESTAMP)
            RETURNING oturum_id, baslangic_zamani;
            """,
            (ogrenci_id,)
        )

        oturum_id, baslangic = cursor.fetchone()

        # Audit kaydı
        cursor.execute(
            """
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu,
                 hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
            """,
            (
                kullanici_id,
                "CREATE",
                "danisma_masasi_oturumlari",
                oturum_id
            )
        )

        conn.commit()

        return {
            "mesaj": "Danışma masası göreviniz başlatıldı.",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "durum": "AKTIF"
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=409,
            detail="Zaten devam eden bir göreviniz bulunuyor."
        )
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise

    except Exception:
        if conn is not None:
            conn.rollback()

        raise HTTPException(
            status_code=500,
            detail="Görev başlatılırken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.patch("/api/danisma/oturum/bitir")
def danisma_oturumu_bitir(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONET")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Giriş yapan öğrenciyi bul ve kilitle
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE
            FOR UPDATE;
        """, (kullanici_id,))

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        ogrenci_id = ogrenci[0]

        # Öğrencinin açık görevini bul
        cursor.execute("""
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NULL
            FOR UPDATE;
        """, (ogrenci_id,))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=409,
                detail="Devam eden bir göreviniz bulunmuyor."
            )

        oturum_id = oturum[0]

        # Görevi sonlandır
        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET bitis_zamani = clock_timestamp()
            WHERE oturum_id = %s
            RETURNING baslangic_zamani, bitis_zamani;
        """, (oturum_id,))

        baslangic, bitis = cursor.fetchone()

        toplam_saniye = max(
            0, int((bitis - baslangic).total_seconds())
        )

        saat, kalan = divmod(toplam_saniye, 3600)
        dakika = kalan // 60

        # Audit kaydı
        cursor.execute("""
            INSERT INTO denetim_kayitlari
                (kullanici_id, olay_turu,
                 hedef_tablo, hedef_kayit_id)
            VALUES (%s, %s, %s, %s);
        """, (
            kullanici_id,
            "UPDATE",
            "danisma_masasi_oturumlari",
            oturum_id
        ))

        conn.commit()

        return {
            "mesaj": "Göreviniz başarıyla tamamlandı.",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "bitis_zamani": bitis.isoformat(),
            "toplam_saniye": toplam_saniye,
            "toplam_dakika": toplam_saniye // 60,
            "calisilan_sure": f"{saat} saat {dakika} dakika",
            "durum": "TAMAMLANDI"
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
            detail="Görev bitirilirken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/api/danisma/oturum/aktif")
def danisma_aktif_oturum(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONET")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Giriş yapan öğrenciyi bul
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE;
        """, (kullanici_id,))

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        # Devam eden görevi sorgula
        cursor.execute("""
            SELECT
                oturum_id,
                baslangic_zamani,
                clock_timestamp()::timestamp
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NULL
            ORDER BY baslangic_zamani DESC
            LIMIT 1;
        """, (ogrenci[0],))

        oturum = cursor.fetchone()

        if oturum is None:
            return {
                "durum": "PASIF",
                "mesaj": "Devam eden göreviniz bulunmuyor.",
                "oturum_id": None,
                "calisilan_sure": "0 saat 0 dakika",
                "toplam_saniye": 0
            }

        oturum_id, baslangic, simdi = oturum

        toplam_saniye = max(
            0, int((simdi - baslangic).total_seconds())
        )

        saat, kalan = divmod(toplam_saniye, 3600)
        dakika = kalan // 60

        return {
            "durum": "AKTIF",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "toplam_saniye": toplam_saniye,
            "toplam_dakika": toplam_saniye // 60,
            "calisilan_sure": f"{saat} saat {dakika} dakika"
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Aktif görev bilgisi alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/api/danisma/oturum/gecmis")
def danisma_oturum_gecmisi(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONET")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE kullanici_id = %s
              AND aktif_mi = TRUE;
        """, (kullanici_id,))

        ogrenci = cursor.fetchone()

        if ogrenci is None:
            raise HTTPException(
                status_code=403,
                detail="Hesabınız bir öğrenci kaydına bağlı değil. Lütfen yöneticinize başvurun."
            )

        cursor.execute("""
            SELECT oturum_id,
                   baslangic_zamani,
                   bitis_zamani,
                   onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND bitis_zamani IS NOT NULL
            ORDER BY baslangic_zamani DESC
            LIMIT 50;
        """, (ogrenci[0],))

        kayitlar = cursor.fetchall()
        gecmis = []

        for oturum_id, baslangic, bitis, onay in kayitlar:
            saniye = max(
                0, int((bitis - baslangic).total_seconds())
            )
            saat, kalan = divmod(saniye, 3600)
            dakika = kalan // 60

            gecmis.append({
                "oturum_id": oturum_id,
                "tarih": baslangic.date().isoformat(),
                "baslangic_zamani": baslangic.isoformat(),
                "bitis_zamani": bitis.isoformat(),
                "toplam_dakika": saniye // 60,
                "calisilan_sure": f"{saat} saat {dakika} dakika",
                "onaylandi_mi": onay
            })

        return {
            "toplam_kayit": len(gecmis),
            "oturumlar": gecmis
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Zaten devam eden bir göreviniz bulunuyor."
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Görev geçmişi alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# ==========================================
# DANIŞMA MASASI YÖNETİMİ
# ==========================================


@app.get("/api/danisma/yonetim/onay-bildirimleri")
def danisma_onay_bildirimleri(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    """Tamamlanmis ve onay bekleyen danisma masasi gorevleri."""

    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM danisma_masasi_oturumlari
            WHERE bitis_zamani IS NOT NULL
              AND COALESCE(onaylandi_mi, FALSE) = FALSE;
        """)

        toplam = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                d.oturum_id,
                o.ad_soyad,
                d.bitis_zamani
            FROM danisma_masasi_oturumlari d
            JOIN ogrenciler o
                ON d.ogrenci_id = o.ogrenci_id
            WHERE d.bitis_zamani IS NOT NULL
              AND COALESCE(d.onaylandi_mi, FALSE) = FALSE
            ORDER BY d.bitis_zamani DESC
            LIMIT 10;
        """)

        kayitlar = cursor.fetchall()

        return {
            "toplam": toplam,
            "oturumlar": [
                {
                    "oturum_id": kayit[0],
                    "ad_soyad": kayit[1],
                    "bitis_zamani": kayit[2].isoformat()
                }
                for kayit in kayitlar
            ]
        }

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


# Bir danışma masası görevi en fazla mesai süresi kadar olabilir (08:00-18:00 = 10 saat). Elle girilen ya da düzenlenen
# daha uzun görev reddedilir; öğrencinin bitirmeyi unuttuğu görev ise kaydedilir ama onay listesinde "uzun görev" diye işaretlenir.
DANISMA_GOREV_EN_UZUN_SAAT = 10
DANISMA_GOREV_COK_UZUN_MESAJI = (
    f"Bir görev en fazla {DANISMA_GOREV_EN_UZUN_SAAT} saat olabilir. "
    "Daha uzun çalışmayı ayrı görevler olarak girin."
)


def danisma_gorevi_cok_uzun_mu(baslangic, bitis):
    return (bitis - baslangic).total_seconds() > DANISMA_GOREV_EN_UZUN_SAAT * 3600


# Yönetim listesinde en yeni kaç görev gösterilir. Devam eden ve onay bekleyen görevler bu sınırdan bağımsız olarak her zaman gelir
# (eski bir onay bekleyen görev listede kaybolup onaylanamaz hale gelmesin).
DANISMA_LISTE_EN_FAZLA = 200


@app.get("/api/danisma/yonetim/oturumlar")
def danisma_yonetim_oturumlari(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Kartlardaki sayılar listeden değil, tüm kayıtlardan hesaplanır.
        cursor.execute("""
            SELECT
                COUNT(*),
                COUNT(*) FILTER (WHERE bitis_zamani IS NULL),
                COUNT(*) FILTER (WHERE bitis_zamani IS NOT NULL AND onaylandi_mi IS NOT TRUE),
                COUNT(*) FILTER (WHERE onaylandi_mi IS TRUE)
            FROM danisma_masasi_oturumlari;
        """)
        toplam, aktif, bekleyen, onaylanan = cursor.fetchone()

        cursor.execute("""
            SELECT
                d.oturum_id,
                d.ogrenci_id,
                o.ad_soyad,
                o.ogrenci_numarasi,
                d.baslangic_zamani,
                d.bitis_zamani,
                d.onaylandi_mi
            FROM danisma_masasi_oturumlari d
            JOIN ogrenciler o
                ON d.ogrenci_id = o.ogrenci_id
            WHERE d.oturum_id IN (
                    SELECT oturum_id
                    FROM danisma_masasi_oturumlari
                    ORDER BY baslangic_zamani DESC
                    LIMIT %s
                )
               OR d.bitis_zamani IS NULL
               OR d.onaylandi_mi IS NOT TRUE
            ORDER BY d.baslangic_zamani DESC;
        """, (DANISMA_LISTE_EN_FAZLA,))

        kayitlar = cursor.fetchall()
        oturumlar = []

        for (
            oturum_id,
            ogrenci_id,
            ad_soyad,
            ogrenci_numarasi,
            baslangic,
            bitis,
            onay
        ) in kayitlar:

            bitis_hesap = bitis if bitis is not None else datetime.now()
            toplam_saniye = max(
                0,
                int((bitis_hesap - baslangic).total_seconds())
            )

            oturumlar.append({
                "oturum_id": oturum_id,
                "ogrenci_id": ogrenci_id,
                "ad_soyad": ad_soyad,
                "ogrenci_numarasi": ogrenci_numarasi,
                "baslangic_zamani": baslangic.isoformat(),
                "bitis_zamani": bitis.isoformat() if bitis else None,
                "toplam_saniye": toplam_saniye,
                "durum": "AKTIF" if bitis is None else "TAMAMLANDI",
                "onaylandi_mi": onay,
                # Mesai süresini aşan görev: öğrenci bitirmeyi unutmuş olabilir, onaylamadan önce saatler kontrol edilmeli.
                "uzun_gorev": toplam_saniye > DANISMA_GOREV_EN_UZUN_SAAT * 3600,
            })

        return {
            "toplam_kayit": toplam,
            "ozet": {
                "toplam": toplam,
                "aktif": aktif,
                "bekleyen": bekleyen,
                "onaylanan": onaylanan,
            },
            "kisaltildi": len(oturumlar) < toplam,
            "oturumlar": oturumlar
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Danışma masası görev kayıtları alınamadı."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.patch("/api/danisma/yonetim/oturumlar/{oturum_id}/onayla")
def danisma_yonetim_oturum_onayla(
    oturum_id: int,
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT bitis_zamani, onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s
            FOR UPDATE;
        """, (oturum_id,))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=404,
                detail="Görev kaydı bulunamadı."
            )

        bitis_zamani, onaylandi_mi = oturum

        if bitis_zamani is None:
            raise HTTPException(
                status_code=409,
                detail="Devam eden görev onaylanamaz."
            )

        if onaylandi_mi:
            raise HTTPException(
                status_code=409,
                detail="Bu görev zaten onaylanmış."
            )

        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET onaylandi_mi = TRUE
            WHERE oturum_id = %s;
        """, (oturum_id,))

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={"onceki": {"onaylandi_mi": False}, "yeni": {"onaylandi_mi": True}}
        )

        conn.commit()

        return {
            "durum": "basarili",
            "mesaj": "Danışma masası görevi onaylandı.",
            "oturum_id": oturum_id,
            "onaylandi_mi": True
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
            detail="Görev onaylanırken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.patch("/api/danisma/yonetim/oturumlar/{oturum_id}/onay-geri-al")
def danisma_yonetim_onay_geri_al(
    oturum_id: int,
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    """Onaylanmış görevin onayını kaldırır; görev yeniden onay bekler ve düzenlenebilir."""
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s
            FOR UPDATE;
        """, (oturum_id,))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=404,
                detail="Görev kaydı bulunamadı."
            )

        if not oturum[0]:
            raise HTTPException(
                status_code=409,
                detail="Bu görev onaylı değil."
            )

        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET onaylandi_mi = FALSE
            WHERE oturum_id = %s;
        """, (oturum_id,))

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={"onceki": {"onaylandi_mi": True}, "yeni": {"onaylandi_mi": False}}
        )

        conn.commit()

        return {
            "durum": "basarili",
            "mesaj": "Görevin onayı geri alındı.",
            "oturum_id": oturum_id,
            "onaylandi_mi": False
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
            detail="Görevin onayı geri alınırken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.get("/api/danisma/yonetim/ogrenciler")
def danisma_yonetim_ogrencileri(
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    conn = None
    cursor = None

    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ogrenci_id, ad_soyad, ogrenci_numarasi, tur::text
            FROM ogrenciler
            WHERE aktif_mi = TRUE
              AND tur::text = 'DANISMA_MASASI'
            ORDER BY ad_soyad, ogrenci_numarasi;
        """)

        ogrenciler = [
            {
                "ogrenci_id": ogrenci_id,
                "ad_soyad": ad_soyad,
                "ogrenci_numarasi": ogrenci_numarasi,
                "tur": tur,
                "tur_etiketi": OGRENCI_TUR_ETIKETLERI.get(tur)
            }
            for ogrenci_id, ad_soyad, ogrenci_numarasi, tur
            in cursor.fetchall()
        ]

        return {"ogrenciler": ogrenciler}

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Öğrenci listesi alınamadı."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.post("/api/danisma/yonetim/oturumlar", status_code=201)
def danisma_yonetim_oturum_olustur(
    veri: DanismaGorevOlusturModeli,
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    conn = None
    cursor = None

    try:
        # Önce tarih ve saatleri doğrula.
        if veri.bitis_zamani <= veri.baslangic_zamani:
            raise HTTPException(
                status_code=422,
                detail="Bitiş zamanı başlangıçtan sonra olmalıdır."
            )

        if danisma_gorevi_cok_uzun_mu(veri.baslangic_zamani, veri.bitis_zamani):
            raise HTTPException(
                status_code=422,
                detail=DANISMA_GOREV_COK_UZUN_MESAJI
            )

        if veri.bitis_zamani > datetime.now():
            raise HTTPException(
                status_code=422,
                detail="Gelecekte biten görev kaydı oluşturulamaz."
            )

        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Öğrenci kaydını kilitleyerek eşzamanlı
        # görev ekleme işlemlerini sıraya al. Görev yalnızca danışma masası öğrencisine girilebilir.
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE ogrenci_id = %s
              AND aktif_mi = TRUE
              AND tur::text = 'DANISMA_MASASI'
            FOR UPDATE;
        """, (veri.ogrenci_id,))

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Aktif danışma masası öğrencisi bulunamadı."
            )

        # Aynı öğrencinin görevleriyle zaman çakışması.
        # Açık görevlerde bitiş zamanı henüz bilinmediğinden
        # bitişi sonsuz kabul ediyoruz.
        cursor.execute("""
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND baslangic_zamani < %s
              AND (
                  bitis_zamani IS NULL
                  OR bitis_zamani > %s
              )
            LIMIT 1;
        """, (
            veri.ogrenci_id,
            veri.bitis_zamani,
            veri.baslangic_zamani
        ))

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Öğrencinin bu saatlerle çakışan görevi var."
            )

        cursor.execute("""
            INSERT INTO danisma_masasi_oturumlari
                (
                    ogrenci_id,
                    baslangic_zamani,
                    bitis_zamani,
                    onaylandi_mi
                )
            VALUES (%s, %s, %s, FALSE)
            RETURNING oturum_id;
        """, (
            veri.ogrenci_id,
            veri.baslangic_zamani,
            veri.bitis_zamani
        ))

        oturum_id = cursor.fetchone()[0]

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="CREATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={
                "yeni": {
                    "ogrenci_id": veri.ogrenci_id,
                    "baslangic_zamani": veri.baslangic_zamani.isoformat(sep=" ", timespec="minutes"),
                    "bitis_zamani": veri.bitis_zamani.isoformat(sep=" ", timespec="minutes"),
                }
            }
        )

        conn.commit()

        return {
            "durum": "basarili",
            "mesaj": "Danışma masası görevi oluşturuldu.",
            "oturum_id": oturum_id,
            "onaylandi_mi": False
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
            detail="Görev oluşturulurken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


@app.patch("/api/danisma/yonetim/oturumlar/{oturum_id}")
def danisma_yonetim_oturum_duzenle(
    oturum_id: int,
    veri: DanismaGorevDuzenleModeli,
    kullanici_id: int = Depends(
        izin_kontrol("DANISMA_OTURUMU_YONETIM")
    )
):
    conn = None
    cursor = None

    try:
        # Tarih-saat doğrulamaları
        baslangic = veri.baslangic_zamani
        bitis = veri.bitis_zamani

        if baslangic.tzinfo is not None or bitis.tzinfo is not None:
            raise HTTPException(
                status_code=422,
                detail="Tarih ve saatler yerel saat biçiminde olmalıdır."
            )

        if bitis <= baslangic:
            raise HTTPException(
                status_code=422,
                detail="Bitiş zamanı başlangıçtan sonra olmalıdır."
            )

        if danisma_gorevi_cok_uzun_mu(baslangic, bitis):
            raise HTTPException(
                status_code=422,
                detail=DANISMA_GOREV_COK_UZUN_MESAJI
            )

        if bitis > datetime.now():
            raise HTTPException(
                status_code=422,
                detail="Gelecekte biten görev kaydı oluşturulamaz."
            )

        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Önce görevin hangi öğrenciye ait olduğunu belirle.
        cursor.execute("""
            SELECT ogrenci_id
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s;
        """, (oturum_id,))

        sonuc = cursor.fetchone()

        if sonuc is None:
            raise HTTPException(
                status_code=404,
                detail="Düzenlenecek görev bulunamadı."
            )

        ogrenci_id = sonuc[0]

        # Diğer görev işlemleriyle eşzamanlı değişiklikleri
        # sıraya almak için öğrenci kaydını kilitle.
        cursor.execute("""
            SELECT ogrenci_id
            FROM ogrenciler
            WHERE ogrenci_id = %s
            FOR UPDATE;
        """, (ogrenci_id,))

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Öğrenci kaydı bulunamadı."
            )

        # Düzenlenecek görev kaydını kilitle.
        cursor.execute("""
            SELECT baslangic_zamani, bitis_zamani, onaylandi_mi
            FROM danisma_masasi_oturumlari
            WHERE oturum_id = %s
              AND ogrenci_id = %s
            FOR UPDATE;
        """, (oturum_id, ogrenci_id))

        oturum = cursor.fetchone()

        if oturum is None:
            raise HTTPException(
                status_code=404,
                detail="Düzenlenecek görev bulunamadı."
            )

        eski_baslangic, eski_bitis, onaylandi_mi = oturum

        if eski_bitis is None:
            raise HTTPException(
                status_code=409,
                detail="Devam eden görev düzenlenemez."
            )

        if onaylandi_mi:
            raise HTTPException(
                status_code=409,
                detail="Onaylanmış görev düzenlenemez. Önce onayı geri alın."
            )

        # Diğer görevlerle çakışma var mı?
        # Düzenlediğimiz kaydı kontrol dışında tutuyoruz.
        cursor.execute("""
            SELECT oturum_id
            FROM danisma_masasi_oturumlari
            WHERE ogrenci_id = %s
              AND oturum_id <> %s
              AND baslangic_zamani < %s
              AND (
                  bitis_zamani IS NULL
                  OR bitis_zamani > %s
              )
            LIMIT 1;
        """, (
            ogrenci_id,
            oturum_id,
            bitis,
            baslangic
        ))

        if cursor.fetchone() is not None:
            raise HTTPException(
                status_code=409,
                detail="Öğrencinin bu saatlerle çakışan görevi var."
            )

        # Görev saatlerini güncelle.
        cursor.execute("""
            UPDATE danisma_masasi_oturumlari
            SET baslangic_zamani = %s,
                bitis_zamani = %s
            WHERE oturum_id = %s;
        """, (baslangic, bitis, oturum_id))

        # Audit kaydı aynı transaction içinde tutulur: görev saatlerinin önceki ve yeni hali.
        def _saat(deger):
            return deger.isoformat(sep=" ", timespec="minutes")

        denetim_kaydi_olustur(
            VT_AYARLARI,
            olay_turu="UPDATE",
            kullanici_id=kullanici_id,
            hedef_tablo="danisma_masasi_oturumlari",
            hedef_kayit_id=oturum_id,
            mevcut_cursor=cursor,
            ayrinti={
                "onceki": {"baslangic_zamani": _saat(eski_baslangic), "bitis_zamani": _saat(eski_bitis)},
                "yeni": {"baslangic_zamani": _saat(baslangic), "bitis_zamani": _saat(bitis)},
            }
        )

        conn.commit()

        toplam_saniye = int(
            (bitis - baslangic).total_seconds()
        )

        return {
            "durum": "basarili",
            "mesaj": "Danışma masası görevi güncellendi.",
            "oturum_id": oturum_id,
            "baslangic_zamani": baslangic.isoformat(),
            "bitis_zamani": bitis.isoformat(),
            "toplam_saniye": toplam_saniye
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
            detail="Görev düzenlenirken bir hata oluştu."
        )

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()



BIRIM_ADI_KAYITLI_MESAJI = "Bu birim adı zaten mevcut (büyük/küçük harf farkı aynı ad sayılır)."


@app.post("/api/faaliyet-birimleri")
def faaliyet_birimi_ekle(kayit: FaaliyetBirimIslemModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_BIRIMI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        # Birim adları büyük harfle saklanır; tekrar kontrolü de aynı biçimle yapılır.
        ad = kayit.birim_adi.strip().upper()
        if not ad:
            raise HTTPException(status_code=422, detail="Birim adı boş olamaz.")
        cursor.execute("SELECT birim_id FROM faaliyet_birimleri WHERE birim_adi = %s", (ad,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)

        cursor.execute(
            "INSERT INTO faaliyet_birimleri (birim_adi) VALUES (%s) RETURNING birim_id;",
            (ad,)
        )
        yeni_id = cursor.fetchone()[0]

        # Audit Log (Denetim Kaydı)
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", yetkili_id, "faaliyet_birimleri", yeni_id, mevcut_cursor=cursor)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Birim başarıyla eklendi.", "id": yeni_id}
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        # Kontrol ile kayıt arasında aynı adı başka bir istek eklediyse.
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.put("/api/faaliyet-birimleri/{birim_id}")
def faaliyet_birimi_guncelle(birim_id: int, kayit: FaaliyetBirimIslemModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_BIRIMI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        ad = kayit.birim_adi.strip().upper()
        if not ad:
            raise HTTPException(status_code=422, detail="Birim adı boş olamaz.")

        cursor.execute("SELECT birim_adi FROM faaliyet_birimleri WHERE birim_id = %s FOR UPDATE", (birim_id,))
        eski = cursor.fetchone()
        if not eski:
            raise HTTPException(status_code=404, detail="Güncellenecek birim bulunamadı.")
        eski_ad = eski[0]
        if eski_ad == ad:
            conn.commit()
            return {"durum": "basarili", "mesaj": "Birimde değişiklik yapılmadı."}

        cursor.execute("SELECT 1 FROM faaliyet_birimleri WHERE birim_adi = %s AND birim_id <> %s", (ad, birim_id))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)

        cursor.execute("UPDATE faaliyet_birimleri SET birim_adi = %s WHERE birim_id = %s;", (ad, birim_id))

        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(
            VT_AYARLARI, "UPDATE", yetkili_id, "faaliyet_birimleri", birim_id, mevcut_cursor=cursor,
            ayrinti={"onceki": {"birim_adi": eski_ad}, "yeni": {"birim_adi": ad}},
        )

        conn.commit()
        return {"durum": "basarili", "mesaj": "Birim başarıyla güncellendi."}
    except HTTPException:
        raise
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=400, detail=BIRIM_ADI_KAYITLI_MESAJI)
    except Exception:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="İşlem sırasında beklenmeyen bir sunucu hatası oluştu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.delete("/api/faaliyet-birimleri/{birim_id}")
def faaliyet_birimi_sil(birim_id: int, yetkili_id: int = Depends(izin_kontrol("FAALIYET_BIRIMI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = vt_baglan(VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM ogrenci_faaliyet_takip WHERE birim_id = %s LIMIT 1", (birim_id,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="DİKKAT: Bu birim geçmiş faaliyet kayıtlarında kullanıldığı için SİLİNEMEZ! İsterseniz adını güncelleyebilirsiniz.")

        silinen = satiri_sil_ve_ayrintisini_al(cursor, "faaliyet_birimleri", birim_id)
        from server.denetim import denetim_kaydi_olustur
        denetim_kaydi_olustur(VT_AYARLARI, "DELETE", yetkili_id, "faaliyet_birimleri", birim_id,
                              mevcut_cursor=cursor, ayrinti=silinen)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Birim başarıyla silindi."}
    except HTTPException:
        raise
    except Exception:
        if conn is not None: conn.rollback()
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


# ==========================================================
# FAALIYET TURLERI YONETIMI
# ==========================================================

from pydantic import BaseModel as _FaaliyetBaseModel
from pydantic import Field as _FaaliyetField


# Faaliyet puanı üst sınırı: puan x miktar (en çok 10.000) çarpımı veritabanındaki INTEGER sınırını aşmasın.
FAALIYET_PUANI_EN_FAZLA = 10_000


class FaaliyetTuruEkleModeli(_FaaliyetBaseModel):
    faaliyet_adi: str = _FaaliyetField(
        min_length=1, max_length=100
    )
    puan: int = _FaaliyetField(
        ge=0, le=FAALIYET_PUANI_EN_FAZLA, strict=True
    )


FAALIYET_ADI_KAYITLI_MESAJI = "Bu adla bir faaliyet türü zaten kayıtlı (büyük/küçük harf farkı aynı ad sayılır)."


def _faaliyet_adi_kayitli_mi(cursor, ad, haric_id=None):
    """Aynı ad (büyük/küçük harf ve baş/son boşluk farkı gözetmeden) başka bir faaliyet türünde var mı?

    Pasif türler de sayılır: veritabanındaki benzersizlik kuralı onları da kapsar. Kontrol ile kayıt arasında başka bir
    isteğin aynı adı eklememesi için işlem boyunca tek bir kilit alınır."""
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext('TKYS_FAALIYET_ADI'));")
    cursor.execute(
        "SELECT faaliyet_id FROM faaliyetler "
        "WHERE LOWER(BTRIM(faaliyet_adi)) = LOWER(%s) AND faaliyet_id <> %s;",
        (ad, haric_id if haric_id is not None else 0),
    )
    return len(list(cursor.fetchall())) > 0


@app.post("/api/faaliyetler", status_code=201)
def faaliyet_turu_ekle(
    veri: FaaliyetTuruEkleModeli,
    yetkili_id: int = Depends(
        izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")
    )
):
    ad = veri.faaliyet_adi.strip()

    if not ad:
        raise HTTPException(
            status_code=422,
            detail="Faaliyet adı boş olamaz."
        )

    conn = None

    try:
        conn = vt_baglan(VT_AYARLARI)

        with conn.cursor() as cursor:
            if _faaliyet_adi_kayitli_mi(cursor, ad):
                raise HTTPException(status_code=409, detail=FAALIYET_ADI_KAYITLI_MESAJI)

            cursor.execute("""
                INSERT INTO faaliyetler
                    (faaliyet_adi, puan, aktif_mi)
                VALUES (%s, %s, TRUE)
                RETURNING faaliyet_id;
            """, (ad, veri.puan))

            yeni_id = cursor.fetchone()[0]

            from server.denetim import denetim_kaydi_olustur

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "CREATE",
                yetkili_id,
                "faaliyetler",
                yeni_id,
                mevcut_cursor=cursor
            )

        conn.commit()

        return {
            "durum": "basarili",
            "id": yeni_id,
            "ad": ad,
            "puan": veri.puan
        }

    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu faaliyet türü zaten kayıtlı."
        )

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Faaliyet türü eklenemedi."
        )

    finally:
        if conn:
            conn.close()




class FaaliyetTuruDuzenleModeli(_FaaliyetBaseModel):
    faaliyet_adi: str = _FaaliyetField(
        min_length=1, max_length=100
    )
    puan: int = _FaaliyetField(
        ge=0, le=FAALIYET_PUANI_EN_FAZLA, strict=True
    )
    gecmis_puanlari_guncelle: bool = _FaaliyetField(
        strict=True
    )


@app.put("/api/faaliyetler/{faaliyet_id}")
def faaliyet_turu_duzenle(
    faaliyet_id: int,
    veri: FaaliyetTuruDuzenleModeli,
    yetkili_id: int = Depends(
        izin_kontrol("FAALIYET_KAYITLARI_DUZENLE")
    )
):
    ad = veri.faaliyet_adi.strip()

    if not ad:
        raise HTTPException(
            status_code=422,
            detail="Faaliyet adı boş olamaz."
        )

    conn = None

    try:
        conn = vt_baglan(VT_AYARLARI)

        with conn.cursor() as cursor:

            # Aynı faaliyet üzerinde eşzamanlı değişiklikleri
            # transaction tamamlanana kadar kilitle.
            cursor.execute("""
                SELECT faaliyet_adi, puan
                FROM faaliyetler
                WHERE faaliyet_id = %s
                  AND aktif_mi = TRUE
                FOR UPDATE;
            """, (faaliyet_id,))

            eski = cursor.fetchone()

            if eski is None:
                raise HTTPException(
                    status_code=404,
                    detail="Aktif faaliyet türü bulunamadı."
                )

            eski_ad, eski_puan = eski
            puan_degisti = eski_puan != veri.puan

            # Kayıt değişmemişse gereksiz audit oluşturma.
            if eski_ad == ad and not puan_degisti:
                conn.commit()
                return {
                    "durum": "degisiklik_yok",
                    "id": faaliyet_id,
                    "ad": ad,
                    "puan": veri.puan,
                    "guncellenen_gecmis_kayit": 0
                }

            if eski_ad != ad and _faaliyet_adi_kayitli_mi(cursor, ad, haric_id=faaliyet_id):
                raise HTTPException(status_code=409, detail=FAALIYET_ADI_KAYITLI_MESAJI)

            cursor.execute("""
                UPDATE faaliyetler
                SET faaliyet_adi = %s,
                    puan = %s
                WHERE faaliyet_id = %s;
            """, (ad, veri.puan, faaliyet_id))

            etkilenen = 0

            # Yalnızca puan değişmişse VE kullanıcı açıkça
            # geçmişi güncelle demişse geçmişe dokun.
            if (
                puan_degisti
                and veri.gecmis_puanlari_guncelle
            ):
                cursor.execute("""
                    UPDATE ogrenci_faaliyet_takip
                    SET kayit_puani = %s
                    WHERE faaliyet_id = %s
                      AND kayit_puani <> %s;
                """, (
                    veri.puan,
                    faaliyet_id,
                    veri.puan
                ))

                etkilenen = cursor.rowcount

            from server.denetim import denetim_kaydi_olustur

            # Denetim kaydı: ad ve puanın önceki/yeni değeri; geçmiş kayıtlara uygulandıysa kaç kayıt etkilendiği.
            degisiklik = {"onceki": {}, "yeni": {}}
            if eski_ad != ad:
                degisiklik["onceki"]["faaliyet_adi"] = eski_ad
                degisiklik["yeni"]["faaliyet_adi"] = ad
            if puan_degisti:
                degisiklik["onceki"]["puan"] = eski_puan
                degisiklik["yeni"]["puan"] = veri.puan
                degisiklik["gecmis_kayitlara_uygulandi"] = bool(veri.gecmis_puanlari_guncelle)
                degisiklik["guncellenen_gecmis_kayit"] = etkilenen

            denetim_kaydi_olustur(
                VT_AYARLARI,
                "UPDATE",
                yetkili_id,
                "faaliyetler",
                faaliyet_id,
                mevcut_cursor=cursor,
                ayrinti=degisiklik
            )

            # Toplu geçmiş güncellemesini ayrıca işaretle.
            if etkilenen:
                denetim_kaydi_olustur(
                    VT_AYARLARI,
                    "UPDATE",
                    yetkili_id,
                    "ogrenci_faaliyet_takip",
                    None,
                    mevcut_cursor=cursor,
                    ayrinti={
                        "neden": "faaliyet puanı geçmiş kayıtlara uygulandı",
                        "faaliyet_id": faaliyet_id,
                        "onceki": {"faaliyet_puani": eski_puan},
                        "yeni": {"faaliyet_puani": veri.puan},
                        "etkilenen_kayit": etkilenen,
                    }
                )

        conn.commit()

        return {
            "durum": "basarili",
            "id": faaliyet_id,
            "ad": ad,
            "puan": veri.puan,
            "gecmis_puanlari_guncellendi": (
                puan_degisti
                and veri.gecmis_puanlari_guncelle
            ),
            "guncellenen_gecmis_kayit": etkilenen
        }

    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=409,
            detail="Bu faaliyet türü adı zaten kayıtlı."
        )

    except HTTPException:
        if conn:
            conn.rollback()
        raise

    except Exception:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Faaliyet türü güncellenemedi."
        )

    finally:
        if conn:
            conn.close()




# Oda Etkinlikleri API
from server.oda_etkinlikleri_api import router_olustur

app.include_router(router_olustur(izin_kontrol, VT_AYARLARI))

# Ayrılan modüller (server/sunucu.py'nin parçalanması): uçlar kendi dosyalarında; yetki bağımlılığı buradan verilir.
# Fonksiyon adları geriye dönük olarak burada da erişilebilir kalır (testler `server.sunucu.<ad>` ile içe aktarır).
from server import (
    anasayfa_api, audit_api, cihaz_raporlari_api, cihaz_uygunluk_api, danisma_raporlari_api, puan_raporu_api, randevu_oda_raporlari_api,
    surum_api, yonetim_raporlari_api,
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
