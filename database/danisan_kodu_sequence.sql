-- Danışan kodları için benzersiz sıra numarası.
CREATE SEQUENCE IF NOT EXISTS danisan_kodu_seq
START WITH 1
INCREMENT BY 1;

-- Mevcut kayıtları dikkate alarak sayacı güvenli şekilde ayarla.
-- Bu dosya danisan_kodlari tablosu oluşturulduktan sonra çalıştırılır.
DO $$
DECLARE
    en_buyuk_kayit BIGINT;
    mevcut_sira BIGINT;
    daha_once_kullanildi BOOLEAN;
BEGIN
    SELECT COALESCE(
        MAX(SUBSTRING(danisan_kod_id FROM 10)::BIGINT),
        0
    )
    INTO en_buyuk_kayit
    FROM danisan_kodlari
    WHERE danisan_kod_id ~ '^DAN-[0-9]{4}-[0-9]+$';

    SELECT last_value, is_called
    INTO mevcut_sira, daha_once_kullanildi
    FROM danisan_kodu_seq;

    IF en_buyuk_kayit > 0 OR daha_once_kullanildi THEN
        PERFORM setval(
            'danisan_kodu_seq',
            GREATEST(
                en_buyuk_kayit,
                CASE
                    WHEN daha_once_kullanildi THEN mevcut_sira
                    ELSE 0
                END,
                1
            ),
            TRUE
        );
    END IF;
END $$;
