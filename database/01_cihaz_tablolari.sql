-- 1. Cihaz Durumları (Markdown dosyasında belirlediğimiz kuralların veritabanı karşılığı)
CREATE TYPE cihaz_durumu AS ENUM ('Kullanima_Hazir', 'Rezerve', 'Kullanimda', 'Arizali', 'Bakimda', 'Hurda');

-- 2. Ana Cihazlar Tablosu (Envanter listemiz)
CREATE TABLE cihazlar (
    cihaz_id SERIAL PRIMARY KEY,
    envanter_kodu VARCHAR(50) UNIQUE NOT NULL, -- Örn: CHZ-001
    cihaz_adi VARCHAR(100) NOT NULL,
    marka_model VARCHAR(100),
    seri_no VARCHAR(100) UNIQUE,
    zimmetli_oda_id INT, -- İleride Öğrenci A'nın "odalar" tablosuna bağlanacak
    durum cihaz_durumu DEFAULT 'Kullanima_Hazir',
    son_kalibrasyon_tarihi DATE,
    kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Cihaz Arıza Takip Tablosu (Arızalanan cihazların geçmişini tutacağımız yer)
CREATE TABLE cihaz_arizalari (
    ariza_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bildiren_personel VARCHAR(100),
    ariza_aciklamasi TEXT NOT NULL,
    bildirim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cozum_tarihi TIMESTAMP,
    cozuldu_mu BOOLEAN DEFAULT FALSE
);

-- 4. Cihaz Bakım ve Kalibrasyon Tablosu
CREATE TABLE cihaz_bakimlari (
    bakim_id SERIAL PRIMARY KEY,
    cihaz_id INT REFERENCES cihazlar(cihaz_id),
    bakim_yapan_kisi VARCHAR(100),
    yapilan_islem TEXT,
    maliyet DECIMAL(10, 2),
    bakim_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);