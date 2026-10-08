-- Randevu ve Oda Yönetimi Modülü Tabloları
-- 1. Danışan Kodları Tablosu 
CREATE TABLE danisan_kodlari (
    danisan_kod_id VARCHAR(50) PRIMARY KEY, 
    ucretli_mi BOOLEAN NOT NULL DEFAULT TRUE, -- Ücretli mi yoksa ücretsiz mi?
    istisna_turu VARCHAR(50) DEFAULT 'YOK',   -- 'KANSER_HASTASI', 'SEHIT_GAZI_YAKINI', 'YOK' vb.
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
    olusturulma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. Odalar Tablosu
CREATE TABLE odalar (
    oda_id SERIAL PRIMARY KEY,
    oda_adi VARCHAR(50) UNIQUE NOT NULL,
    kapasite INT DEFAULT 1, -- Fiziksel oda kapasitesi
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

-- 3. Randevular Tablosu (Türler ve anahtarlar eşitlendi)
CREATE TABLE randevular (
    randevu_id SERIAL PRIMARY KEY,
    danisan_kod_id VARCHAR(50) NOT NULL REFERENCES danisan_kodlari(danisan_kod_id),
    psikolog_id INT NOT NULL REFERENCES personel(personel_id),
    oda_id INT NOT NULL REFERENCES odalar(oda_id),
    baslangic_zamani TIMESTAMP NOT NULL,
    bitis_zamani TIMESTAMP NOT NULL,
    durum VARCHAR(30) DEFAULT 'PLANLANDI',
    olusturulma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. Eğitim, Seminer ve İdari Toplantılar için Oda Kullanımı
CREATE TABLE oda_etkinlikleri (
    etkinlik_id SERIAL PRIMARY KEY,
    oda_id INT NOT NULL REFERENCES odalar(oda_id),
    organize_eden_personel_id INT NOT NULL REFERENCES personel(personel_id), -- Eğitimi düzenleyen kişi
    etkinlik_adi VARCHAR(150) NOT NULL, -- Örn: "Cihaz Kullanım Eğitimi", "Haftalık Vaka Toplantısı"
    katilimci_sayisi INT, -- Odanın kapasitesini aşıp aşmadığını kontrol etmek için
    baslangic_zamani TIMESTAMP NOT NULL,
    bitis_zamani TIMESTAMP NOT NULL,
    iptal_edildi_mi BOOLEAN DEFAULT FALSE
);

-- Randevu saat çakışmalarını veritabanı seviyesinde engelle
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- Aynı psikoloğun çakışan iki aktif randevusu olamaz
ALTER TABLE randevular
ADD CONSTRAINT psikolog_randevu_cakisma
EXCLUDE USING gist (
    psikolog_id WITH =,
    tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&
)
WHERE (durum = 'PLANLANDI');

-- Aynı oda çakışan iki aktif randevuya atanamaz
ALTER TABLE randevular
ADD CONSTRAINT oda_randevu_cakisma
EXCLUDE USING gist (
    oda_id WITH =,
    tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&
)
WHERE (durum = 'PLANLANDI');
