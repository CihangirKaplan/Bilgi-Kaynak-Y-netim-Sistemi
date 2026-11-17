"""cihaz_rezervasyonlari: aynı oda aynı saatte iki rezervasyona verilemez

Revision ID: e7c4b1d9a603
Revises: d9a3f6b2c815
Create Date: 2026-11-17 12:00:00.000000

Şimdiye kadar yalnızca aynı CİHAZIN çakışması engelleniyordu (cihaz_rezervasyon_cakisma); aynı odada aynı saatte iki farklı cihaz
rezerve edilebiliyordu. Bu kısıt, iptal edilmemiş ve odası seçilmiş rezervasyonlar için aynı odanın zaman aralığının çakışmasını
veritabanı düzeyinde de engeller (eşzamanlı isteklerde de geçerlidir). Odası boş rezervasyonlar bu kurala girmez.

Mevcut veride zaten çakışan oda rezervasyonları varsa kısıt eklenemez; bu durumda hiçbir değişiklik yapılmadan açık bir hatayla durulur
(çakışan rezervasyonlar listelenir, biri uygulamadan iptal edilip komut yeniden çalıştırılır).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c4b1d9a603"
down_revision: Union[str, Sequence[str], None] = "d9a3f6b2c815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        DO $$
        DECLARE cakisan TEXT;
        BEGIN
            SELECT string_agg(a.rezervasyon_id || '-' || b.rezervasyon_id, ', ') INTO cakisan
            FROM cihaz_rezervasyonlari a
            JOIN cihaz_rezervasyonlari b
              ON a.rezervasyon_id < b.rezervasyon_id
             AND a.kullanilacak_oda_id = b.kullanilacak_oda_id
             AND a.iptal_edildi_mi = FALSE AND b.iptal_edildi_mi = FALSE
             AND a.baslangic_zamani < b.bitis_zamani AND b.baslangic_zamani < a.bitis_zamani;
            IF cakisan IS NOT NULL THEN
                RAISE EXCEPTION 'Aynı odada aynı saatte çakışan cihaz rezervasyonları var (rezervasyon_id çiftleri: %). Birini iptal edip migrasyonu yeniden çalıştırın.', cakisan;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE cihaz_rezervasyonlari
        ADD CONSTRAINT cihaz_rezervasyon_oda_cakisma
        EXCLUDE USING gist (
            kullanilacak_oda_id WITH =,
            tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&
        )
        WHERE (iptal_edildi_mi = FALSE AND kullanilacak_oda_id IS NOT NULL)
        """
    )


def downgrade():
    op.execute("ALTER TABLE cihaz_rezervasyonlari DROP CONSTRAINT IF EXISTS cihaz_rezervasyon_oda_cakisma")
