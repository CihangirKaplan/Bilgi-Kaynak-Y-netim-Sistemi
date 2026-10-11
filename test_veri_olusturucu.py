import psycopg2
# Kendi güvenlik fonksiyonlarımızı import ediyoruz
from guvenlik import parola_hashle 

# 1. YEREL (LOCALHOST) VERİTABANI BAĞLANTI AYARLARI
DB_HOST = "localhost"  
DB_NAME = "crkys"
DB_USER = "postgres"
DB_PASS = "123" 
DB_PORT = "5432"

try:
    # Veritabanına bağlanıyoruz
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    cursor = conn.cursor()
    print("✅ Yerel (Localhost) veritabanına başarıyla bağlanıldı!\n")

    # API'mizin kendi yöntemiyle "12345" şifresini hashliyoruz
    gercek_hash = parola_hashle("12345")

    # 2. TEST VERİLERİNİ EKLEME (INSERT SORGULARI)
    test_verileri = f"""
    -- Roller (Garanti Olsun)
    INSERT INTO roller (rol_adi) VALUES ('PSIKOLOG') ON CONFLICT DO NOTHING;

    -- Test Odaları
    INSERT INTO odalar (oda_adi, kapasite, aktif_mi) VALUES 
    ('Görüntüleme Merkezi', 5, TRUE),
    ('Psikoterapi Odası 1', 2, TRUE) ON CONFLICT DO NOTHING;

    -- Test Danışan Kodları
    INSERT INTO danisan_kodlari (danisan_kod_id, ucretli_mi, aktif_mi) VALUES 
    ('DAN-2026-0001', TRUE, TRUE) ON CONFLICT DO NOTHING;

    -- TEST PSİKOLOĞU (Burada Python'un anlık oluşturduğu Hash'i kullanıyoruz)
    INSERT INTO kullanicilar (kullanici_adi, parola_hash, rol_id, aktif_mi, basarisiz_giris_sayisi) 
    VALUES (
        'doktor_cihangir',
        '{gercek_hash}',
        (SELECT rol_id FROM roller WHERE rol_adi = 'PSIKOLOG' LIMIT 1),
        TRUE,
        0
    ) ON CONFLICT (kullanici_adi) DO UPDATE SET parola_hash = '{gercek_hash}', aktif_mi = TRUE, basarisiz_giris_sayisi = 0;

    -- Personel Kaydı
    INSERT INTO personel (kullanici_id, personel_kodu, aktif_mi) 
    VALUES (
        (SELECT kullanici_id FROM kullanicilar WHERE kullanici_adi = 'doktor_cihangir'),
        'PER-001',
        TRUE
    ) ON CONFLICT (kullanici_id) DO NOTHING;
    """

    # Sorguyu çalıştır ve yerel veritabanına kaydet
    cursor.execute(test_verileri)
    conn.commit()
    
    print("🚀 Test kullanıcısı (doktor_cihangir) ve odalar başarıyla eklendi!")
    print("🔑 Giriş Bilgileri -> Kullanıcı Adı: doktor_cihangir | Şifre: 12345")

except Exception as e:
    print(f"❌ Bağlantı veya Ekleme Hatası: {e}")
finally:
    if 'conn' in locals():
        cursor.close()
        conn.close()