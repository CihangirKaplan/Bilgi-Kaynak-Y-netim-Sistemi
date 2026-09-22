
-- 1. ROLLER
CREATE TABLE roller (
    rol_id SERIAL PRIMARY KEY,
    rol_adi VARCHAR(50) UNIQUE NOT NULL
);


-- 2. KULLANICILAR
CREATE TABLE kullanicilar (
    kullanici_id SERIAL PRIMARY KEY,
    kullanici_adi VARCHAR(100) UNIQUE NOT NULL,
    parola_hash VARCHAR(255) NOT NULL,

    rol_id INT NOT NULL
        REFERENCES roller(rol_id),

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 3. PERSONEL
CREATE TABLE personel (
    personel_id SERIAL PRIMARY KEY,

    kullanici_id INT UNIQUE NOT NULL
        REFERENCES kullanicilar(kullanici_id),

    personel_kodu VARCHAR(50) UNIQUE NOT NULL,

    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- 4. DENETIM OLAY TURU
CREATE TYPE denetim_olay_turu AS ENUM (
    'LOGIN',
    'LOGIN_FAILED',
    'CREATE',
    'UPDATE',
    'CANCEL',
    'ROLE_CHANGE',
    'DEVICE_STATUS_CHANGE'
);


-- 5. DENETIM KAYITLARI
CREATE TABLE denetim_kayitlari (
    denetim_id BIGSERIAL PRIMARY KEY,

    kullanici_id INT
        REFERENCES kullanicilar(kullanici_id),

    olay_turu denetim_olay_turu NOT NULL,

    hedef_tablo VARCHAR(100),

    hedef_kayit_id INT,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);