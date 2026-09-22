-- 1. Cihaz Durumları (Enum)
CREATE TYPE cihaz_durumu AS ENUM ('Kullanima_Hazir', 'Rezerve', 'Kullanimda', 'Arizali', 'Bakimda', 'Kalibrasyonda', 'Kullanim_Disi');

-- 2. Ana Cihazlar Tablosu (devices)
CREATE TABLE cihazlar (
    cihaz_id SERIAL PRIMARY KEY,
    envanter_kodu VARCHAR(50) UNIQUE NOT NULL,
    cihaz_adi VARCHAR(100) NOT NULL,
    marka_model VARCHAR(100),
    seri_no VARCHAR(100) UNIQUE,
    zimmetli_oda_id INT, -- İleride Öğrenci A'nın 'rooms' tablosuna bağlanacak
    durum cihaz_durumu DEFAULT 'Kullanima_Hazir',
    kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Cihaz Rezervasyon Tablosu (device_reservations)
CREATE TABLE cihaz_rezervasyonlari (
    rezervasyon_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    randevu_id INT, -- İleride Öğrenci A'nın 'appointments' tablosuna bağlanacak
    personel_id INT, -- İleride Öğrenci C'nin 'staff' veya 'users' tablosuna bağlanacak
    baslangic_zamani TIMESTAMP NOT NULL,
    bitis_zamani TIMESTAMP NOT NULL,
    iptal_edildi_mi BOOLEAN DEFAULT FALSE
);

-- 4. Cihaz Arıza Takip Tablosu (device_failures)
CREATE TABLE cihaz_arizalari (
    ariza_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bildiren_personel VARCHAR(100),
    ariza_aciklamasi TEXT NOT NULL,
    bildirim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cozum_tarihi TIMESTAMP,
    cozuldu_mu BOOLEAN DEFAULT FALSE
);

-- 5. Cihaz Bakım Tablosu (device_maintenance)
CREATE TABLE cihaz_bakimlari (
    bakim_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bakim_yapan_kisi VARCHAR(100),
    yapilan_islem TEXT,
    maliyet DECIMAL(10, 2),
    bakim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Cihaz Kalibrasyon Tablosu (device_calibrations)
CREATE TABLE cihaz_kalibrasyonlari (
    kalibrasyon_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    kalibrasyon_yapan_kurum VARCHAR(100),
    gecerlilik_tarihi DATE,
    sertifika_no VARCHAR(100),
    islem_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);