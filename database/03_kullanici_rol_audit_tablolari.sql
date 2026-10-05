
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
-- 6. OGRENCI TURU
-- ============================================================

CREATE TYPE ogrenci_turu AS ENUM ('GONULLU', 'DANISMA_MASASI');

-- ============================================================
-- 7. OGRENCILER
-- Gönüllü ve danışma masası öğrencilerinin ortak bilgileri.
-- ============================================================

CREATE TABLE ogrenciler (
    ogrenci_id SERIAL PRIMARY KEY,
    kullanici_id INT UNIQUE REFERENCES kullanicilar(kullanici_id),
    ad_soyad VARCHAR(100) NOT NULL,
    ogrenci_numarasi VARCHAR(50) UNIQUE NOT NULL,
    telefon VARCHAR(20),
    tur ogrenci_turu NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    olusturulma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 8. DANISMA MASASI OTURUMLARI
-- Başlat/Bitir akışıyla gerçek görev süresini tutar.
-- ============================================================

CREATE TABLE danisma_masasi_oturumlari (
    oturum_id SERIAL PRIMARY KEY,
    ogrenci_id INT NOT NULL REFERENCES ogrenciler(ogrenci_id),
    baslangic_zamani TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bitis_zamani TIMESTAMP,
    onaylandi_mi BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (bitis_zamani IS NULL OR bitis_zamani > baslangic_zamani)
);

-- ============================================================
-- 9. FAALIYETLER
-- Güncel faaliyet puanlarını tutar.
-- ============================================================

CREATE TABLE faaliyetler (
    faaliyet_id SERIAL PRIMARY KEY,
    faaliyet_adi VARCHAR(100) UNIQUE NOT NULL,
    puan INT NOT NULL CHECK (puan >= 0),
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

-- ============================================================
-- 10. OGRENCI FAALIYET TAKIP
-- Her iki öğrenci türünün faaliyetlerini tutar.
-- Toplam puan = adet * faaliyetler.puan (güncel puan).
-- ============================================================

CREATE TABLE ogrenci_faaliyet_takip (
    takip_id SERIAL PRIMARY KEY,
    ogrenci_id INT NOT NULL REFERENCES ogrenciler(ogrenci_id),
    faaliyet_id INT NOT NULL REFERENCES faaliyetler(faaliyet_id),
    adet INT NOT NULL CHECK (adet > 0),
    faaliyet_tarihi DATE NOT NULL DEFAULT CURRENT_DATE,
    aciklama VARCHAR(255),
    onaylandi_mi BOOLEAN NOT NULL DEFAULT FALSE,
    olusturulma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================

-- 11. DENETIM OLAY TURU

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

-- 12. DENETIM KAYITLARI

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

-- 13. BASLANGIC VERILERI
-- ============================================================


-- ============================================================
-- 13.1 ROLLER
-- ============================================================

INSERT INTO roller (rol_adi) VALUES
    ('PSIKOLOG'),
    ('MEMUR'),
    ('MUDUR'),
    ('DANISMA_OGRENCISI'),
    ('PROJE_ASISTANI'),
    ('ADMIN');


-- ============================================================
-- 13.2 FAALIYET BASLANGIC VERILERI
-- Güncel puanlar faaliyetler tablosunda tutulur.
-- ============================================================

INSERT INTO faaliyetler (faaliyet_adi, puan) VALUES
    ('Yüz Yüze Anket', 5),
    ('Online Anket', 1),
    ('İç Tanıtım Görüşmesi', 3),
    ('Dış Tanıtım Görüşmesi', 10),
    ('Sponsorluk', 20),
    ('Sempozyum', 10),
    ('PsiLab Etkinliği', 3);


-- ============================================================
-- 13.3 IZINLER
-- İzin adları, son paylaşılan izin matrisindeki işlemleri temsil eder.
-- ============================================================

INSERT INTO izinler (izin_adi, aciklama) VALUES
    ('RANDEVU_OLUSTUR', 'Randevu oluşturma'),
    ('RANDEVU_DUZENLE', 'Randevu düzenleme'),
    ('RANDEVU_IPTAL', 'Randevu iptal etme'),
    ('TAKVIM_GORUNTULE', 'Randevu takvimini görüntüleme'),
    ('ODA_DURUMU_GORUNTULE', 'Oda kullanım durumunu görüntüleme'),
    ('CIHAZ_UYGUNLUK_GORUNTULE', 'Cihaz uygunluğunu görüntüleme'),
    ('CIHAZ_ENVANTER_YONET', 'Cihaz envanterini yönetme'),
    ('CIHAZ_REZERVASYON', 'Cihaz rezervasyonu yapma'),
    ('BAKIM_KAYITLARI_YONET', 'Bakım kayıtlarını yönetme'),
    ('KALIBRASYON_KAYITLARI_YONET', 'Kalibrasyon kayıtlarını yönetme'),
    ('ARIZA_KAYITLARI_YONET', 'Arıza kayıtlarını yönetme'),
    ('KULLANICI_OLUSTUR', 'Kullanıcı oluşturma'),
    ('PERSONEL_TANIMLA', 'Personel tanımlama'),
    ('KULLANICI_PASIFLESTIR', 'Kullanıcı pasifleştirme'),
    ('ROL_ATAMA_DEGISTIRME', 'Rol atama veya değiştirme'),
    ('AUDIT_KAYITLARI_INCELE', 'Audit kayıtlarını inceleme'),
    ('DANISMA_OTURUMU_YONET', 'Danışma masası oturumunu yönetme'),
    ('CIHAZ_EKLE', 'Sisteme yeni cihaz ekleme'),
    ('FAALIYET_KAYITLARI_DUZENLE', 'Faaliyet kayıtlarını düzenleme'),
    ('CIHAZ_TAKIP_KONTROL_LISTESI', 'Cihaz takip kontrol listesini yönetme'),
    ('IZIN_TANIMLA', 'Sisteme yeni izin tanımlama'),
    ('IZIN_DUZENLE', 'Mevcut izin tanımını düzenleme'),
    ('ROL_IZIN_YONET', 'Rollerin izinlerini yönetme'),
    ('ROL_OLUSTUR', 'Sisteme yeni rol oluşturma'),
    ('ROL_DUZENLE', 'Mevcut rolü düzenleme');


-- ============================================================
-- 13.4 PSIKOLOG IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT r.rol_id, i.izin_id,
    CASE WHEN i.izin_adi IN (
        'RANDEVU_OLUSTUR',
        'RANDEVU_DUZENLE',
        'RANDEVU_IPTAL',
        'TAKVIM_GORUNTULE',
        'ODA_DURUMU_GORUNTULE',
        'CIHAZ_UYGUNLUK_GORUNTULE'
    ) THEN 1 ELSE 0 END
FROM roller r
CROSS JOIN izinler i
WHERE r.rol_adi = 'PSIKOLOG';


-- ============================================================
-- 13.5 MEMUR IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT r.rol_id, i.izin_id,
    CASE WHEN i.izin_adi IN (
        'TAKVIM_GORUNTULE',
        'ODA_DURUMU_GORUNTULE',
        'CIHAZ_UYGUNLUK_GORUNTULE',
        'CIHAZ_ENVANTER_YONET',
        'CIHAZ_REZERVASYON',
        'BAKIM_KAYITLARI_YONET',
        'KALIBRASYON_KAYITLARI_YONET',
        'ARIZA_KAYITLARI_YONET',
        'DANISMA_OTURUMU_YONET',
        'CIHAZ_EKLE',
        'FAALIYET_KAYITLARI_DUZENLE',
        'CIHAZ_TAKIP_KONTROL_LISTESI'
    ) THEN 1 ELSE 0 END
FROM roller r
CROSS JOIN izinler i
WHERE r.rol_adi = 'MEMUR';


-- ============================================================
-- 13.6 MUDUR IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT r.rol_id, i.izin_id,
    CASE WHEN i.izin_adi IN (
        'TAKVIM_GORUNTULE',
        'ODA_DURUMU_GORUNTULE',
        'CIHAZ_UYGUNLUK_GORUNTULE',
        'CIHAZ_ENVANTER_YONET',
        'BAKIM_KAYITLARI_YONET',
        'KALIBRASYON_KAYITLARI_YONET',
        'ARIZA_KAYITLARI_YONET',
        'KULLANICI_OLUSTUR',
        'PERSONEL_TANIMLA',
        'KULLANICI_PASIFLESTIR',
        'ROL_ATAMA_DEGISTIRME',
        'AUDIT_KAYITLARI_INCELE',
        'DANISMA_OTURUMU_YONET',
        'CIHAZ_EKLE',
        'FAALIYET_KAYITLARI_DUZENLE',
        'CIHAZ_TAKIP_KONTROL_LISTESI'
    ) THEN 1 ELSE 0 END
FROM roller r
CROSS JOIN izinler i
WHERE r.rol_adi = 'MUDUR';


-- ============================================================
-- 13.7 DANISMA OGRENCISI IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT r.rol_id, i.izin_id,
    CASE WHEN i.izin_adi IN (
        'RANDEVU_OLUSTUR',
        'RANDEVU_DUZENLE',
        'RANDEVU_IPTAL',
        'TAKVIM_GORUNTULE',
        'ODA_DURUMU_GORUNTULE',
        'DANISMA_OTURUMU_YONET'
    ) THEN 1 ELSE 0 END
FROM roller r
CROSS JOIN izinler i
WHERE r.rol_adi = 'DANISMA_OGRENCISI';


-- ============================================================
-- 13.8 PROJE ASISTANI IZINLERI
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT r.rol_id, i.izin_id,
    CASE WHEN i.izin_adi IN (
        'TAKVIM_GORUNTULE',
        'ODA_DURUMU_GORUNTULE',
        'CIHAZ_UYGUNLUK_GORUNTULE',
        'CIHAZ_REZERVASYON',
        'FAALIYET_KAYITLARI_DUZENLE'
    ) THEN 1 ELSE 0 END
FROM roller r
CROSS JOIN izinler i
WHERE r.rol_adi = 'PROJE_ASISTANI';

-- ============================================================
-- 13.9 ADMIN IZINLERI
-- ADMIN süper kullanıcıdır ve sistemde tanımlı tüm izinlere sahiptir.
-- Yeni izin oluşturma işleminde FastAPI, yeni izni ADMIN rolüne de
-- otomatik olarak izin_var = 1 ile bağlamalıdır.
-- ============================================================

INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
SELECT
    r.rol_id,
    i.izin_id,
    1
FROM roller r
CROSS JOIN izinler i
WHERE r.rol_adi = 'ADMIN';


