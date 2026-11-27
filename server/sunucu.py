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
from pydantic import BaseModel as _DurumBaseModel, Field as _DurumField
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


from server.ortak_sabitler import CIHAZ_ODALARI_SORGUSU, ETKIN_CIHAZ_DURUMU_SQL, OGRENCI_TUR_ETIKETLERI, PLANLI_RANDEVU_COZUMU
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


# --- server/sunucu.py parçalama: kullanıcı, rol, izin, personel, oda ve parola talebi uçları (kendi dosyalarında) ---
from server import kullanici_api, oda_api, parola_talebi_api, personel_api, rol_api  # noqa: E402
app.include_router(oda_api.router_olustur(izin_kontrol, izin_kontrol_tumu))
app.include_router(rol_api.router_olustur(izin_kontrol))
app.include_router(parola_talebi_api.router_olustur(izin_kontrol))
app.include_router(personel_api.router_olustur(izin_kontrol))
app.include_router(kullanici_api.router_olustur(izin_kontrol))
from server.oda_api import (  # noqa: E402  (geriye dönük adlar)
    OdaYetkileriModeli,
    psikolog_planli_randevulari_denetle,
    etkinlik_oda_atama_kilitlerini_al,
    oda_etkinlikli_odalari_denetle,
    cihaz_rezervasyonlu_odalari_denetle,
    _hedef_psikolog_kontrol,
    psikolog_oda_yetkilerini_getir,
    psikolog_oda_yetkilerini_guncelle,
    oda_planli_kayit_sayilari,
    oda_planli_randevu_sayilari,
    oda_psikolog_atamalari,
    oda_olustur,
    psikolog_odalarini_getir,
    odalari_listele,
    cihaz_odalarini_listele,
    oda_detay,
    oda_guncelle,
    aktif_psikologlari_listele,
)
from server.rol_api import (  # noqa: E402  (geriye dönük adlar)
    rol_olustur,
    SISTEM_ROLLERI,
    rol_guncelle,
    rol_sil,
    _atanabilir_rolleri_getir,
    olusturma_rolleri,
    degistirme_rolleri,
    rolleri_listele,
    rol_yetki_ozeti,
    rol_izin_matrisi_getir,
    izin_ekle,
    izin_duzenle,
)
from server.parola_talebi_api import (  # noqa: E402  (geriye dönük adlar)
    PAROLA_TALEBI_ACIK_UST_SINIR,
    PAROLA_TALEBI_ALINDI_MESAJI,
    PAROLA_TALEBI_ZATEN_VAR_MESAJI,
    PAROLA_TALEBI_KULLANICI_YOK_MESAJI,
    PAROLA_TALEBI_HESAP_PASIF_MESAJI,
    PAROLA_TALEBI_HESAP_YONETICI_MESAJI,
    parola_sifirlama_talebi_olustur,
    parola_sifirlama_taleplerini_listele,
    parola_sifirlama_talebini_kapat,
)
from server.personel_api import (  # noqa: E402  (geriye dönük adlar)
    personel_olustur,
    personel_listele,
    personel_olmayan_kullanicilari_listele,
    personel_detay,
    personel_guncelle,
)
from server.kullanici_api import (  # noqa: E402  (geriye dönük adlar)
    ROL_PASIF_ATAMA_MESAJI,
    _siradaki_personel_kodu,
    kullanici_olustur,
    musait_kullanici_adi,
    kullanici_ogrenci_kayit_durumu,
    kullanici_rol_degistir,
    YONETICI_PAROLASI_ENGEL_MESAJI,
    kullanici_parola_sifirla,
    DurumDegistirModeli,
    kullanici_durum_degistir,
)


# --- server/sunucu.py parçalama: randevu ve danışan kodu uçları (kendi dosyalarında) ---
from server import danisan_api, randevu_api  # noqa: E402
app.include_router(randevu_api.router_olustur(izin_kontrol))
app.include_router(danisan_api.router_olustur(izin_kontrol))
from server.randevu_api import (  # noqa: E402  (geriye dönük adlar)
    psikolog_odasina_atanmis_mi,
    randevu_deadlock_yeniden_dene,
    randevu_olustur,
    RANDEVU_LISTE_SUTUNLARI,
    RANDEVU_LISTE_ENCOK,
    randevulari_listele,
    danisan_randevu_sayilari,
    HAFTA_SONU_MESAJI,
    hafta_sonuna_denk_mi,
    GECMIS_TARIH_MESAJI,
    gecmis_tarihe_mi,
    DANISAN_PSIKOLOG_MESAJI,
    danisan_psikologa_ait_mi,
    randevu_taraflarini_denetle,
    randevu_doluluk,
    randevu_guncelle,
    randevu_iptal_et,
    randevu_durumunu_isaretle,
)
from server.danisan_api import (  # noqa: E402  (geriye dönük adlar)
    otomatik_danisan_kodu_uret,
    siradaki_danisan_kodunu_ver,
    IZINLI_ISTISNA_TURLERI,
    danisan_kodu_olustur,
    danisan_kodlari_listele,
    danisan_durumunu_degistir,
    danisan_bilgilerini_guncelle,
)


# --- server/sunucu.py parçalama: öğrenci yönetimi uçları (kendi dosyasında) ---
from server import ogrenci_api  # noqa: E402
app.include_router(ogrenci_api.router_olustur(izin_kontrol))
from server.ogrenci_api import (  # noqa: E402  (geriye dönük adlar)
    ogrencileri_getir,
    OgrenciAktiflikModeli,
    OgrenciErteleModeli,
    OgrenciSilOnayModeli,
    ogrenciler_yonetim_listesi,
    ogrenci_puan_detayi,
    _ogrenci_saklama_suresi_kontrol,
    ogrenci_silme_ertele,
    ogrenci_saklama_suresi_sil,
    ogrenci_aktiflik_duzenle,
    ogrenci_ekle,
)


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
