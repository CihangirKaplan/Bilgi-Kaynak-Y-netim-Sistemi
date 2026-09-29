import psycopg2

VT_AYARLARI = {
    "dbname": "04_test_verisi", 
    "user": "postgres",
    "password": "123",   
    "host": "localhost",
    "port": "5432"
}

sql_sorgusu = """
INSERT INTO odalar (oda_adi) VALUES ('Depo 1');

INSERT INTO cihazlar (envanter_kodu, cihaz_adi, durum, zimmetli_oda_id) 
VALUES 
('ENV-001', 'Defibrilatör Cihazı', 'Kullanima_Hazir', 1),
('ENV-002', 'EKG Monitörü', 'Arizali', 1);
"""

try:
    print("Veritabanına bağlanılıyor...")
    baglanti = psycopg2.connect(**VT_AYARLARI)
    imlec = baglanti.cursor()
    
    # Kodu çalıştır
    imlec.execute(sql_sorgusu)
    
    # Değişiklikleri veritabanına mühürle (commit)
    baglanti.commit()
    print("Veriler başarıyla eklendi!")
    
    imlec.close()
    baglanti.close()
except Exception as hata:
    print("Bir hata oluştu", hata)