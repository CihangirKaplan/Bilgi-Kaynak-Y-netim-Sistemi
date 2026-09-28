-- ============================================================
-- STUDENT C - BACKEND, SECURITY & PLATFORM
-- KULLANICI, ROL, YETKI, DANISMA OGRENCISI VE AUDIT
-- ============================================================


-- ============================================================
-- 1. ROLLER
-- Sistemde bulunan kullanıcı rollerini tanımlar.
-- ============================================================

CREATE TABLE roller (
    rol_id SERIAL PRIMARY KEY,
    rol_adi VARCHAR(50) UNIQUE NOT NULL
);


-- ============================================================
-- 2. IZINLER
-- Sistemde gerçekleştirilebilecek yetkili işlemleri tanımlar.
-- ============================================================

CREATE TABLE izinler (
    izin_id SERIAL PRIMARY KEY,
    izin_adi VARCHAR(100) UNIQUE NOT NULL,
    aciklama VARCHAR(255)
);


-- ============================================================
-- 3. ROL IZINLERI
-- Her rolün hangi işlemi yapıp yapamayacağını tutar.
--
-- izin_var = 1 -> izin var
-- izin_var = 0 -> izin yok
-- ============================================================

CREATE TABLE rol_izinleri (
    rol_id INT NOT NULL
        REFERENCES roller(rol_id),

    izin_id INT NOT NULL
        REFERENCES izinler(izin_id),

    izin_var SMALLINT NOT NULL
        DEFAULT 0,

    PRIMARY KEY (rol_id, izin_id),

    CHECK (izin_var IN (0, 1))
);


-- ============================================================
-- 4. KULLANICILAR
-- Sisteme giriş yapabilen kullanıcı hesaplarını tutar.
-- ============================================================

