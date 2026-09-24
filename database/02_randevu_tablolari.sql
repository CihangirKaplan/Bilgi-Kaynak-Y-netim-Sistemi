-- Randevu ve Oda Yönetimi Modülü Tabloları

CREATE TABLE danisan_kodlari (
    danisan_id SERIAL PRIMARY KEY,
    danisan_kod_id VARCHAR(50) UNIQUE NOT NULL,
    kapasite INT DEFAULT 1,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE odalar (
    oda_id SERIAL PRIMARY KEY,
    oda_adi VARCHAR(50) UNIQUE NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE randevular (
    randevu_id SERIAL PRIMARY KEY,
    danisan_kod_id INT NOT NULL REFERENCES danisan_kodlari(danisan_kod_id),
    psikolog_id INT NOT NULL REFERENCES personel(personel_id),
    oda_id INT NOT NULL REFERENCES odalar(oda_id),
    baslangic_zamani TIMESTAMP NOT NULL,
    bitis_zamani TIMESTAMP NOT NULL,
    durum VARCHAR(30) DEFAULT 'PLANLANDI',
    olusturulma_tarihi TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Eğitim, Seminer ve İdari Toplantılar için Oda Kullanımı
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
