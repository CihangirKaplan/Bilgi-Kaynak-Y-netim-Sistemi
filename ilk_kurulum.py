import psycopg2
from guvenlik import parola_hashle
import os
from dotenv import load_dotenv

load_dotenv()

# .env dosyasından ayarları okuyoruz
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "crkys")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD")  # varsayılan şifre yok; .env içinde tanımlı olmalı
DB_PORT = os.getenv("DB_PORT", "5432")

# Takım arkadaşları için toplu test kullanıcıları listesi
# Arayüzdeki güncel 'personel_kodu' mimarisine uyarlandı.
TEST_KULLANICILARI = [
    # 1. Psikolog
    {"k_adi": "psikolog1", "sifre": "Psikolog1.123", "rol": "PSIKOLOG", "p_kodu": "PER-PSK-001"},
    {"k_adi": "psikolog2", "sifre": "Psikolog2.123", "rol": "PSIKOLOG", "p_kodu": "PER-PSK-002"}, 
    {"k_adi": "admin", "sifre": "Admin.123", "rol": "ADMIN", "p_kodu": "PER-ADM-001"},
    {"k_adi": "memur", "sifre": "Memur.123", "rol": "MEMUR", "p_kodu": "PER-MEM-001"},
    {"k_adi": "mudur", "sifre": "Mudur.123", "rol": "MUDUR", "p_kodu": "PER-MUD-001"},
    {"k_adi": "ogrenci", "sifre": "Ogrenci.123", "rol": "DANISMA_OGRENCISI", "p_kodu": "PER-OGR-001"},
    {"k_adi": "asistan", "sifre": "Asistan.123", "rol": "PROJE_ASISTANI", "p_kodu": "PER-AST-001"}
]
def ilk_kurulumu_yap():
    if not DB_PASS:
        print("❌ .env dosyasında DB_PASSWORD tanımlı değil (bkz. .env.example). Kurulum yapılmadı.")
        return

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
                hashli_sifre = parola_hashle(k["sifre"])
                cursor.execute("""
                    INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, basarisiz_giris_sayisi) 
                    VALUES (%s, %s, %s, TRUE, 0) 
                    RETURNING kullanici_id;
                """, (k["k_adi"], hashli_sifre, rol_id))
                kullanici_id = cursor.fetchone()[0]
                print(f"✅ Kullanıcı Eklendi: {k['k_adi']} (Rol: {k['rol']})")
            else:
                kullanici_id = kullanici[0]
                print(f"⚠️ Kullanıcı Zaten Mevcut: {k['k_adi']}")

            # 3. KULLANICIYI PERSONEL TABLOSUNA BAĞLA (Mimarine Uygun Olarak)
            cursor.execute("SELECT * FROM personel WHERE kullanici_id = %s;", (kullanici_id,))
            personel = cursor.fetchone()
            
            if not personel:
                cursor.execute("""
                    INSERT INTO personel (kullanici_id, personel_kodu, aktif_mi) 
                    VALUES (%s, %s, TRUE);
                """, (kullanici_id, k["p_kodu"]))
                print(f"   └─ ✅ Personel Kaydı Oluşturuldu: {k['p_kodu']}")
            else:
                print(f"   └─ ⚠️ Personel Kaydı Zaten Var")

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