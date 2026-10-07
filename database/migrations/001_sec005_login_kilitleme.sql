-- SEC-005
-- Başarısız giriş denemelerinin takip edilmesi ve
-- kullanıcı hesabının geçici olarak kilitlenebilmesi için gerekli alanlar.

ALTER TABLE kullanicilar
ADD COLUMN basarisiz_giris_sayisi INT NOT NULL DEFAULT 0,
ADD COLUMN kilit_bitis_zamani TIMESTAMP NULL;