CREATE TABLE kullanicilar (
    kullanici_id SERIAL PRIMARY KEY,

    kullanici_adi VARCHAR(100) UNIQUE NOT NULL,

    parola_hash VARCHAR(255) NOT NULL,

    rol_id INT NOT NULL
        REFERENCES roller(rol_id),

    -- TRUE  -> kullanıcı sisteme giriş yapabilir
    -- FALSE -> kullanıcı hesabı pasiftir
    aktif_mi BOOLEAN NOT NULL
        DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 5. PERSONEL
-- Kurum personellerinin operasyonel kayıtlarını tutar.
-- ============================================================

CREATE TABLE personel (
    personel_id SERIAL PRIMARY KEY,

    kullanici_id INT UNIQUE NOT NULL
        REFERENCES kullanicilar(kullanici_id),

    personel_kodu VARCHAR(50) UNIQUE NOT NULL,

    aktif_mi BOOLEAN NOT NULL
        DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 6. DANISMA OGRENCILERI
-- Danışma masasında görev yapan ve sisteme giriş yetkisi
-- bulunan öğrencilere ait bilgileri tutar.
-- ============================================================

CREATE TABLE danisma_ogrencileri (
    ogrenci_id SERIAL PRIMARY KEY,

    kullanici_id INT UNIQUE NOT NULL
        REFERENCES kullanicilar(kullanici_id),

    ad_soyad VARCHAR(100) NOT NULL,

    ogrenci_numarasi VARCHAR(50) UNIQUE NOT NULL,

    telefon VARCHAR(20),

    -- Öğrencinin danışma masasında aktif görev yapıp
    -- yapmadığını belirtir.
    aktif_mi BOOLEAN NOT NULL
        DEFAULT TRUE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- 7. DANISMA MASASI OTURUMLARI
-- Danışma masası öğrencisinin hangi zaman aralığında
-- danışma masasında görev yapacağını tutar.
-- ============================================================

CREATE TABLE danisma_masasi_oturumlari (
    oturum_id SERIAL PRIMARY KEY,

    -- Oturumun hangi öğrenciye ait olduğunu belirtir.
    ogrenci_id INT NOT NULL
        REFERENCES danisma_ogrencileri(ogrenci_id),

    -- Öğrencinin danışma masasına geldiği zaman.
    baslangic_zamani TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    -- Öğrencinin danışma masasında bulunacağını
    -- belirttiği bitiş zamanı.
    bitis_zamani TIMESTAMP NOT NULL,

    -- Girilen zaman bilgisinin onaylanıp
    -- onaylanmadığını belirtir.
    onaylandi_mi BOOLEAN NOT NULL
        DEFAULT FALSE,

    olusturulma_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    -- Oturum bilgisi değiştirildiğinde FastAPI tarafından
    -- güncellenecektir.
    guncellenme_tarihi TIMESTAMP NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    -- Bitiş zamanı başlangıç zamanından sonra olmalıdır.
    CHECK (bitis_zamani > baslangic_zamani)
);


-- ============================================================
-- 8. DENETIM OLAY TURU
-- Audit kayıtlarında kullanılabilecek olay türlerini tanımlar.
-- ============================================================

CREATE TYPE denetim_olay_turu AS ENUM (
    'LOGIN',
    'LOGIN_FAILED',
    'CREATE',
    'UPDATE',
    'CANCEL',
    'ROLE_CHANGE',
    'DEVICE_STATUS_CHANGE'
);


-- ============================================================
-- 9. DENETIM KAYITLARI
-- Sistemde gerçekleşen kritik işlemlerin kayıtlarını tutar.
-- ============================================================

CREATE TABLE denetim_kayitlari (
    denetim_id BIGSERIAL PRIMARY KEY,

    -- LOGIN_FAILED gibi durumlarda geçerli bir kullanıcı
    -- bulunmayabileceği için NULL olabilir.
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


-- ============================================================
-- 10. BASLANGIC VERILERI
-- ============================================================


-- ============================================================
-- 10.1 ROLLER
-- ============================================================

INSERT INTO roller (rol_adi) VALUES
    ('PSIKOLOG'),
    ('MEMUR'),
    ('MUDUR'),
    ('DANISMA_OGRENCISI');


-- ============================================================
-- 10.2 IZINLER
-- ============================================================

INSERT INTO izinler (izin_adi, aciklama) VALUES

    ('RANDEVU_GORUNTULE',
     'Randevuları görüntüleme'),

    ('RANDEVU_OLUSTUR',
     'Randevu oluşturma'),

    ('RANDEVU_DUZENLE',
     'Randevu düzenleme'),

    ('RANDEVU_IPTAL',
     'Randevu iptal etme'),

    ('TAKVIM_GORUNTULE',
     'Randevu takvimini görüntüleme'),

    ('ODA_DURUMU_GORUNTULE',
     'Oda kullanım durumunu görüntüleme'),

    ('CIHAZ_UYGUNLUK_GORUNTULE',
     'Cihaz uygunluğunu görüntüleme'),

    ('CIHAZ_ENVANTER_YONET',
     'Cihaz envanterini yönetme'),

    ('CIHAZ_REZERVASYON',
     'Cihaz rezervasyonu yapma'),

    ('BAKIM_KAYITLARI_YONET',
     'Bakım kayıtlarını yönetme'),

    ('KALIBRASYON_KAYITLARI_YONET',
     'Kalibrasyon kayıtlarını yönetme'),

    ('ARIZA_KAYITLARI_YONET',
     'Arıza kayıtlarını yönetme'),

    ('KULLANICI_OLUSTUR',
     'Kullanıcı oluşturma'),

    ('PERSONEL_TANIMLA',
     'Personel tanımlama'),

    ('KULLANICI_PASIFLESTIR',
     'Kullanıcı pasifleştirme'),

    ('ROL_ATAMA_DEGISTIRME',
     'Rol atama veya değiştirme'),

    ('AUDIT_KAYITLARI_INCELE',
     'Audit kayıtlarını inceleme'),

    ('DANISMA_OTURUMU_YONET',
     'Danışma masası oturumunu yönetme'),

    ('CIHAZ_EKLE',
     'Sisteme yeni cihaz ekleme');


-- ============================================================
-- 10.3 PSIKOLOG IZINLERI
--
-- 1 -> izin var
-- 0 -> izin yok
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT
    r.rol_id,
    i.izin_id,

    CASE
        WHEN i.izin_adi IN (
            'RANDEVU_GORUNTULE',
            'RANDEVU_OLUSTUR',
            'RANDEVU_DUZENLE',
            'RANDEVU_IPTAL',
            'TAKVIM_GORUNTULE',
            'ODA_DURUMU_GORUNTULE'
        )
        THEN 1
        ELSE 0
    END

FROM roller r
CROSS JOIN izinler i

WHERE r.rol_adi = 'PSIKOLOG';


-- ============================================================
-- 10.4 MEMUR IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT
    r.rol_id,
    i.izin_id,

    CASE
        WHEN i.izin_adi IN (
            'RANDEVU_GORUNTULE',
            'TAKVIM_GORUNTULE',
            'ODA_DURUMU_GORUNTULE',
            'CIHAZ_UYGUNLUK_GORUNTULE',
            'CIHAZ_ENVANTER_YONET',
            'CIHAZ_REZERVASYON',
            'BAKIM_KAYITLARI_YONET',
            'KALIBRASYON_KAYITLARI_YONET',
            'ARIZA_KAYITLARI_YONET',
            'KULLANICI_PASIFLESTIR',
            'DANISMA_OTURUMU_YONET',
            'CIHAZ_EKLE'
        )
        THEN 1
        ELSE 0
    END

FROM roller r
CROSS JOIN izinler i

WHERE r.rol_adi = 'MEMUR';


-- ============================================================
-- 10.5 MUDUR IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT
    r.rol_id,
    i.izin_id,

    CASE
        WHEN i.izin_adi IN (
            'RANDEVU_GORUNTULE',
            'TAKVIM_GORUNTULE',
            'ODA_DURUMU_GORUNTULE',
            'CIHAZ_UYGUNLUK_GORUNTULE',
            'KULLANICI_OLUSTUR',
            'PERSONEL_TANIMLA',
            'KULLANICI_PASIFLESTIR',
            'ROL_ATAMA_DEGISTIRME',
            'AUDIT_KAYITLARI_INCELE',
            'DANISMA_OTURUMU_YONET',
            'CIHAZ_EKLE'
        )
        THEN 1
        ELSE 0
    END

FROM roller r
CROSS JOIN izinler i

WHERE r.rol_adi = 'MUDUR';


-- ============================================================
-- 10.6 DANISMA OGRENCISI IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT
    r.rol_id,
    i.izin_id,

    CASE
        WHEN i.izin_adi IN (
            'RANDEVU_GORUNTULE',
            'RANDEVU_OLUSTUR',
            'RANDEVU_DUZENLE',
            'RANDEVU_IPTAL',
            'TAKVIM_GORUNTULE',
            'ODA_DURUMU_GORUNTULE',
            'DANISMA_OTURUMU_YONET'
        )
        THEN 1
        ELSE 0
    END

FROM roller r
CROSS JOIN izinler i

WHERE r.rol_adi = 'DANISMA_OGRENCISI';