
-- 1. ROLLER
CREATE TABLE roller (
    rol_id SERIAL PRIMARY KEY,
    rol_adi VARCHAR(50) UNIQUE NOT NULL
);


-- 2. KULLANICILAR
-- Sisteme giriş yapabilen kullanıcı hesaplarını tutar.
CREATE TABLE kullanicilar (
    kullanici_id SERIAL PRIMARY KEY,

    kullanici_adi VARCHAR(100) UNIQUE NOT NULL,

    parola_hash VARCHAR(255) NOT NULL,

    rol_id INT NOT NULL
        REFERENCES roller(rol_id),

    -- Kullanıcının sisteme giriş yapıp yapamayacağını belirtir.
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 3. PERSONEL
-- Kurum personellerine ait kayıtları tutar.
CREATE TABLE personel (
    personel_id SERIAL PRIMARY KEY,

    kullanici_id INT UNIQUE NOT NULL
        REFERENCES kullanicilar(kullanici_id),

    personel_kodu VARCHAR(50) UNIQUE NOT NULL,

    -- Personelin kurumdaki aktiflik durumunu belirtir.
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 4. DANISMA MASASI OGRENCILERI
-- Danışma masasında görev yapan ve sisteme giriş yetkisi bulunan
-- öğrencilere ait gerekli bilgileri tutar.
CREATE TABLE danisma_ogrencileri (
    ogrenci_id SERIAL PRIMARY KEY,

    -- Öğrencinin sistem hesabı ile bağlantısını kurar.
    kullanici_id INT UNIQUE NOT NULL
        REFERENCES kullanicilar(kullanici_id),

    ad_soyad VARCHAR(100) NOT NULL,

    ogrenci_numarasi VARCHAR(50) UNIQUE NOT NULL,

    telefon VARCHAR(20),

    -- Öğrencinin danışma masasında aktif görev yapıp yapmadığını belirtir.
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 5. DENETIM OLAY TURU
CREATE TYPE denetim_olay_turu AS ENUM (
    'LOGIN',
    'LOGIN_FAILED',
    'CREATE',
    'UPDATE',
    'CANCEL',
    'ROLE_CHANGE',
    'DEVICE_STATUS_CHANGE'
);


-- 6. DENETIM KAYITLARI
-- Sistemde gerçekleşen kritik işlemlerin kayıtlarını tutar.
CREATE TABLE denetim_kayitlari (
    denetim_id BIGSERIAL PRIMARY KEY,

    -- İşlemi gerçekleştiren kullanıcı.
    -- LOGIN_FAILED gibi durumlar nedeniyle NULL olabilir.
    kullanici_id INT
        REFERENCES kullanicilar(kullanici_id),

    olay_turu denetim_olay_turu NOT NULL,

    -- İşlemden etkilenen tablo.
    hedef_tablo VARCHAR(100),

    -- İşlemden etkilenen kaydın ID değeri.
    hedef_kayit_id INT,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);