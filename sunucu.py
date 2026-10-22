from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.errors import ExclusionViolation, DeadlockDetected
import os
import time
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
from modeller import (
    GirisModeli,
    RolDegistirModeli,
    KullaniciOlusturModeli,
    PersonelOlusturModeli,
    PersonelGuncelleModeli,
    SifreDegistirModeli,
    RandevuOlusturModeli,
    RandevuGuncelleModeli,
    DanisanKoduModeli,
    OdaOlusturModeli,
    OdaGuncelleModeli,
    CihazOlusturModeli,
    CihazGuncelleModeli,
    RezervasyonOlusturModeli,
    ArizaBildirimModeli,
    ArizaGuncelleModeli,
    KalibrasyonOlusturModeli,
    KalibrasyonGuncelleModeli,
    BakimOlusturModeli,
    BakimGuncelleModeli,
    FaaliyetKayitModeli
)
from guvenlik import (
    parola_hashle,
    parola_dogrula,
    gecici_parola_uret,
    access_token_olustur,
    token_dogrula
)
from denetim import denetim_kaydi_olustur

load_dotenv()
app = FastAPI()
bearer_scheme = HTTPBearer()

VT_AYARLARI = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

def otomatik_danisan_kodu_uret(cursor) -> str:
    yil = datetime.now().year
    cursor.execute("SELECT nextval('danisan_kodu_seq');")
    sira = cursor.fetchone()[0]
    return f"DAN-{yil}-{sira:04d}"

