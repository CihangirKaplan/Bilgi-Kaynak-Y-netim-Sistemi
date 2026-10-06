from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import psycopg2
import os
from dotenv import load_dotenv
import jwt

from modeller import GirisModeli
from guvenlik import parola_dogrula, access_token_olustur, token_dogrula


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


def mevcut_kullanici_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> int:
    try:
        token = credentials.credentials
        kullanici_id = token_dogrula(token)

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token süresi dolmuş."
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Geçersiz token."
        )

    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT aktif_mi
            FROM kullanicilar
            WHERE kullanici_id = %s;
            """,
            (kullanici_id,)
        )

        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(
                status_code=401,
                detail="Kullanıcı bulunamadı."
            )

        if not kullanici[0]:
            raise HTTPException(
                status_code=403,
                detail="Kullanıcı hesabı aktif değil."
            )

        return kullanici_id

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

    
def izin_kontrol(izin_adi: str):
    def kontrol(
        kullanici_id: int = Depends(mevcut_kullanici_id)
    ):
        conn = None
        cursor = None

        try:
            conn = psycopg2.connect(**VT_AYARLARI)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT ri.izin_var
                FROM kullanicilar k
                JOIN rol_izinleri ri
                    ON k.rol_id = ri.rol_id
                JOIN izinler i
                    ON ri.izin_id = i.izin_id
                WHERE k.kullanici_id = %s
                  AND i.izin_adi = %s;
                """,
                (kullanici_id, izin_adi)
            )

            sonuc = cursor.fetchone()

            if sonuc is None or sonuc[0] != 1:
                raise HTTPException(
                    status_code=403,
                    detail="Bu işlem için yetkiniz bulunmuyor."
                )

            return kullanici_id

        finally:
            if cursor is not None:
                cursor.close()

            if conn is not None:
                conn.close()

    return kontrol


@app.get("/api/korumali-test")
def korumali_test(
    kullanici_id: int = Depends(mevcut_kullanici_id)
):
    return {
        "durum": "basarili",
        "mesaj": "Token geçerli.",
        "kullanici_id": kullanici_id
    }


@app.get("/api/yetki-test")
def yetki_test(
    kullanici_id: int = Depends(izin_kontrol("CIHAZ_EKLE"))
):
    return {
        "durum": "basarili",
        "mesaj": "Kullanıcının CIHAZ_EKLE izni var.",
        "kullanici_id": kullanici_id
    }



@app.get("/api/cihazlar")
def cihazlari_getir():
    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()
        cursor.execute("SELECT envanter_kodu, cihaz_adi, durum FROM cihazlar;")
        kayitlar = cursor.fetchall()
        
        veri = []
        for k in kayitlar:
            veri.append({
                "envanter_kodu": k[0],
                "cihaz_adi": k[1],
                "durum": k[2]
            })
            
        cursor.close()
        conn.close()
        return {"durum": "basarili", "veri": veri}
    except Exception as e:
        return {"durum": "hata", "mesaj": str(e)}


# AUTH-004: Login Endpointi
@app.post("/api/login")
def giris_yap(giris: GirisModeli):
    conn = None
    cursor = None

    try:
        conn = psycopg2.connect(**VT_AYARLARI)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT kullanici_id, kullanici_adi, parola_hash, rol_id, aktif_mi
            FROM kullanicilar
            WHERE kullanici_adi = %s;
            """,
            (giris.kullanici_adi,)
        )

        kullanici = cursor.fetchone()

        if kullanici is None:
            raise HTTPException(
                status_code=401,
                detail="Kullanıcı adı veya parola hatalı."
            )

        if not kullanici[4]:
            raise HTTPException(
                status_code=403,
                detail="Kullanıcı hesabı aktif değil."
            )

        if not parola_dogrula(giris.parola, kullanici[2]):
            raise HTTPException(
                status_code=401,
                detail="Kullanıcı adı veya parola hatalı."
            )

        access_token = access_token_olustur(kullanici[0])

        return {
            "durum": "basarili",
            "mesaj": "Giriş başarılı.",
            "access_token": access_token,
            "token_type": "bearer",
            "kullanici_id": kullanici[0],
            "kullanici_adi": kullanici[1],
            "rol_id": kullanici[3]
        }

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()
