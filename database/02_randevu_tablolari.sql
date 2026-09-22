-- Randevu ve Oda Yönetimi Modülü Tabloları

CREATE TABLE danisan_kodlari (
    danisan_kod_id SERIAL PRIMARY KEY,
    kod VARCHAR(50) UNIQUE NOT NULL,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
);

CREATE TABLE odalar (
    oda_id SERIAL PRIMARY KEY,
    oda_numarasi VARCHAR(50) UNIQUE NOT NULL,
    kapasite INT DEFAULT 1,
    aktif_mi BOOLEAN NOT NULL DEFAULT TRUE,
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
