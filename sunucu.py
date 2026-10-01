from fastapi import FastAPI
import psycopg2

app = FastAPI()

VT_AYARLARI = {
    "dbname": "bkys",
    "user": "postgres",
    "password": "123", 
    "host": "172.24.4.66", 
    "port": "5432"
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