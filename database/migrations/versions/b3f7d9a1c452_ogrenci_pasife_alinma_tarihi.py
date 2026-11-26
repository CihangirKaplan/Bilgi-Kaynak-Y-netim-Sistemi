"""Öğrenci saklama süresi: pasife alındıktan sonra 2 yıl (önceden kayıt tarihinden 10 yıl).

`ogrenciler.pasife_alinma_tarihi`, öğrencinin en son pasife alındığı anı tutar; öğrenci yeniden aktif edilince boşalır. Değer bir
tetikleyici ile korunur: `aktif_mi` hangi kod yolundan değişirse değişsin (Öğrenciler sayfası, danışma öğrencisi hesabı, toplu işlem)
tarih tutarlı kalır, her güncelleme yerine ayrı kod yazmak gerekmez.

Bu göçten önce zaten pasif olan öğrencilerin ne zaman pasife alındığı bilinmez; süreleri bu göçün çalıştığı günden başlatılır
(kimse beklenenden erken silinmeye aday olmaz).

Revision ID: b3f7d9a1c452
Revises: d4a8b6c2e913
"""

from alembic import op

revision = "b3f7d9a1c452"
down_revision = "d4a8b6c2e913"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE ogrenciler ADD COLUMN IF NOT EXISTS pasife_alinma_tarihi TIMESTAMP")

    op.execute("""
        CREATE OR REPLACE FUNCTION ogrenci_pasife_alinma_tarihi_yaz() RETURNS trigger AS $$
        BEGIN
            IF NEW.aktif_mi THEN
                NEW.pasife_alinma_tarihi := NULL;
            ELSIF TG_OP = 'INSERT' OR OLD.aktif_mi THEN
                NEW.pasife_alinma_tarihi := CURRENT_TIMESTAMP;
            ELSE
                NEW.pasife_alinma_tarihi := COALESCE(NEW.pasife_alinma_tarihi, OLD.pasife_alinma_tarihi, CURRENT_TIMESTAMP);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("DROP TRIGGER IF EXISTS tr_ogrenci_pasife_alinma_tarihi ON ogrenciler")
    op.execute("""
        CREATE TRIGGER tr_ogrenci_pasife_alinma_tarihi
        BEFORE INSERT OR UPDATE OF aktif_mi ON ogrenciler
        FOR EACH ROW EXECUTE FUNCTION ogrenci_pasife_alinma_tarihi_yaz()
    """)

    # Mevcut pasif öğrenciler: süre bu günden başlar.
    op.execute("UPDATE ogrenciler SET pasife_alinma_tarihi = CURRENT_TIMESTAMP WHERE NOT aktif_mi AND pasife_alinma_tarihi IS NULL")

    op.execute("""
        UPDATE izinler
        SET aciklama = 'Öğrenci kaydını kalıcı silme (pasife alındıktan 2 yıl sonra, saklama süresi sonunda)'
        WHERE izin_adi = 'OGRENCI_KAYDI_SIL'
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS tr_ogrenci_pasife_alinma_tarihi ON ogrenciler")
    op.execute("DROP FUNCTION IF EXISTS ogrenci_pasife_alinma_tarihi_yaz()")
    op.execute("ALTER TABLE ogrenciler DROP COLUMN IF EXISTS pasife_alinma_tarihi")
    op.execute("""
        UPDATE izinler
        SET aciklama = 'Öğrenci kaydını kalıcı silme (10 yıllık saklama süresi sonunda)'
        WHERE izin_adi = 'OGRENCI_KAYDI_SIL'
    """)
