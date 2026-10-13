from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
from psycopg2.errors import ExclusionViolation
import os
from dotenv import load_dotenv
import jwt
from datetime import datetime, timedelta
from modeller import GirisModeli, RandevuOlusturModeli, RandevuGuncelleModeli, DanisanKoduModeli 
from guvenlik import parola_dogrula, access_token_olustur, token_dogrula
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

# CLI-001 / CLI-002: Otomatik danışan kodu üretimi
def otomatik_danisan_kodu_uret(cursor) -> str:
    yil = datetime.now().year
    
    # Sequence kullanmak yerine doğrudan tablodaki o yıla ait en büyük koda bakıyoruz
    cursor.execute(f"SELECT danisan_kod_id FROM danisan_kodlari WHERE danisan_kod_id LIKE 'DAN-{yil}-%%' ORDER BY danisan_kod_id DESC LIMIT 1;")
    son_kayit = cursor.fetchone()
    
    if son_kayit:
        # DAN-2026-0002 -> Son parçayı al, 1 ekle
        son_kod = son_kayit[0]
        sira = int(son_kod.split('-')[-1]) + 1
    else:
        sira = 1
        
    return f"DAN-{yil}-{sira:04d}"

def mevcut_kullanici_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> int:
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
        cursor.execute("SELECT aktif_mi FROM kullanicilar WHERE kullanici_id = %s;", (kullanici_id,))
        kullanici = cursor.fetchone()
        if kullanici is None:
            raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı.")
        if not kullanici[0]:
            raise HTTPException(status_code=403, detail="Kullanıcı hesabı aktif değil.")
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
                   basarisiz_giris_sayisi, kilit_bitis_zamani
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
            "rol_id": kullanici[3]
        }
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.get("/api/randevular/siradaki-kod")
def siradaki_danisan_kodunu_ver(kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))):
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        
        # Artık doğrudan fonksiyonu çağırıyoruz, sequence ile uğraşmıyoruz
        siradaki_kod = otomatik_danisan_kodu_uret(cursor)
        return {"siradaki_kod": siradaki_kod}
    except Exception:
        yil = datetime.now().year
        return {"siradaki_kod": f"DAN-{yil}-0001"}
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()

@app.post("/api/randevular", status_code=201)
def randevu_olustur(
    randevu: RandevuOlusturModeli,
    kullanici_id: int = Depends(izin_kontrol("RANDEVU_OLUSTUR"))
):
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

        # DÜZELTİLEN YER: Danışan kodu dışarıdan beklenmiyor, sunucu kendi üretiyor ve MÜHÜRLÜYOR!
        yeni_danisan_kodu = otomatik_danisan_kodu_uret(cursor)
        cursor.execute(
            """
            INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, istisna_turu, aktif_mi)
            VALUES (%s, TRUE, 'YOK', TRUE);
            """,
            (yeni_danisan_kodu,)
        )

        cursor.execute("SELECT 1 FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND r.rol_adi = 'PSIKOLOG';", (randevu.psikolog_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")
            
        cursor.execute("SELECT 1 FROM odalar WHERE oda_id = %s AND aktif_mi = TRUE;", (randevu.oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Oda bulunamadı veya aktif değil.")

        cursor.execute(
            """
            SELECT 1 FROM randevular WHERE durum = 'PLANLANDI' AND (psikolog_id = %s OR oda_id = %s) AND baslangic_zamani < %s AND bitis_zamani > %s LIMIT 1;
            """, (randevu.psikolog_id, randevu.oda_id, randevu.bitis_zamani, randevu.baslangic_zamani)
        )
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=409, detail="Seçilen psikolog veya oda bu saatlerde dolu.")

        cursor.execute(
            """
            INSERT INTO randevular (danisan_kod_id, psikolog_id, oda_id, baslangic_zamani, bitis_zamani, durum)
            VALUES (%s, %s, %s, %s, %s, 'PLANLANDI') RETURNING randevu_id;
            """, (yeni_danisan_kodu, randevu.psikolog_id, randevu.oda_id, randevu.baslangic_zamani, randevu.bitis_zamani)
        )
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
        return [
            {"randevu_id": kayit[0], "danisan_kod_id": kayit[1], "psikolog_id": kayit[2], "oda_id": kayit[3], "baslangic_zamani": kayit[4], "bitis_zamani": kayit[5], "durum": kayit[6]} for kayit in kayitlar
        ]
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
        if rol is None or rol[0] not in ("PSIKOLOG", "ADMIN", "DANISMA_OGRENCISI"):
            raise HTTPException(status_code=403, detail="Randevu düzenleme yetkiniz yok.")
            
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

        cursor.execute("SELECT 1 FROM danisan_kodlari WHERE danisan_kod_id = %s AND aktif_mi = TRUE;", (danisan_kod_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Danışan kodu bulunamadı veya aktif değil.")

        cursor.execute("SELECT 1 FROM personel p JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id JOIN roller r ON k.rol_id = r.rol_id WHERE p.personel_id = %s AND p.aktif_mi = TRUE AND k.aktif_mi = TRUE AND r.rol_adi = 'PSIKOLOG';", (psikolog_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Geçerli ve aktif bir psikolog seçilmelidir.")

        cursor.execute("SELECT 1 FROM odalar WHERE oda_id = %s AND aktif_mi = TRUE;", (oda_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=422, detail="Oda bulunamadı veya aktif değil.")

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
        if rol is None or rol[0] not in ("PSIKOLOG", "ADMIN", "DANISMA_OGRENCISI"):
            raise HTTPException(status_code=403, detail="Randevu iptal etme yetkiniz yok.")

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

@app.post("/api/danisan-kodlari", status_code=201, summary="Yeni Otomatik Danışan Kodu Oluştur")
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
    except HTTPException:
        if conn is not None: conn.rollback()
        raise
    except psycopg2.Error:
        if conn is not None: conn.rollback()
        raise HTTPException(status_code=500, detail="Danışan kodu oluşturulurken bir hata oluştu.")
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
        
        # p.ad ve p.soyad OLMADIĞI İÇİN doğrudan k.kullanici_adi çekiyoruz
        cursor.execute("""
            SELECT p.personel_id, k.kullanici_adi 
            FROM personel p
            JOIN kullanicilar k ON p.kullanici_id = k.kullanici_id
            JOIN roller r ON k.rol_id = r.rol_id
            WHERE p.aktif_mi = TRUE 
              AND k.aktif_mi = TRUE 
              AND UPPER(r.rol_adi) = 'PSIKOLOG'; 
        """)
        kayitlar = cursor.fetchall()
        
        return [
            # Frontend "ad_soyad" beklediği için anahtarı öyle bırakıp değeri kullanıcı adı yapıyoruz
            {"personel_id": k[0], "ad_soyad": k[1]}
            for k in kayitlar
        ]
    finally:
        if cursor is not None: cursor.close()
        if conn is not None: conn.close()