def token_kullanici_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> int:
    try:
        return token_dogrula(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token.")

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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT aktif_mi, ilk_giris_mi FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[0]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
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
            conn = psycopg2.connect(**VT_AYARLARI)
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

@app.get("/api/korumali-test")
def korumali_test(kullanici_id: int = Depends(mevcut_kullanici_id)):
    return {"durum": "basarili", "mesaj": "Token geçerli.", "kullanici_id": kullanici_id}

@app.post("/api/login")
def giris_yap(giris: GirisModeli):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT kullanici_id, kullanici_adi, parola_hash, rol_id, aktif_mi,
                   basarisiz_giris_sayisi, kilit_bitis_zamani, ilk_giris_mi
            FROM kullanicilar WHERE kullanici_adi = %s;
            """, (giris.kullanici_adi,)
        )
        kullanici = cursor.fetchone()

        if kullanici is None:
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", hedef_tablo="kullanicilar")
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya parola hatalı.")
        if not kullanici[4]:
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
        if kullanici[6] is not None and kullanici[6] > datetime.now():
            raise HTTPException(status_code=429, detail="Çok fazla hatalı giriş denemesi. Lütfen daha sonra tekrar deneyin.")

        if not parola_dogrula(giris.parola, kullanici[2]):
            yeni_basarisiz_giris_sayisi = kullanici[5] + 1
            if yeni_basarisiz_giris_sayisi >= 5:
                kilit_bitis_zamani = datetime.now() + timedelta(minutes=15)
                cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = %s, kilit_bitis_zamani = %s WHERE kullanici_id = %s;", (yeni_basarisiz_giris_sayisi, kilit_bitis_zamani, kullanici[0]))
            else:
                cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = %s WHERE kullanici_id = %s;", (yeni_basarisiz_giris_sayisi, kullanici[0]))
            conn.commit()
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            if yeni_basarisiz_giris_sayisi >= 5:
                raise HTTPException(status_code=429, detail="Çok fazla hatalı giriş denemesi. Hesap 15 dakika kilitlendi.")
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya parola hatalı.")

        cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = 0, kilit_bitis_zamani = NULL WHERE kullanici_id = %s;", (kullanici[0],))
        conn.commit()
        access_token = access_token_olustur(kullanici[0])

        cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici[0],))
        pers = cursor.fetchone()
        personel_id = pers[0] if pers else None

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
            "sifre_degistirme_gerekli": kullanici[7]
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/sifre-degistir")
def sifre_degistir(veri: SifreDegistirModeli, kullanici_id: int = Depends(token_kullanici_id)):
    if veri.yeni_parola != veri.yeni_parola_tekrar:
        raise HTTPException(status_code=422, detail="Yeni şifreler birbiriyle eşleşmiyor.")
    if len(veri.yeni_parola.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Yeni şifre en fazla 72 bayt olabilir.")
    if veri.eski_parola == veri.yeni_parola:
        raise HTTPException(status_code=422, detail="Yeni şifre eski şifreyle aynı olamaz.")

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT parola_hash, aktif_mi FROM kullanicilar WHERE kullanici_id = %s FOR UPDATE;", (kullanici_id,))
        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[1]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
        if not parola_dogrula(veri.eski_parola, kullanici[0]):
            raise HTTPException(status_code=401, detail="Eski şifre hatalı.")

        yeni_hash = parola_hashle(veri.yeni_parola)
        cursor.execute("UPDATE kullanicilar SET parola_hash = %s, ilk_giris_mi = FALSE WHERE kullanici_id = %s;", (yeni_hash, kullanici_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Şifreniz başarıyla değiştirildi."}
    except Exception:
        if conn is not None: conn.rollback()
        raise
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# ADM MODÜLÜ (Kullanıcı, Rol ve Personel)
# ==========================================

@app.post("/api/kullanicilar", status_code=201)
def kullanici_olustur(yeni_kullanici: KullaniciOlusturModeli, kullanici_id: int = Depends(izin_kontrol("KULLANICI_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        yapan = cursor.fetchone()

        cursor.execute(
            """
            SELECT 1 FROM kullanicilar k JOIN rol_izinleri ri ON k.rol_id = ri.rol_id JOIN izinler i ON ri.izin_id = i.izin_id
            WHERE k.kullanici_id = %s AND i.izin_adi = 'ROL_ATAMA_DEGISTIRME' AND ri.izin_var = 1;
            """, (kullanici_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=403, detail="Rol atama yetkiniz bulunmuyor.")

        cursor.execute("SELECT rol_adi FROM roller WHERE rol_id = %s;", (yeni_kullanici.rol_id,))
        hedef_rol = cursor.fetchone()
        if hedef_rol is None:
            raise HTTPException(status_code=422, detail="Geçersiz rol seçildi.")

        if hedef_rol[0] == "ADMIN" and (yapan is None or yapan[0] != "ADMIN"):
            raise HTTPException(status_code=403, detail="ADMIN rolünü atama yetkiniz bulunmuyor.")

        gecici_parola = gecici_parola_uret()
        parola_hash = parola_hashle(gecici_parola)

        cursor.execute(
            "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi) VALUES (%s, %s, %s, TRUE, TRUE) RETURNING kullanici_id;",
            (yeni_kullanici.kullanici_adi, parola_hash, yeni_kullanici.rol_id)
        )
        yeni_id = cursor.fetchone()[0]
        conn.commit()

        return {
            "durum": "basarili",
            "kullanici_id": yeni_id,
            "kullanici_adi": yeni_kullanici.kullanici_adi,
            "gecici_parola": gecici_parola,
            "ilk_giris_mi": True
        }
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten kullanılıyor.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()
        if islem_yapan is None:
            raise HTTPException(status_code=403, detail="Yetkisiz işlem.")
        islem_yapan_rol = islem_yapan[0]

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef_kullanici = cursor.fetchone()
        if hedef_kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
        mevcut_rol = hedef_kullanici[0]

        cursor.execute("SELECT rol_adi FROM roller WHERE rol_id = %s;", (veri.rol_id,))
        yeni_rol = cursor.fetchone()
        if yeni_rol is None:
            raise HTTPException(status_code=404, detail="Atanacak rol bulunamadı.")
        yeni_rol_adi = yeni_rol[0]

        if islem_yapan_rol != "ADMIN":
            if mevcut_rol == "ADMIN" or yeni_rol_adi == "ADMIN":
                raise HTTPException(status_code=403, detail="ADMIN rolünü yalnızca ADMIN yönetebilir.")

        cursor.execute("UPDATE kullanicilar SET rol_id = %s WHERE kullanici_id = %s;", (veri.rol_id, kullanici_id))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "ROLE_CHANGE", "kullanicilar", kullanici_id))
        conn.commit()

        return {"mesaj": "Kullanıcı rolü başarıyla değiştirildi.", "kullanici_id": kullanici_id, "yeni_rol_id": veri.rol_id, "yeni_rol_adi": yeni_rol_adi}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/kullanicilar/{kullanici_id}/pasiflestir")
def kullanici_pasiflestir(kullanici_id: int, islem_yapan_id: int = Depends(izin_kontrol("KULLANICI_PASIFLESTIR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        if kullanici_id == islem_yapan_id:
            raise HTTPException(status_code=403, detail="Kendi hesabınızı pasifleştiremezsiniz.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()
        if islem_yapan is None:
            raise HTTPException(status_code=403, detail="Yetkisiz işlem.")

        cursor.execute("SELECT r.rol_adi, k.aktif_mi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef = cursor.fetchone()
        if hedef is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

        hedef_rol, aktif_mi = hedef
        if hedef_rol == "ADMIN" and islem_yapan[0] != "ADMIN":
            raise HTTPException(status_code=403, detail="ADMIN hesabını yalnızca ADMIN pasifleştirebilir.")
        if not aktif_mi:
            raise HTTPException(status_code=409, detail="Kullanıcı zaten pasif durumda.")

        cursor.execute("UPDATE kullanicilar SET aktif_mi = FALSE WHERE kullanici_id = %s;", (kullanici_id,))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "UPDATE", "kullanicilar", kullanici_id))
        conn.commit()

        return {"mesaj": "Kullanıcı başarıyla pasifleştirildi.", "kullanici_id": kullanici_id, "aktif_mi": False}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Kullanıcı pasifleştirme sırasında veritabanı hatası oluştu: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/personel", status_code=201)
def personel_olustur(yeni_personel: PersonelOlusturModeli, islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT k.aktif_mi, r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (yeni_personel.kullanici_id,))
        kullanici = cursor.fetchone()
        if kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı hesabı bulunamadı.")
        if not kullanici[0]:
            raise HTTPException(status_code=422, detail="Pasif kullanıcı için personel kaydı oluşturulamaz.")

        cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id;", (yeni_personel.kullanici_id, yeni_personel.personel_kodu.strip()))
        personel_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "CREATE", "personel", personel_id))
        conn.commit()

        return {
            "mesaj": "Personel başarıyla oluşturuldu.",
            "personel_id": personel_id,
            "kullanici_id": yeni_personel.kullanici_id,
            "personel_kodu": yeni_personel.personel_kodu.strip(),
            "aktif_mi": True
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu kullanıcıya ait personel kaydı veya personel kodu zaten mevcut.")
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Personel oluşturulurken veritabanı hatası oluştu: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/personel")
def personel_listele(islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, p.kullanici_id, k.kullanici_adi, p.personel_kodu, r.rol_adi, p.aktif_mi, p.olusturulma_tarihi
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id ORDER BY p.personel_id;
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "kullanici_id": k[1], "kullanici_adi": k[2], "personel_kodu": k[3], "rol_adi": k[4], "aktif_mi": k[5], "olusturulma_tarihi": k[6]} for k in kayitlar]
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
        conn = psycopg2.connect(**VT_AYARLARI)
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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT personel_id, personel_kodu, aktif_mi FROM personel WHERE personel_id = %s FOR UPDATE;", (personel_id,))
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Personel bulunamadı.")

        yeni_kod = degisiklikler.get("personel_kodu", mevcut[1])
        yeni_aktiflik = degisiklikler.get("aktif_mi", mevcut[2])

        cursor.execute("UPDATE personel SET personel_kodu = %s, aktif_mi = %s WHERE personel_id = %s;", (yeni_kod, yeni_aktiflik, personel_id))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "UPDATE", "personel", personel_id))
        conn.commit()
        return {"mesaj": "Personel başarıyla güncellendi.", "personel_id": personel_id, "personel_kodu": yeni_kod, "aktif_mi": yeni_aktiflik}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu personel kodu başka bir kayıtta kullanılıyor.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# RANDEVU & ODA MODÜLÜ
# ==========================================
@app.get("/api/randevular/siradaki-kod")
def siradaki_danisan_kodunu_ver(kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        siradaki_kod = otomatik_danisan_kodu_uret(cursor)
        return {"siradaki_kod": siradaki_kod}
    except Exception:
        yil = datetime.now().year
        return {"siradaki_kod": f"DAN-{yil}-0001"}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/randevular", status_code=201)
def randevu_olustur(randevu: RandevuOlusturModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    if randevu.baslangic_zamani >= randevu.bitis_zamani:
        raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol is not None and rol[0] == "PSIKOLOG":
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu.psikolog_id:
                raise HTTPException(status_code=403, detail="Yalnızca kendi adınıza randevu oluşturabilirsiniz.")

        yeni_danisan_kodu = otomatik_danisan_kodu_uret(cursor)
        cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi) VALUES (%s, TRUE, 'YOK', TRUE);", (yeni_danisan_kodu,))

        cursor.execute("SELECT 1 FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND r.rol_adi = 'PSIKOLOG';", (randevu.psikolog_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")

        cursor.execute("SELECT 1 FROM odalar WHERE oda_id = %s AND aktif_mi = TRUE;", (randevu.oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Oda bulunamadı veya aktif değil.")

        cursor.execute("SELECT 1 FROM randevular WHERE durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu.psikolog_id, randevu.oda_id, randevu.bitis_zamani, randevu.baslangic_zamani))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        cursor.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) VALUES (%s, %s, %s, %s, %s, 'PLANLANDI') RETURNING randevu_id;", (yeni_danisan_kodu, randevu.psikolog_id, randevu.oda_id, randevu.baslangic_zamani, randevu.bitis_zamani))
        randevu_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "randevular", randevu_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu oluşturuldu.", "randevu_id": randevu_id}
    except ExclusionViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/randevular")
def randevulari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is None or rol[0] not in ("PSIKOLOG", "ADMIN", "DANISMA_OGRENCISI"):
            raise HTTPException(status_code=403, detail="Randevuları görüntüleme yetkiniz yok.")

        cursor.execute("SELECT randevu_id, danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum FROM randevular ORDER BY baslangic_zamani;")
        kayitlar = cursor.fetchall()
        return [{"randevu_id": kayit[0], "danisan_kod_id": kayit[1], "psikolog_id": kayit[2], "oda_id": kayit[3], "baslangic_zamani": kayit[4], "bitis_zamani": kayit[5], "durum": kayit[6]} for kayit in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/randevular/{randevu_id}")
def randevu_guncelle(randevu_id: int, guncelleme: RandevuGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")
        if mevcut[5] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Yalnızca planlanmış randevular güncellenebilir.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol[0] == "PSIKOLOG":
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

        if rol[0] == "PSIKOLOG" and psikolog_id != mevcut[1]:
            raise HTTPException(status_code=403, detail="Randevuyu başka psikoloğa devredemezsiniz.")
        if baslangic >= bitis:
            raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")

        cursor.execute("SELECT 1 FROM randevular WHERE randevu_id != %s AND durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu_id, psikolog_id, oda_id, bitis, baslangic))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        cursor.execute("UPDATE randevular SET danisan_kod_id = %s, psikolog_id = %s, oda_id = %s, baslangic_zamani = %s, bitis_zamani = %s WHERE randevu_id = %s;", (danisan_kod_id, psikolog_id, oda_id, baslangic, bitis, randevu_id))
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
def randevu_iptal_et(randevu_id: int, kullanici_id: int = Depends(izin_kontrol("RANDEVU_IPTAL"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT psikolog_id, durum FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        randevu = cursor.fetchone()
        if randevu is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol[0] == "PSIKOLOG":
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzu iptal edebilirsiniz.")

        if randevu[1] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Bu randevu iptal edilemez.")

        cursor.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI' WHERE randevu_id = %s;", (randevu_id,))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CANCEL", "randevular", randevu_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu iptal edildi.", "randevu_id": randevu_id}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/danisan-kodlari", status_code=201)
def danisan_kodu_olustur(ucretli_mi: bool = True, istisna_turu: str = "YOK", kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s AND k.aktif_mi = TRUE;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is None or rol[0] not in ("ADMIN", "PSIKOLOG", "DANISMA_OGRENCISI"):
            raise HTTPException(status_code=403, detail="Danışan kodu oluşturma yetkiniz yok.")

        yeni_kod = otomatik_danisan_kodu_uret(cursor)
        cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi) VALUES (%s, %s, %s, TRUE) RETURNING danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi, olusturulma_tarihi;", (yeni_kod, ucretli_mi, istisna_turu))
        kayit = cursor.fetchone()
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo) VALUES (%s, %s, %s);", (kullanici_id, "CREATE", "danisan_kodlari"))
        conn.commit()
        veri = DanisanKoduModeli(danisan_kod_id=kayit[0], ucretli_mi=kayit[1], istisna_turu=kayit[2], aktif_mi=kayit[3], olusturulma_tarihi=kayit[4])
        return {"durum": "basarili", "veri": veri.model_dump(mode="json")}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/odalar", status_code=201)
def oda_olustur(oda: OdaOlusturModeli, kullanici_id: int = Depends(izin_kontrol("ODA_EKLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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

@app.get("/api/odalar")
def odalari_listele():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar ORDER BY oda_id;")
        odalar = cursor.fetchall()
        return [{"oda_id": oda[0], "oda_adi": oda[1], "kapasite": oda[2], "aktif_mi": oda[3]} for oda in odalar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/odalar/{oda_id}")
def oda_detay(oda_id: int, kullanici_id: int = Depends(izin_kontrol("ODA_DURUMU_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = %s FOR UPDATE;", (oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")

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
def danisan_kodlari_listele(kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT danisan_kod_id, ucretli_mi, aktif_mi FROM danisan_kodlari WHERE aktif_mi = TRUE ORDER BY olusturulma_tarihi DESC;")
        kayitlar = cursor.fetchall()
        return [{"danisan_kod_id": k[0], "ucretli_mi": k[1], "aktif_mi": k[2]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/psikologlar")
def aktif_psikologlari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, k.kullanici_adi
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id
            WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "ad_soyad": k[1]} for k in kayitlar]
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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM cihazlar WHERE envanter_kodu = %s OR seri_no = %s;", (cihaz.envanter_kodu, cihaz.seri_no))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Bu envanter kodu veya seri no zaten kullanımda.")

        cursor.execute(
            "INSERT INTO cihazlar (envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum) VALUES (%s, %s, %s, %s, %s, %s) RETURNING cihaz_id;",
            (cihaz.envanter_kodu, cihaz.cihaz_adi, cihaz.marka_model, cihaz.seri_no, cihaz.zimmetli_oda_id, cihaz.durum.value)
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
        conn = psycopg2.connect(**VT_AYARLARI)
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

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.get("/api/cihazlar")
def cihazlari_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_UYGUNLUK_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum, kayit_tarihi FROM cihazlar ORDER BY cihaz_id;")
        kayitlar = cursor.fetchall()
        return [{"cihaz_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2], "marka_model": k[3], "seri_no": k[4], "zimmetli_oda_id": k[5], "durum": k[6], "kayit_tarihi": k[7]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/cihazlar/{cihaz_id}")
def cihaz_detayi_getir(cihaz_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_UYGUNLUK_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum, kayit_tarihi FROM cihazlar WHERE cihaz_id = %s;", (cihaz_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        return {"cihaz_id": kayit[0], "envanter_kodu": kayit[1], "cihaz_adi": kayit[2], "marka_model": kayit[3], "seri_no": kayit[4], "zimmetli_oda_id": kayit[5], "durum": kayit[6], "kayit_tarihi": kayit[7]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/rezervasyonlar", status_code=201)
def cihaz_rezervasyonu_yap(rez: RezervasyonOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    if rez.baslangic_zamani >= rez.bitis_zamani:
        raise HTTPException(status_code=422, detail="Bitiş zamanı, başlangıçtan sonra olmalıdır.")
    maksimum_deneme = 3
    for deneme in range(maksimum_deneme):
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute("SELECT durum FROM cihazlar WHERE cihaz_id = %s;", (rez.cihaz_id,))
            cihaz = cursor.fetchone()
            if cihaz is None:
                raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
            if cihaz[0] not in ["Kullanima_Hazir", "Rezerve"]:
                raise HTTPException(status_code=403, detail=f"Cihaz şu anda {cihaz[0]} durumunda olduğu için rezerve edilemez!")

            cursor.execute("SELECT 1 FROM cihaz_rezervasyonlari WHERE cihaz_id = %s AND iptal_edildi_mi = FALSE AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten başka bir iş için rezerve edilmiş.")

            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici_id,))
            pers = cursor.fetchone()
            personel_id = pers[0] if pers else None

            cursor.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, rezervasyonu_yapan_personel_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani, proje_turu, proje_adi_aciklamasi) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING rezervasyon_id;", (rez.cihaz_id, personel_id, rez.kullanilacak_oda_id, rez.baslangic_zamani, rez.bitis_zamani, rez.proje_turu, rez.proje_adi_aciklamasi))
            rez_id = cursor.fetchone()[0]

            cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "cihaz_rezervasyonlari", rez_id))
            conn.commit()
            return {"durum": "basarili", "mesaj": "Rezervasyon başarıyla oluşturuldu.", "rezervasyon_id": rez_id}
        except DeadlockDetected:
            if conn is not None: conn.rollback()
            if deneme == maksimum_deneme - 1:
                raise HTTPException(status_code=503, detail="Rezervasyon işlemi eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
            time.sleep(0.1 * (deneme + 1))
        except ExclusionViolation:
            if conn is not None: conn.rollback()
            raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten rezerve edilmiş.")
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()

@app.patch("/api/rezervasyonlar/{rezervasyon_id}/iptal")
def rezervasyon_iptal(rezervasyon_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("UPDATE cihaz_rezervasyonlari SET iptal_edildi_mi = TRUE WHERE rezervasyon_id = %s RETURNING rezervasyon_id;", (rezervasyon_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı veya yetkiniz yok.")
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CANCEL", kullanici_id=kullanici_id, hedef_tablo="cihaz_rezervasyonlari", hedef_kayit_id=rezervasyon_id)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Rezervasyon iptal edildi."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/rezervasyonlar")
def rezervasyonlari_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rezervasyon_id, c.envanter_kodu, c.cihaz_adi, r.baslangic_zamani, r.bitis_zamani, r.iptal_edildi_mi FROM cihaz_rezervasyonlari r JOIN cihazlar c ON r.cihaz_id = c.cihaz_id ORDER BY r.baslangic_zamani DESC;")
        kayitlar = cursor.fetchall()
        return [{"rezervasyon_id": k[0], "cihaz_id": f"{k[1]} - {k[2]}", "baslangic_zamani": k[3].isoformat() if hasattr(k[3], 'isoformat') else str(k[3]), "bitis_zamani": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]), "durum": "İptal Edildi" if k[5] else "Aktif"} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# ARIZA YÖNETİMİ MODÜLÜ (EFSANE YER)
# ==========================================

@app.get("/api/arizalar")
def arizalari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.ariza_id, c.cihaz_adi, a.ariza_aciklamasi, a.cozuldu_mu, a.bildirim_tarihi
            FROM cihaz_arizalari a
            JOIN cihazlar c ON a.cihaz_id = c.cihaz_id
            ORDER BY a.bildirim_tarihi DESC;
        """)
        kayitlar = cursor.fetchall()

        sonuc = []
        for kayit in kayitlar:
            tam_metin = kayit[2] if kayit[2] else ""
            aciliyet_derecesi = "Belirtilmedi"
            baslik = tam_metin
            aciklama = ""

            # DB'den gelen "[Kritik] Başlık - Açıklama" formatını form için 3'e bölüyoruz
            if tam_metin.startswith("[") and "]" in tam_metin:
                bol = tam_metin.split("]", 1)
                aciliyet_derecesi = bol[0].replace("[", "").strip()
                kalan = bol[1].strip()
                if "-" in kalan:
                    baslik, aciklama = kalan.split("-", 1)
                    baslik = baslik.strip()
                    aciklama = aciklama.strip()
                else:
                    baslik = kalan

            durum_metni = "Çözüldü" if kayit[3] else "Açık"
            sonuc.append({
                "ariza_id": kayit[0],
                "cihaz_adi": kayit[1],
                "ariza_baslik": baslik,
                "ariza_aciklama": aciklama, # Artık form için bunu da gönderiyoruz
                "aciliyet": aciliyet_derecesi,
                "durum": durum_metni,
                "bildirim_tarihi": kayit[4].isoformat() if hasattr(kayit[4], 'isoformat') else str(kayit[4])
            })
        return sonuc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/arizalar", status_code=201)
