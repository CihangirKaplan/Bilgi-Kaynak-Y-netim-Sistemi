import psycopg2

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

    # 2. TEST VERİLERİNİ EKLEME (INSERT SORGULARI)
    test_verileri = """
    -- Test cihazı eklenecek örnek bir oda
    INSERT INTO odalar (oda_adi, kapasite) VALUES ('Görüntüleme Merkezi', 5) ON CONFLICT DO NOTHING;

    -- 2 Adet Test Cihazı (Senin merkezin)
    INSERT INTO cihazlar (envanter_kodu, cihaz_adi, marka_model, seri_no, zimmetli_oda_id, durum) 
    VALUES 
    ('ENV-MRI-001', 'Gelişmiş MRI Cihazı', 'Siemens Magnetom', 'SN-987654321', 1, 'Kullanima_Hazir'),
    ('ENV-XR-002', 'Taşınabilir X-Ray', 'Philips MobileDiagnost', 'SN-123456789', 1, 'Kullanimda')
    ON CONFLICT DO NOTHING;

    -- MRI Cihazı için Test Takip Parametresi
    INSERT INTO cihaz_takip_parametreleri (cihaz_id, parametre_adi, parametre_degeri, birim)
    VALUES 
    (1, 'Helyum Seviyesi', '85', '%'),
    (1, 'Soğutma Sıcaklığı', '-269', 'Derece');

    -- X-Ray Cihazı İçin Periyodik Bakım Planı
    INSERT INTO cihaz_bakim_planlari (cihaz_id, gorev_turu, periyot_gun, uyari_suresi_gun, sonraki_gorev_tarihi)
    VALUES 
    (2, 'Tüp Kalibrasyonu ve Temizlik', 7, 2, CURRENT_DATE + INTERVAL '5 days');
    """

    # Sorguyu çalıştır ve yerel veritabanına kaydet
    cursor.execute(test_verileri)
    conn.commit()
    
    print("🚀 Test cihazları, parametreler ve bakım planları YEREL sisteme başarıyla eklendi!")

except Exception as e:
    print(f"❌ Bağlantı veya Ekleme Hatası: {e}")
finally:
    if 'conn' in locals():
        cursor.close()
        conn.close()