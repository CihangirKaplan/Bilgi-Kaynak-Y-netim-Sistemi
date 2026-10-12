import psycopg2
from guvenlik import parola_hashle
import os
from dotenv import load_dotenv

load_dotenv()

# .env dosyasından ayarları okuyoruz
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

# Takım arkadaşları için toplu test kullanıcıları listesi
TEST_KULLANICILARI = [
    {"k_adi": "doktor_cihangir", "sifre": "Cihangir.123", "rol": "PSIKOLOG", "ad": "Cihangir", "soyad": "Kaplan", "unvan": "Uzman Psikolog"},
    {"k_adi": "admin", "sifre": "Admin.123", "rol": "ADMIN", "ad": "Sistem", "soyad": "Yöneticisi", "unvan": "Kurucu Admin"},
    {"k_adi": "memur", "sifre": "Memur.123", "rol": "MEMUR", "ad": "Ahmet", "soyad": "Yılmaz", "unvan": "Cihaz Sorumlusu"},
    {"k_adi": "mudur", "sifre": "Mudur.123", "rol": "MUDUR", "ad": "Ayşe", "soyad": "Kaya", "unvan": "Klinik Müdürü"},
    {"k_adi": "ogrenci", "sifre": "Ogrenci.123", "rol": "DANISMA_OGRENCISI", "ad": "Can", "soyad": "Öztürk", "unvan": "Stajyer Öğrenci"},
    {"k_adi": "asistan", "sifre": "Asistan.123", "rol": "ASISTAN", "ad": "Fatma", "soyad": "Çelik", "unvan": "Proje Asistanı"}
]

def ilk_kurulumu_yap():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT)
        cursor = conn.cursor()
        print("🚀 Veritabanına bağlanıldı, tohumlama (seeding) başlatılıyor...\n")

        for k in TEST_KULLANICILARI:
            # 1. ROLÜ KONTROL ET VE YOKSA EKLE
            cursor.execute("SELECT rol_id FROM roller WHERE rol_adi = %s;", (k["rol"],))
            rol = cursor.fetchone()
            if not rol:
                cursor.execute("INSERT INTO roller (rol_adi) VALUES (%s) RETURNING rol_id;", (k["rol"],))
                rol_id = cursor.fetchone()[0]
            else:
                rol_id = rol[0]

            # 2. KULLANICIYI KONTROL ET VE YOKSA EKLE
            cursor.execute("SELECT kullanici_id FROM kullanicilar WHERE kullanici_adi = %s;", (k["k_adi"],))
            kullanici = cursor.fetchone()
            
            if not kullanici:
                # Şifreyi güvenlik modülüyle hashle
                hashli_sifre = parola_hashle(k["sifre"])
                
                cursor.execute("""
                    INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, basarisiz_giris_sayisi) 
                    VALUES (%s, %s, %s, TRUE, 0) 
                    RETURNING kullanici_id;
                """, (k["k_adi"], hashli_sifre, rol_id))
                kullanici_id = cursor.fetchone()[0]
                
                # 3. KULLANICIYI PERSONEL TABLOSUNA BAĞLA (Randevu işlemleri için şart)
                cursor.execute("""
                    INSERT INTO personel (kullanici_id, ad, soyad, unvan, aktif_mi) 
                    VALUES (%s, %s, %s, %s, TRUE);
                """, (kullanici_id, k["ad"], k["soyad"], k["unvan"]))
                
                print(f"✅ Eklendi: {k['k_adi']} (Rol: {k['rol']})")
            else:
                print(f"⚠️ Zaten Mevcut: {k['k_adi']}")

        conn.commit()
        print("\n🎉 Tüm test kullanıcıları başarıyla veritabanına işlendi!")

    except Exception as e:
        print(f"❌ Kurulum Hatası: {e}")
        if conn: conn.rollback()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    ilk_kurulumu_yap()