def ariza_bildir(ariza: ArizaBildirimModeli, kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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

        # 3. Tabloda Başlık ve Aciliyet sütunları olmadığı için hepsini anlamlı bir metin olarak birleştiriyoruz
        tam_aciklama = f"[{ariza.aciliyet}] {ariza.ariza_baslik} - {ariza.ariza_aciklama}"

        # 4. Arıza kaydını birebir veritabanı şemana uygun ekle
        cursor.execute("""
            INSERT INTO cihaz_arizalari (cihaz_id, bildiren_personel, ariza_aciklamasi, bildirim_tarihi, cozuldu_mu)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, FALSE) RETURNING ariza_id;
        """, (ariza.cihaz_id, bildiren_kisi, tam_aciklama))
        ariza_id = cursor.fetchone()[0]

        # 5. Cihazın durumunu 'Arizali' (veritabanı formatında) olarak güncelle!
        cursor.execute("UPDATE cihazlar SET durum = 'Arizali' WHERE cihaz_id = %s;", (ariza.cihaz_id,))
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
        if cihaz[0] != "Arizali":
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=ariza.cihaz_id,
                mevcut_cursor=cursor
            )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Arıza bildirimi alındı ve cihaz arızalı konuma çekildi.", "ariza_id": ariza_id}
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
def ariza_guncelle(ariza_id: int, ariza: ArizaGuncelleModeli, kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Cihaz IDsini bulalım
        cursor.execute("SELECT cihaz_id FROM cihaz_arizalari WHERE ariza_id = %s FOR UPDATE;", (ariza_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Arıza kaydı bulunamadı.")
        cihaz_id = kayit[0]

        # Tekrar veritabanı formatına (Tam Metin) dönüştür
        tam_aciklama = f"[{ariza.aciliyet}] {ariza.ariza_baslik} - {ariza.ariza_aciklama}"

        # Çözüldüyse çözüm tarihini anlık at, çözülmediyse NULL (Boş) yap
        cozum_sql = "CURRENT_TIMESTAMP" if ariza.cozuldu_mu else "NULL"

        # Arıza Tablosunu Güncelle
        cursor.execute(f"""
            UPDATE cihaz_arizalari
            SET ariza_aciklamasi = %s, cozuldu_mu = %s, cozum_tarihi = {cozum_sql}
            WHERE ariza_id = %s;
        """, (tam_aciklama, ariza.cozuldu_mu, ariza_id))

        # Cihazın mevcut durumunu oku ve satırı kilitle.
        cursor.execute(
            "SELECT durum FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;",
            (cihaz_id,)
        )
        cihaz_kaydi = cursor.fetchone()

        if cihaz_kaydi is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        eski_cihaz_durum = cihaz_kaydi[0]
        yeni_cihaz_durum = "Kullanima_Hazir" if ariza.cozuldu_mu else "Arizali"

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

@app.get("/api/bakimlar")
def bakimlari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # SQL Sorgusuna b.sonraki_bakim_tarihi eklendi
        cursor.execute("""
            SELECT b.bakim_id, c.cihaz_adi, c.envanter_kodu,
                   b.bakim_yapan_kisi, b.yapilan_islem, b.maliyet, b.bakim_tarihi, b.sonraki_bakim_tarihi
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            ORDER BY b.bakim_tarihi DESC;
        """)
        kayitlar = cursor.fetchall()

        return [
            {
                "bakim_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "bakim_yapan_kisi": k[3],
                "yapilan_islem": k[4],
                "maliyet": float(k[5]) if k[5] else 0.0,
                "bakim_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                "sonraki_bakim_tarihi": k[7].isoformat() if k[7] and hasattr(k[7], 'isoformat') else (str(k[7]) if k[7] else "Belirtilmedi")
            }
            for k in kayitlar
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/bakimlar", status_code=201)
def bakim_kaydi_ekle(bakim: BakimOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # INSERT sorgusuna sonraki_bakim_tarihi eklendi
        cursor.execute("""
            INSERT INTO cihaz_bakimlari (cihaz_id, bakim_yapan_kisi, yapilan_islem, maliyet, bakim_tarihi, sonraki_bakim_tarihi)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING bakim_id;
        """, (bakim.cihaz_id, bakim.bakim_yapan_kisi, bakim.yapilan_islem, bakim.maliyet, bakim.bakim_tarihi, bakim.sonraki_bakim_tarihi))
        bakim_id = cursor.fetchone()[0]

        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", kullanici_id, "cihaz_bakimlari", bakim_id)

        conn.commit()
        return {"durum": "basarili", "bakim_id": bakim_id}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/bakimlar/{bakim_id}")
def bakim_guncelle(bakim_id: int, guncelleme: BakimGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_bakimlari WHERE bakim_id = %s FOR UPDATE;", (bakim_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Bakım kaydı bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Güncellenecek veri bulunamadı.")

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_bakimlari SET {alanlar} WHERE bakim_id = %s;", (*degerler, bakim_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_bakimlari", hedef_kayit_id=bakim_id)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Bakım kaydı başarıyla güncellendi."}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# KALİBRASYON YÖNETİMİ MODÜLÜ (CALB-001, CALB-002)
# ==========================================

@app.get("/api/kalibrasyonlar")
def kalibrasyonlari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT k.kalibrasyon_id, c.cihaz_adi, c.envanter_kodu,
                   k.kalibrasyon_yapan_kurum, k.gecerlilik_tarihi, k.sertifika_no, k.islem_tarihi
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            ORDER BY k.islem_tarihi DESC;
        """)
        kayitlar = cursor.fetchall()

        return [
            {
                "kalibrasyon_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "kalibrasyon_yapan_kurum": k[3],
                "gecerlilik_tarihi": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]),
                "sertifika_no": k[5],
                "islem_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6])
            }
            for k in kayitlar
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/kalibrasyonlar", status_code=201)
def kalibrasyon_kaydi_ekle(kalib: KalibrasyonOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # islem_tarihi veritabanı tarafından otomatik veya backend'den eklenecek
        cursor.execute("""
            INSERT INTO cihaz_kalibrasyonlari (cihaz_id, kalibrasyon_yapan_kurum, gecerlilik_tarihi, sertifika_no, islem_tarihi)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP) RETURNING kalibrasyon_id;
        """, (kalib.cihaz_id, kalib.kalibrasyon_yapan_kurum, kalib.gecerlilik_tarihi, kalib.sertifika_no))
        kalibrasyon_id = cursor.fetchone()[0]

        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kalibrasyon başarıyla eklendi.", "kalibrasyon_id": kalibrasyon_id}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/kalibrasyonlar/{kalibrasyon_id}")
def kalibrasyon_guncelle(kalibrasyon_id: int, guncelleme: KalibrasyonGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_kalibrasyonlari WHERE kalibrasyon_id = %s FOR UPDATE;", (kalibrasyon_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Değişiklik yok.")

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_kalibrasyonlari SET {alanlar} WHERE kalibrasyon_id = %s;", (*degerler, kalibrasyon_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id)

        conn.commit()
        return {"durum": "basarili"}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# DASHBOARD VE RAPORLAMA MODÜLÜ (DASH-001)
# ==========================================

@app.get("/api/dashboard/ozet")
def dashboard_ozet_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        
        ozet = {
            "toplam_cihaz": 0, "aktif_cihaz": 0, "arizali_cihaz": 0, 
            "bakimdaki_cihaz": 0, "acik_ariza_sayisi": 0, "bugunku_randevu_sayisi": 0
        }

        # 1. Cihaz İstatistiklerini Çek
        cursor.execute("SELECT durum, COUNT(*) FROM cihazlar GROUP BY durum;")
        cihaz_durumlari = cursor.fetchall()
        for durum, sayi in cihaz_durumlari:
            ozet["toplam_cihaz"] += sayi
            if durum == "Kullanima_Hazir":
                ozet["aktif_cihaz"] = sayi
            elif durum == "Arizali":
                ozet["arizali_cihaz"] = sayi
            elif durum == "Bakimda":
                ozet["bakimdaki_cihaz"] = sayi

        # 2. Açık Arızaları Çek (cozuldu_mu sütunu FALSE olanlar)
        # Eğer tabloda cozuldu_mu yok durum varsa: WHERE durum != 'Çözüldü' şeklinde de olabilir, biz genel halini yazalım.
        try:
            cursor.execute("SELECT COUNT(*) FROM cihaz_arizalari WHERE cozuldu_mu = False;")
            ozet["acik_ariza_sayisi"] = cursor.fetchone()[0]
        except:
            conn.rollback() # Sütun adı farklıysa diye önlem

        # 3. Bugünkü Randevuları Çek
        cursor.execute("SELECT COUNT(*) FROM randevular WHERE DATE(baslangic_zamani) = CURRENT_DATE;")
        ozet["bugunku_randevu_sayisi"] = cursor.fetchone()[0]

        return ozet

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard veri çekme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.get("/api/dashboard/yaklasan-islemler")
def yaklasan_islemler_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    import datetime
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        islemler = []
        bugun = datetime.date.today()

        # 1. YAKLAŞAN BAKIMLAR (Saf Python Hesabı)
        cursor.execute("""
            SELECT c.envanter_kodu, c.cihaz_adi, b.sonraki_bakim_tarihi
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            WHERE b.sonraki_bakim_tarihi IS NOT NULL
        """)
        for kayit in cursor.fetchall():
            hedef_tarih = kayit[2]
            kalan_gun = (hedef_tarih - bugun).days
            if 0 <= kalan_gun <= 60:
                islemler.append({
                    "cihaz_adi": f"{kayit[0]} - {kayit[1]}",
                    "islem_turu": "Bakım",
                    "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                    "kalan_gun": kalan_gun,
                    "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
                })

        # 2. YAKLAŞAN KALİBRASYONLAR (Saf Python Hesabı)
        cursor.execute("""
            SELECT c.envanter_kodu, c.cihaz_adi, k.gecerlilik_tarihi
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            WHERE k.gecerlilik_tarihi IS NOT NULL
        """)
        for kayit in cursor.fetchall():
            hedef_tarih = kayit[2]
            kalan_gun = (hedef_tarih - bugun).days
            if 0 <= kalan_gun <= 60:
                islemler.append({
                    "cihaz_adi": f"{kayit[0]} - {kayit[1]}",
                    "islem_turu": "Kalibrasyon",
                    "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                    "kalan_gun": kalan_gun,
                    "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
                })

        islemler.sort(key=lambda x: x["kalan_gun"])
        return islemler[:10]

    except Exception as e:
        print("DASHBOARD API ÇÖKTÜ HATA:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# --- YENİ: FAALİYET DÜZENLEME (PUT) ---
@app.put("/api/faaliyet-kayitlari/{takip_id}")
def faaliyet_kaydi_guncelle(takip_id: int, kayit: FaaliyetKayitModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Kaydın var olup olmadığını kontrol edelim
        cursor.execute("SELECT * FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Güncellenecek kayıt bulunamadı.")

        cursor.execute("""
            UPDATE ogrenci_faaliyet_takip 
            SET ogrenci_id = %s, faaliyet_id = %s, birim_id = %s, adet = %s 
            WHERE takip_id = %s;
        """, (kayit.ogrenci_id, kayit.faaliyet_id, kayit.birim_id, kayit.miktar, takip_id))
        
        # Audit log (Denetim kaydı)
        try:
            from denetim import denetim_kaydi_olustur
            denetim_kaydi_olustur(VT_AYARLARI, "UPDATE", yetkili_id, "ogrenci_faaliyet_takip", takip_id)
        except ImportError:
            pass

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla güncellendi."}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Güncelleme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# --- YENİ: FAALİYET SİLME (DELETE) ---
@app.delete("/api/faaliyet-kayitlari/{takip_id}")
def faaliyet_kaydi_sil(takip_id: int, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Kaydın var olup olmadığını kontrol edelim
        cursor.execute("SELECT * FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Silinecek kayıt bulunamadı.")

        cursor.execute("DELETE FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        
        # Audit log (Denetim kaydı)
        try:
            from denetim import denetim_kaydi_olustur
            denetim_kaydi_olustur(VT_AYARLARI, "DELETE", yetkili_id, "ogrenci_faaliyet_takip", takip_id)
        except ImportError:
            pass

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt kalıcı olarak silindi."}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Silme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.errors import ExclusionViolation, DeadlockDetected
import os
import time
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
from modeller import (
    GirisModeli,
    RolDegistirModeli,
    KullaniciOlusturModeli,
    PersonelOlusturModeli,
    PersonelGuncelleModeli,
    SifreDegistirModeli,
    RandevuOlusturModeli,
    RandevuGuncelleModeli,
    DanisanKoduModeli,
    OdaOlusturModeli,
    OdaGuncelleModeli,
    CihazOlusturModeli,
    CihazGuncelleModeli,
    RezervasyonOlusturModeli,
    ArizaBildirimModeli,
    ArizaGuncelleModeli,
    KalibrasyonOlusturModeli,
    KalibrasyonGuncelleModeli,
    BakimOlusturModeli,
    BakimGuncelleModeli
)
from guvenlik import (
    parola_hashle,
    parola_dogrula,
    gecici_parola_uret,
    access_token_olustur,
    token_dogrula
)
from denetim import denetim_kaydi_olustur
from modeller import CihazGuncelleModeli, ArizaBildirimModeli, ArizaGuncelleModeli, FaaliyetKayitModeli
import psycopg2.errors
from modeller import FaaliyetKayitModeli, OgrenciEkleModeli

load_dotenv()
app = FastAPI()
bearer_scheme = HTTPBearer()

VT_AYARLARI = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
}

def otomatik_danisan_kodu_uret(cursor) -> str:
    yil = datetime.now().year
    cursor.execute("SELECT nextval('danisan_kodu_seq');")
    sira = cursor.fetchone()[0]
    return f"DAN-{yil}-{sira:04d}"

def token_kullanici_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> int:
    try:
        return token_dogrula(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi dolmuş.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token.")

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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT aktif_mi, ilk_giris_mi FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[0]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
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
            conn = psycopg2.connect(**VT_AYARLARI)
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

@app.get("/api/korumali-test")
def korumali_test(kullanici_id: int = Depends(mevcut_kullanici_id)):
    return {"durum": "basarili", "mesaj": "Token geçerli.", "kullanici_id": kullanici_id}

@app.post("/api/login")
def giris_yap(giris: GirisModeli):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT kullanici_id, kullanici_adi, parola_hash, rol_id, aktif_mi,
                   basarisiz_giris_sayisi, kilit_bitis_zamani, ilk_giris_mi
            FROM kullanicilar WHERE kullanici_adi = %s;
            """, (giris.kullanici_adi,)
        )
        kullanici = cursor.fetchone()

        if kullanici is None:
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", hedef_tablo="kullanicilar")
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya parola hatalı.")
        if not kullanici[4]:
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
        if kullanici[6] is not None and kullanici[6] > datetime.now():
            raise HTTPException(status_code=429, detail="Çok fazla hatalı giriş denemesi. Lütfen daha sonra tekrar deneyin.")

        if not parola_dogrula(giris.parola, kullanici[2]):
            yeni_basarisiz_giris_sayisi = kullanici[5] + 1
            if yeni_basarisiz_giris_sayisi >= 5:
                kilit_bitis_zamani = datetime.now() + timedelta(minutes=15)
                cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = %s, kilit_bitis_zamani = %s WHERE kullanici_id = %s;", (yeni_basarisiz_giris_sayisi, kilit_bitis_zamani, kullanici[0]))
            else:
                cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = %s WHERE kullanici_id = %s;", (yeni_basarisiz_giris_sayisi, kullanici[0]))
            conn.commit()
            denetim_kaydi_olustur(VT_AYARLARI, olay_turu="LOGIN_FAILED", kullanici_id=kullanici[0], hedef_tablo="kullanicilar", hedef_kayit_id=kullanici[0])
            if yeni_basarisiz_giris_sayisi >= 5:
                raise HTTPException(status_code=429, detail="Çok fazla hatalı giriş denemesi. Hesap 15 dakika kilitlendi.")
            raise HTTPException(status_code=401, detail="Kullanıcı adı veya parola hatalı.")

        cursor.execute("UPDATE kullanicilar SET basarisiz_giris_sayisi = 0, kilit_bitis_zamani = NULL WHERE kullanici_id = %s;", (kullanici[0],))
        conn.commit()
        access_token = access_token_olustur(kullanici[0])

        cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici[0],))
        pers = cursor.fetchone()
        personel_id = pers[0] if pers else None

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
            "sifre_degistirme_gerekli": kullanici[7]
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/sifre-degistir")
def sifre_degistir(veri: SifreDegistirModeli, kullanici_id: int = Depends(token_kullanici_id)):
    if veri.yeni_parola != veri.yeni_parola_tekrar:
        raise HTTPException(status_code=422, detail="Yeni şifreler birbiriyle eşleşmiyor.")
    if len(veri.yeni_parola.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Yeni şifre en fazla 72 bayt olabilir.")
    if veri.eski_parola == veri.yeni_parola:
        raise HTTPException(status_code=422, detail="Yeni şifre eski şifreyle aynı olamaz.")

    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT parola_hash, aktif_mi FROM kullanicilar WHERE kullanici_id = %s FOR UPDATE;", (kullanici_id,))
        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[1]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
        if not parola_dogrula(veri.eski_parola, kullanici[0]):
            raise HTTPException(status_code=401, detail="Eski şifre hatalı.")

        yeni_hash = parola_hashle(veri.yeni_parola)
        cursor.execute("UPDATE kullanicilar SET parola_hash = %s, ilk_giris_mi = FALSE WHERE kullanici_id = %s;", (yeni_hash, kullanici_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Şifreniz başarıyla değiştirildi."}
    except Exception:
        if conn is not None: conn.rollback()
        raise
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# ADM MODÜLÜ (Kullanıcı, Rol ve Personel)
# ==========================================

@app.post("/api/kullanicilar", status_code=201)
def kullanici_olustur(yeni_kullanici: KullaniciOlusturModeli, kullanici_id: int = Depends(izin_kontrol("KULLANICI_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        yapan = cursor.fetchone()

        cursor.execute(
            """
            SELECT 1 FROM kullanicilar k JOIN rol_izinleri ri ON k.rol_id = ri.rol_id JOIN izinler i ON ri.izin_id = i.izin_id
            WHERE k.kullanici_id = %s AND i.izin_adi = 'ROL_ATAMA_DEGISTIRME' AND ri.izin_var = 1;
            """, (kullanici_id,)
        )
        if cursor.fetchone() is None:
            raise HTTPException(status_code=403, detail="Rol atama yetkiniz bulunmuyor.")

        cursor.execute("SELECT rol_adi FROM roller WHERE rol_id = %s;", (yeni_kullanici.rol_id,))
        hedef_rol = cursor.fetchone()
        if hedef_rol is None:
            raise HTTPException(status_code=422, detail="Geçersiz rol seçildi.")

        if hedef_rol[0] == "ADMIN" and (yapan is None or yapan[0] != "ADMIN"):
            raise HTTPException(status_code=403, detail="ADMIN rolünü atama yetkiniz bulunmuyor.")

        gecici_parola = gecici_parola_uret()
        parola_hash = parola_hashle(gecici_parola)

        cursor.execute(
            "INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, ilk_giris_mi) VALUES (%s, %s, %s, TRUE, TRUE) RETURNING kullanici_id;",
            (yeni_kullanici.kullanici_adi, parola_hash, yeni_kullanici.rol_id)
        )
        yeni_id = cursor.fetchone()[0]
        conn.commit()

        return {
            "durum": "basarili",
            "kullanici_id": yeni_id,
            "kullanici_adi": yeni_kullanici.kullanici_adi,
            "gecici_parola": gecici_parola,
            "ilk_giris_mi": True
        }
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu kullanıcı adı zaten kullanılıyor.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()
        if islem_yapan is None:
            raise HTTPException(status_code=403, detail="Yetkisiz işlem.")
        islem_yapan_rol = islem_yapan[0]

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef_kullanici = cursor.fetchone()
        if hedef_kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
        mevcut_rol = hedef_kullanici[0]

        cursor.execute("SELECT rol_adi FROM roller WHERE rol_id = %s;", (veri.rol_id,))
        yeni_rol = cursor.fetchone()
        if yeni_rol is None:
            raise HTTPException(status_code=404, detail="Atanacak rol bulunamadı.")
        yeni_rol_adi = yeni_rol[0]

        if islem_yapan_rol != "ADMIN":
            if mevcut_rol == "ADMIN" or yeni_rol_adi == "ADMIN":
                raise HTTPException(status_code=403, detail="ADMIN rolünü yalnızca ADMIN yönetebilir.")

        cursor.execute("UPDATE kullanicilar SET rol_id = %s WHERE kullanici_id = %s;", (veri.rol_id, kullanici_id))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "ROLE_CHANGE", "kullanicilar", kullanici_id))
        conn.commit()

        return {"mesaj": "Kullanıcı rolü başarıyla değiştirildi.", "kullanici_id": kullanici_id, "yeni_rol_id": veri.rol_id, "yeni_rol_adi": yeni_rol_adi}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/kullanicilar/{kullanici_id}/pasiflestir")
def kullanici_pasiflestir(kullanici_id: int, islem_yapan_id: int = Depends(izin_kontrol("KULLANICI_PASIFLESTIR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        if kullanici_id == islem_yapan_id:
            raise HTTPException(status_code=403, detail="Kendi hesabınızı pasifleştiremezsiniz.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (islem_yapan_id,))
        islem_yapan = cursor.fetchone()
        if islem_yapan is None:
            raise HTTPException(status_code=403, detail="Yetkisiz işlem.")

        cursor.execute("SELECT r.rol_adi, k.aktif_mi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s FOR UPDATE OF k;", (kullanici_id,))
        hedef = cursor.fetchone()
        if hedef is None:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

        hedef_rol, aktif_mi = hedef
        if hedef_rol == "ADMIN" and islem_yapan[0] != "ADMIN":
            raise HTTPException(status_code=403, detail="ADMIN hesabını yalnızca ADMIN pasifleştirebilir.")
        if not aktif_mi:
            raise HTTPException(status_code=409, detail="Kullanıcı zaten pasif durumda.")

        cursor.execute("UPDATE kullanicilar SET aktif_mi = FALSE WHERE kullanici_id = %s;", (kullanici_id,))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "UPDATE", "kullanicilar", kullanici_id))
        conn.commit()

        return {"mesaj": "Kullanıcı başarıyla pasifleştirildi.", "kullanici_id": kullanici_id, "aktif_mi": False}
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Kullanıcı pasifleştirme sırasında veritabanı hatası oluştu: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/personel", status_code=201)
def personel_olustur(yeni_personel: PersonelOlusturModeli, islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT k.aktif_mi, r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (yeni_personel.kullanici_id,))
        kullanici = cursor.fetchone()
        if kullanici is None:
            raise HTTPException(status_code=404, detail="Kullanıcı hesabı bulunamadı.")
        if not kullanici[0]:
            raise HTTPException(status_code=422, detail="Pasif kullanıcı için personel kaydı oluşturulamaz.")

        cursor.execute("INSERT INTO personel (kullanici_id, personel_kodu) VALUES (%s, %s) RETURNING personel_id;", (yeni_personel.kullanici_id, yeni_personel.personel_kodu.strip()))
        personel_id = cursor.fetchone()[0]

        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "CREATE", "personel", personel_id))
        conn.commit()

        return {
            "mesaj": "Personel başarıyla oluşturuldu.",
            "personel_id": personel_id,
            "kullanici_id": yeni_personel.kullanici_id,
            "personel_kodu": yeni_personel.personel_kodu.strip(),
            "aktif_mi": True
        }
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu kullanıcıya ait personel kaydı veya personel kodu zaten mevcut.")
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Personel oluşturulurken veritabanı hatası oluştu: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/personel")
def personel_listele(islem_yapan_id: int = Depends(izin_kontrol("PERSONEL_TANIMLA"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, p.kullanici_id, k.kullanici_adi, p.personel_kodu, r.rol_adi, p.aktif_mi, p.olusturulma_tarihi
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id ORDER BY p.personel_id;
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "kullanici_id": k[1], "kullanici_adi": k[2], "personel_kodu": k[3], "rol_adi": k[4], "aktif_mi": k[5], "olusturulma_tarihi": k[6]} for k in kayitlar]
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
        conn = psycopg2.connect(**VT_AYARLARI)
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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT personel_id, personel_kodu, aktif_mi FROM personel WHERE personel_id = %s FOR UPDATE;", (personel_id,))
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Personel bulunamadı.")

        yeni_kod = degisiklikler.get("personel_kodu", mevcut[1])
        yeni_aktiflik = degisiklikler.get("aktif_mi", mevcut[2])

        cursor.execute("UPDATE personel SET personel_kodu = %s, aktif_mi = %s WHERE personel_id = %s;", (yeni_kod, yeni_aktiflik, personel_id))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (islem_yapan_id, "UPDATE", "personel", personel_id))
        conn.commit()
        return {"mesaj": "Personel başarıyla güncellendi.", "personel_id": personel_id, "personel_kodu": yeni_kod, "aktif_mi": yeni_aktiflik}
    except psycopg2.errors.UniqueViolation:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=409, detail="Bu personel kodu başka bir kayıtta kullanılıyor.")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# RANDEVU & ODA MODÜLÜ
# ==========================================
@app.get("/api/randevular/siradaki-kod")
def siradaki_danisan_kodunu_ver(kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        siradaki_kod = otomatik_danisan_kodu_uret(cursor)
        return {"siradaki_kod": siradaki_kod}
    except Exception:
        yil = datetime.now().year
        return {"siradaki_kod": f"DAN-{yil}-0001"}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/randevular", status_code=201)
def randevu_olustur(randevu: RandevuOlusturModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    if randevu.baslangic_zamani >= randevu.bitis_zamani:
        raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol is not None and rol[0] == "PSIKOLOG":
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu.psikolog_id:
                raise HTTPException(status_code=403, detail="Yalnızca kendi adınıza randevu oluşturabilirsiniz.")

        yeni_danisan_kodu = otomatik_danisan_kodu_uret(cursor)
        cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi) VALUES (%s, TRUE, 'YOK', TRUE);", (yeni_danisan_kodu,))

        cursor.execute("SELECT 1 FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND r.rol_adi = 'PSIKOLOG';", (randevu.psikolog_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")

        cursor.execute("SELECT 1 FROM odalar WHERE oda_id = %s AND aktif_mi = TRUE;", (randevu.oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Oda bulunamadı veya aktif değil.")

        cursor.execute("SELECT 1 FROM randevular WHERE durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu.psikolog_id, randevu.oda_id, randevu.bitis_zamani, randevu.baslangic_zamani))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        cursor.execute("INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum) VALUES (%s, %s, %s, %s, %s, 'PLANLANDI') RETURNING randevu_id;", (yeni_danisan_kodu, randevu.psikolog_id, randevu.oda_id, randevu.baslangic_zamani, randevu.bitis_zamani))
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
    except HTTPException:
        if conn is not None:
            conn.rollback()
        raise
    except Exception:
        if conn is not None:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail="Randevu oluşturulurken bir hata oluştu."
        )
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()
@app.get("/api/randevular")
def randevulari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is None or rol[0] not in ("PSIKOLOG", "ADMIN", "DANISMA_OGRENCISI"):
            raise HTTPException(status_code=403, detail="Randevuları görüntüleme yetkiniz yok.")

        cursor.execute("SELECT randevu_id, danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum FROM randevular ORDER BY baslangic_zamani;")
        kayitlar = cursor.fetchall()
        return [{"randevu_id": kayit[0], "danisan_kod_id": kayit[1], "psikolog_id": kayit[2], "oda_id": kayit[3], "baslangic_zamani": kayit[4], "bitis_zamani": kayit[5], "durum": kayit[6]} for kayit in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.patch("/api/randevular/{randevu_id}")
def randevu_guncelle(randevu_id: int, guncelleme: RandevuGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("RANDEVU_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        mevcut = cursor.fetchone()
        if mevcut is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")
        if mevcut[5] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Yalnızca planlanmış randevular güncellenebilir.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol[0] == "PSIKOLOG":
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

        if rol[0] == "PSIKOLOG" and psikolog_id != mevcut[1]:
            raise HTTPException(status_code=403, detail="Randevuyu başka psikoloğa devredemezsiniz.")
        if baslangic >= bitis:
            raise HTTPException(status_code=422, detail="Başlangıç zamanı bitiş zamanından önce olmalıdır.")

        cursor.execute("SELECT 1 FROM randevular WHERE randevu_id != %s AND durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (randevu_id, psikolog_id, oda_id, bitis, baslangic))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        cursor.execute("UPDATE randevular SET danisan_kod_id = %s, psikolog_id = %s, oda_id = %s, baslangic_zamani = %s, bitis_zamani = %s WHERE randevu_id = %s;", (danisan_kod_id, psikolog_id, oda_id, baslangic, bitis, randevu_id))
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
def randevu_iptal_et(randevu_id: int, kullanici_id: int = Depends(izin_kontrol("RANDEVU_IPTAL"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT psikolog_id, durum FROM randevular WHERE randevu_id = %s FOR UPDATE;", (randevu_id,))
        randevu = cursor.fetchone()
        if randevu is None:
            raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s;", (kullanici_id,))
        rol = cursor.fetchone()

        if rol[0] == "PSIKOLOG":
            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s AND aktif_mi = TRUE;", (kullanici_id,))
            personel = cursor.fetchone()
            if personel is None or personel[0] != randevu[0]:
                raise HTTPException(status_code=403, detail="Yalnızca kendi randevunuzu iptal edebilirsiniz.")

        if randevu[1] != "PLANLANDI":
            raise HTTPException(status_code=409, detail="Bu randevu iptal edilemez.")

        cursor.execute("UPDATE randevular SET durum = 'IPTAL_EDILDI' WHERE randevu_id = %s;", (randevu_id,))
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CANCEL", "randevular", randevu_id))
        conn.commit()
        return {"durum": "basarili", "mesaj": "Randevu iptal edildi.", "randevu_id": randevu_id}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/danisan-kodlari", status_code=201)
def danisan_kodu_olustur(ucretli_mi: bool = True, istisna_turu: str = "YOK", kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rol_adi FROM kullanicilar k JOIN roller r ON k.rol_id = r.rol_id WHERE k.kullanici_id = %s AND k.aktif_mi = TRUE;", (kullanici_id,))
        rol = cursor.fetchone()
        if rol is None or rol[0] not in ("ADMIN", "PSIKOLOG", "DANISMA_OGRENCISI"):
            raise HTTPException(status_code=403, detail="Danışan kodu oluşturma yetkiniz yok.")

        yeni_kod = otomatik_danisan_kodu_uret(cursor)
        cursor.execute("INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi) VALUES (%s, %s, %s, TRUE) RETURNING danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi, olusturulma_tarihi;", (yeni_kod, ucretli_mi, istisna_turu))
        kayit = cursor.fetchone()
        cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo) VALUES (%s, %s, %s);", (kullanici_id, "CREATE", "danisan_kodlari"))
        conn.commit()
        veri = DanisanKoduModeli(danisan_kod_id=kayit[0], ucretli_mi=kayit[1], istisna_turu=kayit[2], aktif_mi=kayit[3], olusturulma_tarihi=kayit[4])
        return {"durum": "basarili", "veri": veri.model_dump(mode="json")}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/odalar", status_code=201)
def oda_olustur(oda: OdaOlusturModeli, kullanici_id: int = Depends(izin_kontrol("ODA_EKLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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

@app.get("/api/odalar")
def odalari_listele():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id, oda_adi, kapasite, aktif_mi FROM odalar ORDER BY oda_id;")
        odalar = cursor.fetchall()
        return [{"oda_id": oda[0], "oda_adi": oda[1], "kapasite": oda[2], "aktif_mi": oda[3]} for oda in odalar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/odalar/{oda_id}")
def oda_detay(oda_id: int, kullanici_id: int = Depends(izin_kontrol("ODA_DURUMU_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT oda_id FROM odalar WHERE oda_id = %s FOR UPDATE;", (oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Oda bulunamadı.")

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
def danisan_kodlari_listele(kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT danisan_kod_id, ucretli_mi, aktif_mi FROM danisan_kodlari WHERE aktif_mi = TRUE ORDER BY olusturulma_tarihi DESC;")
        kayitlar = cursor.fetchall()
        return [{"danisan_kod_id": k[0], "ucretli_mi": k[1], "aktif_mi": k[2]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/psikologlar")
def aktif_psikologlari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.personel_id, k.kullanici_adi
            FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id
            WHERE p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND UPPER(r.rol_adi) = 'PSIKOLOG';
        """)
        kayitlar = cursor.fetchall()
        return [{"personel_id": k[0], "ad_soyad": k[1]} for k in kayitlar]
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
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM cihazlar WHERE envanter_kodu = %s OR seri_no = %s;", (cihaz.envanter_kodu, cihaz.seri_no))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Bu envanter kodu veya seri no zaten kullanımda.")

        cursor.execute(
            "INSERT INTO cihazlar (envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum) VALUES (%s, %s, %s, %s, %s, %s) RETURNING cihaz_id;",
            (cihaz.envanter_kodu, cihaz.cihaz_adi, cihaz.marka_model, cihaz.seri_no, cihaz.zimmetli_oda_id, cihaz.durum.value)
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
        conn = psycopg2.connect(**VT_AYARLARI)
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

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

@app.get("/api/cihazlar")
def cihazlari_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_UYGUNLUK_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum, kayit_tarihi FROM cihazlar ORDER BY cihaz_id;")
        kayitlar = cursor.fetchall()
        return [{"cihaz_id": k[0], "envanter_kodu": k[1], "cihaz_adi": k[2], "marka_model": k[3], "seri_no": k[4], "zimmetli_oda_id": k[5], "durum": k[6], "kayit_tarihi": k[7]} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/cihazlar/{cihaz_id}")
def cihaz_detayi_getir(cihaz_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_UYGUNLUK_GORUNTULE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT cihaz_id, envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum, kayit_tarihi FROM cihazlar WHERE cihaz_id = %s;", (cihaz_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
        return {"cihaz_id": kayit[0], "envanter_kodu": kayit[1], "cihaz_adi": kayit[2], "marka_model": kayit[3], "seri_no": kayit[4], "zimmetli_oda_id": kayit[5], "durum": kayit[6], "kayit_tarihi": kayit[7]}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/rezervasyonlar", status_code=201)
def cihaz_rezervasyonu_yap(rez: RezervasyonOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    if rez.baslangic_zamani >= rez.bitis_zamani:
        raise HTTPException(status_code=422, detail="Bitiş zamanı, başlangıçtan sonra olmalıdır.")
    maksimum_deneme = 3
    for deneme in range(maksimum_deneme):
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**VT_AYARLARI)
            cursor = conn.cursor()
            cursor.execute("SELECT durum FROM cihazlar WHERE cihaz_id = %s;", (rez.cihaz_id,))
            cihaz = cursor.fetchone()
            if cihaz is None:
                raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")
            if cihaz[0] not in ["Kullanima_Hazir", "Rezerve"]:
                raise HTTPException(status_code=403, detail=f"Cihaz şu anda {cihaz[0]} durumunda olduğu için rezerve edilemez!")

            cursor.execute("SELECT 1 FROM cihaz_rezervasyonlari WHERE cihaz_id = %s AND iptal_edildi_mi = FALSE AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;", (rez.cihaz_id, rez.bitis_zamani, rez.baslangic_zamani))
            if cursor.fetchone():
                raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten başka bir iş için rezerve edilmiş.")

            cursor.execute("SELECT personel_id FROM personel WHERE kullanici_id = %s;", (kullanici_id,))
            pers = cursor.fetchone()
            personel_id = pers[0] if pers else None

            cursor.execute("INSERT INTO cihaz_rezervasyonlari (cihaz_id, rezervasyonu_yapan_personel_id, kullanilacak_oda_id, baslangic_zamani, bitis_zamani, proje_turu, proje_adi_aciklamasi) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING rezervasyon_id;", (rez.cihaz_id, personel_id, rez.kullanilacak_oda_id, rez.baslangic_zamani, rez.bitis_zamani, rez.proje_turu, rez.proje_adi_aciklamasi))
            rez_id = cursor.fetchone()[0]

            cursor.execute("INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id) VALUES (%s, %s, %s, %s);", (kullanici_id, "CREATE", "cihaz_rezervasyonlari", rez_id))
            conn.commit()
            return {"durum": "basarili", "mesaj": "Rezervasyon başarıyla oluşturuldu.", "rezervasyon_id": rez_id}
        except DeadlockDetected:
            if conn is not None: conn.rollback()
            if deneme == maksimum_deneme - 1:
                raise HTTPException(status_code=503, detail="Rezervasyon işlemi eşzamanlı yoğunluk nedeniyle tamamlanamadı. Lütfen tekrar deneyin.")
            time.sleep(0.1 * (deneme + 1))
        except ExclusionViolation:
            if conn is not None: conn.rollback()
            raise HTTPException(status_code=409, detail="Cihaz seçilen saat aralığında zaten rezerve edilmiş.")
        finally:
            if cursor is not None: cursor.close()
            if conn is not None: conn.close()

@app.patch("/api/rezervasyonlar/{rezervasyon_id}/iptal")
def rezervasyon_iptal(rezervasyon_id: int, kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("UPDATE cihaz_rezervasyonlari SET iptal_edildi_mi = TRUE WHERE rezervasyon_id = %s RETURNING rezervasyon_id;", (rezervasyon_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Rezervasyon bulunamadı veya yetkiniz yok.")
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CANCEL", kullanici_id=kullanici_id, hedef_tablo="cihaz_rezervasyonlari", hedef_kayit_id=rezervasyon_id)
        conn.commit()
        return {"durum": "basarili", "mesaj": "Rezervasyon iptal edildi."}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/rezervasyonlar")
def rezervasyonlari_listele(kullanici_id: int = Depends(izin_kontrol("CIHAZ_REZERVASYON"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT r.rezervasyon_id, c.envanter_kodu, c.cihaz_adi, r.baslangic_zamani, r.bitis_zamani, r.iptal_edildi_mi FROM cihaz_rezervasyonlari r JOIN cihazlar c ON r.cihaz_id = c.cihaz_id ORDER BY r.baslangic_zamani DESC;")
        kayitlar = cursor.fetchall()
        return [{"rezervasyon_id": k[0], "cihaz_id": f"{k[1]} - {k[2]}", "baslangic_zamani": k[3].isoformat() if hasattr(k[3], 'isoformat') else str(k[3]), "bitis_zamani": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]), "durum": "İptal Edildi" if k[5] else "Aktif"} for k in kayitlar]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# ARIZA YÖNETİMİ MODÜLÜ (EFSANE YER)
# ==========================================

@app.get("/api/arizalar")
def arizalari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.ariza_id, c.cihaz_adi, a.ariza_aciklamasi, a.cozuldu_mu, a.bildirim_tarihi
            FROM cihaz_arizalari a
            JOIN cihazlar c ON a.cihaz_id = c.cihaz_id
            ORDER BY a.bildirim_tarihi DESC;
        """)
        kayitlar = cursor.fetchall()

        sonuc = []
        for kayit in kayitlar:
            tam_metin = kayit[2] if kayit[2] else ""
            aciliyet_derecesi = "Belirtilmedi"
            baslik = tam_metin
            aciklama = ""

            # DB'den gelen "[Kritik] Başlık - Açıklama" formatını form için 3'e bölüyoruz
            if tam_metin.startswith("[") and "]" in tam_metin:
                bol = tam_metin.split("]", 1)
                aciliyet_derecesi = bol[0].replace("[", "").strip()
                kalan = bol[1].strip()
                if "-" in kalan:
                    baslik, aciklama = kalan.split("-", 1)
                    baslik = baslik.strip()
                    aciklama = aciklama.strip()
                else:
                    baslik = kalan

            durum_metni = "Çözüldü" if kayit[3] else "Açık"
            sonuc.append({
                "ariza_id": kayit[0],
                "cihaz_adi": kayit[1],
                "ariza_baslik": baslik,
                "ariza_aciklama": aciklama, # Artık form için bunu da gönderiyoruz
                "aciliyet": aciliyet_derecesi,
                "durum": durum_metni,
                "bildirim_tarihi": kayit[4].isoformat() if hasattr(kayit[4], 'isoformat') else str(kayit[4])
            })
        return sonuc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/arizalar", status_code=201)
def ariza_bildir(ariza: ArizaBildirimModeli, kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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

        # 3. Tabloda Başlık ve Aciliyet sütunları olmadığı için hepsini anlamlı bir metin olarak birleştiriyoruz
        tam_aciklama = f"[{ariza.aciliyet}] {ariza.ariza_baslik} - {ariza.ariza_aciklama}"

        # 4. Arıza kaydını birebir veritabanı şemana uygun ekle
        cursor.execute("""
            INSERT INTO cihaz_arizalari (cihaz_id, bildiren_personel, ariza_aciklamasi, bildirim_tarihi, cozuldu_mu)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, FALSE) RETURNING ariza_id;
        """, (ariza.cihaz_id, bildiren_kisi, tam_aciklama))
        ariza_id = cursor.fetchone()[0]

        # 5. Cihazın durumunu 'Arizali' (veritabanı formatında) olarak güncelle!
        cursor.execute("UPDATE cihazlar SET durum = 'Arizali' WHERE cihaz_id = %s;", (ariza.cihaz_id,))
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
        if cihaz[0] != "Arizali":
            denetim_kaydi_olustur(
                VT_AYARLARI,
                olay_turu="DEVICE_STATUS_CHANGE",
                kullanici_id=kullanici_id,
                hedef_tablo="cihazlar",
                hedef_kayit_id=ariza.cihaz_id,
                mevcut_cursor=cursor
            )
        conn.commit()
        return {"durum": "basarili", "mesaj": "Arıza bildirimi alındı ve cihaz arızalı konuma çekildi.", "ariza_id": ariza_id}
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
def ariza_guncelle(ariza_id: int, ariza: ArizaGuncelleModeli, kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Cihaz IDsini bulalım
        cursor.execute("SELECT cihaz_id FROM cihaz_arizalari WHERE ariza_id = %s FOR UPDATE;", (ariza_id,))
        kayit = cursor.fetchone()
        if kayit is None:
            raise HTTPException(status_code=404, detail="Arıza kaydı bulunamadı.")
        cihaz_id = kayit[0]

        # Tekrar veritabanı formatına (Tam Metin) dönüştür
        tam_aciklama = f"[{ariza.aciliyet}] {ariza.ariza_baslik} - {ariza.ariza_aciklama}"

        # Çözüldüyse çözüm tarihini anlık at, çözülmediyse NULL (Boş) yap
        cozum_sql = "CURRENT_TIMESTAMP" if ariza.cozuldu_mu else "NULL"

        # Arıza Tablosunu Güncelle
        cursor.execute(f"""
            UPDATE cihaz_arizalari
            SET ariza_aciklamasi = %s, cozuldu_mu = %s, cozum_tarihi = {cozum_sql}
            WHERE ariza_id = %s;
        """, (tam_aciklama, ariza.cozuldu_mu, ariza_id))

        # Cihazın mevcut durumunu oku ve satırı kilitle.
        cursor.execute(
            "SELECT durum FROM cihazlar WHERE cihaz_id = %s FOR UPDATE;",
            (cihaz_id,)
        )
        cihaz_kaydi = cursor.fetchone()

        if cihaz_kaydi is None:
            raise HTTPException(status_code=404, detail="Cihaz bulunamadı.")

        eski_cihaz_durum = cihaz_kaydi[0]
        yeni_cihaz_durum = "Kullanima_Hazir" if ariza.cozuldu_mu else "Arizali"

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

@app.get("/api/bakimlar")
def bakimlari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # SQL Sorgusuna b.sonraki_bakim_tarihi eklendi
        cursor.execute("""
            SELECT b.bakim_id, c.cihaz_adi, c.envanter_kodu,
                   b.bakim_yapan_kisi, b.yapilan_islem, b.maliyet, b.bakim_tarihi, b.sonraki_bakim_tarihi
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            ORDER BY b.bakim_tarihi DESC;
        """)
        kayitlar = cursor.fetchall()

        return [
            {
                "bakim_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "bakim_yapan_kisi": k[3],
                "yapilan_islem": k[4],
                "maliyet": float(k[5]) if k[5] else 0.0,
                "bakim_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6]),
                "sonraki_bakim_tarihi": k[7].isoformat() if k[7] and hasattr(k[7], 'isoformat') else (str(k[7]) if k[7] else "Belirtilmedi")
            }
            for k in kayitlar
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/bakimlar", status_code=201)
def bakim_kaydi_ekle(bakim: BakimOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # INSERT sorgusuna sonraki_bakim_tarihi eklendi
        cursor.execute("""
            INSERT INTO cihaz_bakimlari (cihaz_id, bakim_yapan_kisi, yapilan_islem, maliyet, bakim_tarihi, sonraki_bakim_tarihi)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING bakim_id;
        """, (bakim.cihaz_id, bakim.bakim_yapan_kisi, bakim.yapilan_islem, bakim.maliyet, bakim.bakim_tarihi, bakim.sonraki_bakim_tarihi))
        bakim_id = cursor.fetchone()[0]

        denetim_kaydi_olustur(VT_AYARLARI, "CREATE", kullanici_id, "cihaz_bakimlari", bakim_id)

        conn.commit()
        return {"durum": "basarili", "bakim_id": bakim_id}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/bakimlar/{bakim_id}")
def bakim_guncelle(bakim_id: int, guncelleme: BakimGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_bakimlari WHERE bakim_id = %s FOR UPDATE;", (bakim_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Bakım kaydı bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Güncellenecek veri bulunamadı.")

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_bakimlari SET {alanlar} WHERE bakim_id = %s;", (*degerler, bakim_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_bakimlari", hedef_kayit_id=bakim_id)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Bakım kaydı başarıyla güncellendi."}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# KALİBRASYON YÖNETİMİ MODÜLÜ (CALB-001, CALB-002)
# ==========================================

@app.get("/api/kalibrasyonlar")
def kalibrasyonlari_listele(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT k.kalibrasyon_id, c.cihaz_adi, c.envanter_kodu,
                   k.kalibrasyon_yapan_kurum, k.gecerlilik_tarihi, k.sertifika_no, k.islem_tarihi
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            ORDER BY k.islem_tarihi DESC;
        """)
        kayitlar = cursor.fetchall()

        return [
            {
                "kalibrasyon_id": k[0],
                "cihaz_adi": f"{k[2]} - {k[1]}",
                "kalibrasyon_yapan_kurum": k[3],
                "gecerlilik_tarihi": k[4].isoformat() if hasattr(k[4], 'isoformat') else str(k[4]),
                "sertifika_no": k[5],
                "islem_tarihi": k[6].isoformat() if hasattr(k[6], 'isoformat') else str(k[6])
            }
            for k in kayitlar
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/kalibrasyonlar", status_code=201)
def kalibrasyon_kaydi_ekle(kalib: KalibrasyonOlusturModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # islem_tarihi veritabanı tarafından otomatik veya backend'den eklenecek
        cursor.execute("""
            INSERT INTO cihaz_kalibrasyonlari (cihaz_id, kalibrasyon_yapan_kurum, gecerlilik_tarihi, sertifika_no, islem_tarihi)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP) RETURNING kalibrasyon_id;
        """, (kalib.cihaz_id, kalib.kalibrasyon_yapan_kurum, kalib.gecerlilik_tarihi, kalib.sertifika_no))
        kalibrasyon_id = cursor.fetchone()[0]

        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="CREATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id)

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kalibrasyon başarıyla eklendi.", "kalibrasyon_id": kalibrasyon_id}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.put("/api/kalibrasyonlar/{kalibrasyon_id}")
def kalibrasyon_guncelle(kalibrasyon_id: int, guncelleme: KalibrasyonGuncelleModeli, kullanici_id: int = Depends(izin_kontrol("CIHAZ_ENVANTER_YONET"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM cihaz_kalibrasyonlari WHERE kalibrasyon_id = %s FOR UPDATE;", (kalibrasyon_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Kayıt bulunamadı.")

        degisiklikler = guncelleme.model_dump(exclude_unset=True)
        if not degisiklikler:
            raise HTTPException(status_code=422, detail="Değişiklik yok.")

        alanlar = ", ".join(f"{alan} = %s" for alan in degisiklikler)
        degerler = list(degisiklikler.values())

        cursor.execute(f"UPDATE cihaz_kalibrasyonlari SET {alanlar} WHERE kalibrasyon_id = %s;", (*degerler, kalibrasyon_id))
        denetim_kaydi_olustur(VT_AYARLARI, olay_turu="UPDATE", kullanici_id=kullanici_id, hedef_tablo="cihaz_kalibrasyonlari", hedef_kayit_id=kalibrasyon_id)

        conn.commit()
        return {"durum": "basarili"}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# DASHBOARD VE RAPORLAMA MODÜLÜ (DASH-001)
# ==========================================

@app.get("/api/dashboard/ozet")
def dashboard_ozet_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        
        ozet = {
            "toplam_cihaz": 0, "aktif_cihaz": 0, "arizali_cihaz": 0, 
            "bakimdaki_cihaz": 0, "acik_ariza_sayisi": 0, "bugunku_randevu_sayisi": 0
        }

        # 1. Cihaz İstatistiklerini Çek
        cursor.execute("SELECT durum, COUNT(*) FROM cihazlar GROUP BY durum;")
        cihaz_durumlari = cursor.fetchall()
        for durum, sayi in cihaz_durumlari:
            ozet["toplam_cihaz"] += sayi
            if durum == "Kullanima_Hazir":
                ozet["aktif_cihaz"] = sayi
            elif durum == "Arizali":
                ozet["arizali_cihaz"] = sayi
            elif durum == "Bakimda":
                ozet["bakimdaki_cihaz"] = sayi

        # 2. Açık Arızaları Çek (cozuldu_mu sütunu FALSE olanlar)
        # Eğer tabloda cozuldu_mu yok durum varsa: WHERE durum != 'Çözüldü' şeklinde de olabilir, biz genel halini yazalım.
        try:
            cursor.execute("SELECT COUNT(*) FROM cihaz_arizalari WHERE cozuldu_mu = False;")
            ozet["acik_ariza_sayisi"] = cursor.fetchone()[0]
        except:
            conn.rollback() # Sütun adı farklıysa diye önlem

        # 3. Bugünkü Randevuları Çek
        cursor.execute("SELECT COUNT(*) FROM randevular WHERE DATE(baslangic_zamani) = CURRENT_DATE;")
        ozet["bugunku_randevu_sayisi"] = cursor.fetchone()[0]

        return ozet

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard veri çekme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


@app.get("/api/dashboard/yaklasan-islemler")
def yaklasan_islemler_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    import datetime
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        islemler = []
        bugun = datetime.date.today()

        # 1. YAKLAŞAN BAKIMLAR (Saf Python Hesabı)
        cursor.execute("""
            SELECT c.envanter_kodu, c.cihaz_adi, b.sonraki_bakim_tarihi
            FROM cihaz_bakimlari b
            JOIN cihazlar c ON b.cihaz_id = c.cihaz_id
            WHERE b.sonraki_bakim_tarihi IS NOT NULL
        """)
        for kayit in cursor.fetchall():
            hedef_tarih = kayit[2]
            kalan_gun = (hedef_tarih - bugun).days
            if 0 <= kalan_gun <= 60:
                islemler.append({
                    "cihaz_adi": f"{kayit[0]} - {kayit[1]}",
                    "islem_turu": "Bakım",
                    "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                    "kalan_gun": kalan_gun,
                    "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
                })

        # 2. YAKLAŞAN KALİBRASYONLAR (Saf Python Hesabı)
        cursor.execute("""
            SELECT c.envanter_kodu, c.cihaz_adi, k.gecerlilik_tarihi
            FROM cihaz_kalibrasyonlari k
            JOIN cihazlar c ON k.cihaz_id = c.cihaz_id
            WHERE k.gecerlilik_tarihi IS NOT NULL
        """)
        for kayit in cursor.fetchall():
            hedef_tarih = kayit[2]
            kalan_gun = (hedef_tarih - bugun).days
            if 0 <= kalan_gun <= 60:
                islemler.append({
                    "cihaz_adi": f"{kayit[0]} - {kayit[1]}",
                    "islem_turu": "Kalibrasyon",
                    "tarih": hedef_tarih.strftime("%d.%m.%Y"),
                    "kalan_gun": kalan_gun,
                    "durum_kodu": "KRITIK" if kalan_gun <= 5 else "UYARI"
                })

        islemler.sort(key=lambda x: x["kalan_gun"])
        return islemler[:10]

    except Exception as e:
        print("DASHBOARD API ÇÖKTÜ HATA:", str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# ==========================================
# FAALİYET YÖNETİMİ MODÜLÜ API UÇLARI
# ==========================================

@app.get("/api/faaliyetler")
def faaliyetleri_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/faaliyet-birimleri")
def faaliyet_birimleri_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# --- YENİ EKLENEN: ÖĞRENCİ LİSTESİNİ GETİRİR ---
@app.get("/api/ogrenciler-liste")
def ogrencileri_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        # Sadece Ad Soyad ve Öğrenci Numarasını çek (Bolum ve sinif iptal edildi)
        cursor.execute("SELECT ogrenci_id, ad_soyad, ogrenci_numarasi FROM ogrenciler WHERE aktif_mi = true;")
        
        liste = []
        for r in cursor.fetchall():
            liste.append({"id": r[0], "metin": f"{r[1]} - [{r[2]}]"})
        return liste
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()


# --- GÜNCELLENEN: YENİ TABLOYA (ÖĞRENCİ TAKİP) KAYIT ATAR ---
@app.post("/api/faaliyet-kayitlari")
def faaliyet_kaydi_ekle(kayit: FaaliyetKayitModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Doğrudan senin şemandaki "ogrenci_faaliyet_takip" tablosuna yazıyoruz.
        # Not: Senin şemanda miktar sütununun adı "adet", o yüzden "adet" olarak ekliyoruz.
        cursor.execute("""
            INSERT INTO ogrenci_faaliyet_takip 
            (ogrenci_id, faaliyet_id, birim_id, adet, faaliyet_tarihi) 
            VALUES (%s, %s, %s, %s, CURRENT_DATE) RETURNING takip_id;
        """, (kayit.ogrenci_id, kayit.faaliyet_id, kayit.birim_id, kayit.miktar))
        
        yeni_id = cursor.fetchone()[0]
        
        # Öğrenci C'nin Denetim (Audit) logunu tutuyoruz
# Öğrenci C'nin Denetim (Audit) logunu tutuyoruz
        try:
            from denetim import denetim_kaydi_olustur
            denetim_kaydi_olustur(VT_AYARLARI, "CREATE", yetkili_id, "ogrenci_faaliyet_takip", yeni_id)
        except ImportError:
            pass

        conn.commit()
        return {"durum": "basarili", "mesaj": "Öğrenci faaliyeti başarıyla sisteme işlendi."}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/ogrenci-ekle")
def ogrenci_ekle(ogr: OgrenciEkleModeli, yetkili_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO ogrenciler 
            (ad_soyad, ogrenci_numarasi, telefon, tur, bolum, sinif) 
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING ogrenci_id;
        """, (ogr.ad_soyad, ogr.ogrenci_numarasi, ogr.telefon, ogr.tur, ogr.bolum, ogr.sinif))
        
        yeni_id = cursor.fetchone()[0]
        conn.commit()
        return {"durum": "basarili", "mesaj": "Öğrenci başarıyla sisteme eklendi.", "ogrenci_id": yeni_id}
        
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        raise HTTPException(status_code=400, detail="Bu öğrenci numarası sistemde zaten kayıtlı!")
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veritabanı hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# --- LİSTELEME İÇİN EKLENEN YENİ GET FONKSİYONU ---
@app.get("/api/faaliyet-kayitlari")
def faaliyet_kayitlarini_getir(kullanici_id: int = Depends(mevcut_kullanici_id)):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        
        # 4 tabloyu birleştirip, puanı (adet * faaliyet_puanı) olarak hesaplayan efsane SQL
        sorgu = """
        SELECT 
            t.takip_id,
            o.ad_soyad,
            o.ogrenci_numarasi,
            f.faaliyet_adi,
            t.adet,
            b.birim_adi,
            (t.adet * f.puan) AS toplam_puan,
            t.faaliyet_tarihi
        FROM ogrenci_faaliyet_takip t
        JOIN ogrenciler o ON t.ogrenci_id = o.ogrenci_id
        JOIN faaliyetler f ON t.faaliyet_id = f.faaliyet_id
        JOIN faaliyet_birimleri b ON t.birim_id = b.birim_id
        ORDER BY t.olusturulma_tarihi DESC;
        """
        cursor.execute(sorgu)
        
        kayitlar = []
        for row in cursor.fetchall():
            kayitlar.append({
                "id": row[0],
                "ad_soyad": row[1],
                "ogrenci_no": row[2],
                "faaliyet_adi": row[3],
                "miktar": f"{row[4]} {row[5]}", # Örn: "3 KISI" veya "5 SAAT"
                "toplam_puan": row[6],
                "tarih": row[7].strftime("%d.%m.%Y") if row[7] else ""
            })
        return kayitlar
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Veri çekme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()
# --- YENİ: FAALİYET DÜZENLEME (PUT) ---
@app.put("/api/faaliyet-kayitlari/{takip_id}")
def faaliyet_kaydi_guncelle(takip_id: int, kayit: FaaliyetKayitModeli, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Kaydın var olup olmadığını kontrol edelim
        cursor.execute("SELECT * FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Güncellenecek kayıt bulunamadı.")

        cursor.execute("""
            UPDATE ogrenci_faaliyet_takip 
            SET ogrenci_id = %s, faaliyet_id = %s, birim_id = %s, adet = %s 
            WHERE takip_id = %s;
        """, (kayit.ogrenci_id, kayit.faaliyet_id, kayit.birim_id, kayit.miktar, takip_id))
        
        # Audit log (Denetim kaydı)
        try:
            from denetim import denetim_kaydi_olustur
            denetim_kaydi_olustur(VT_AYARLARI, "UPDATE", yetkili_id, "ogrenci_faaliyet_takip", takip_id)
        except ImportError:
            pass

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla güncellendi."}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Güncelleme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

# --- YENİ: FAALİYET SİLME (DELETE) ---
@app.delete("/api/faaliyet-kayitlari/{takip_id}")
def faaliyet_kaydi_sil(takip_id: int, yetkili_id: int = Depends(izin_kontrol("FAALIYET_KAYITLARI_DUZENLE"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        # Silinmeden önce kaydın var olup olmadığını kontrol edelim
        cursor.execute("SELECT * FROM ogrenci_faaliyet_takip WHERE takip_id = %s", (takip_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Silinecek kayıt zaten yok veya bulunamadı.")

        # Kaydı acımadan veritabanından siliyoruz
        cursor.execute("DELETE FROM ogrenci_faaliyet_takip WHERE takip_id = %s;", (takip_id,))
        
        # Audit log (Denetim kaydı) - Kim sildi bilelim
        try:
            from denetim import denetim_kaydi_olustur
            denetim_kaydi_olustur(VT_AYARLARI, "DELETE", yetkili_id, "ogrenci_faaliyet_takip", takip_id)
        except ImportError:
            pass

        conn.commit()
        return {"durum": "basarili", "mesaj": "Kayıt başarıyla silindi!"}
    except Exception as e:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail=f"Silme hatası: {str(e)}")
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()