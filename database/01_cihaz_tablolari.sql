-- 1. Cihaz Durumları (Enum)
CREATE TYPE cihaz_durumu AS ENUM ('Kullanima_Hazir', 'Rezerve', 'Kullanimda', 'Arizali', 'Bakimda', 'Kalibrasyonda', 'Kullanim_Disi');

-- 2. Bölümler Tablosu (Cihazların kiralandığı/verildiği yerler)
CREATE TABLE bolumler (
    bolum_id SERIAL PRIMARY KEY,
    bolum_adi VARCHAR(150) UNIQUE NOT NULL, -- Örn: "Nöroloji Laboratuvarı", "Biyomedikal Mühendisliği"
    sorumlu_ad_soyad VARCHAR(100) NOT NULL, -- Teslim alan yetkilinin adı soyadı (Hasta verisi olmadığı için serbest)
    iletisim_bilgisi VARCHAR(100), -- Telefon veya dahili numara
    aktif_mi BOOLEAN DEFAULT TRUE
);

-- 3. Ana Cihazlar Tablosu (devices)
CREATE TABLE cihazlar (
    cihaz_id SERIAL PRIMARY KEY,
    envanter_kodu VARCHAR(50) UNIQUE NOT NULL,
    cihaz_adi VARCHAR(100) NOT NULL,
    marka_model VARCHAR(100),
    seri_no VARCHAR(100) UNIQUE,
    zimmetli_oda_id INT REFERENCES odalar(oda_id), 
    durum cihaz_durumu DEFAULT 'Kullanima_Hazir',
    kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Cihaz Rezervasyon Tablosu (device_reservations)
CREATE TABLE cihaz_rezervasyonlari (
    rezervasyon_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bolum_id INT REFERENCES bolumler(bolum_id), -- Cihazın kiralandığı dış/iç bölüm
    rezervasyonu_yapan_personel_id INT REFERENCES personel(personel_id), 
    baslangic_zamani TIMESTAMP NOT NULL,
    bitis_zamani TIMESTAMP NOT NULL,
    iptal_edildi_mi BOOLEAN DEFAULT FALSE, 
    kullanilacak_oda_id INT REFERENCES odalar(oda_id) 
);

-- 5. Cihaz Arıza Takip Tablosu (device_failures)
CREATE TABLE cihaz_arizalari (
    ariza_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bildiren_personel VARCHAR(100),
    ariza_aciklamasi TEXT NOT NULL,
    bildirim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cozum_tarihi TIMESTAMP,
    cozuldu_mu BOOLEAN DEFAULT FALSE
);

-- 6. Cihaz Bakım Tablosu (device_maintenance)
CREATE TABLE cihaz_bakimlari (
    bakim_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bakim_yapan_kisi VARCHAR(100),
    yapilan_islem TEXT,
    maliyet DECIMAL(10, 2),
    bakim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Cihaz Kalibrasyon Tablosu (device_calibrations)
CREATE TABLE cihaz_kalibrasyonlari (
    kalibrasyon_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    kalibrasyon_yapan_kurum VARCHAR(100),
    gecerlilik_tarihi DATE,
    sertifika_no VARCHAR(100),
    islem_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);