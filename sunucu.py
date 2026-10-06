from fastapi import FastAPI, HTTPException
import psycopg2
import os
from dotenv import load_dotenv

from modeller import GirisModeli
from guvenlik import parola_dogrula

load_dotenv()

app = FastAPI()

VT_AYARLARI = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT")
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

        return {
            "durum": "basarili",
            "mesaj": "Giriş başarılı.",
            "kullanici_id": kullanici[0],
            "kullanici_adi": kullanici[1],
            "rol_id": kullanici[3]
        }

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()