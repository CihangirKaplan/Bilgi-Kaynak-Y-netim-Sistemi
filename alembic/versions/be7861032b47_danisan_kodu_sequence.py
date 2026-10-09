"""danisan kodu sequence

Revision ID: be7861032b47
Revises: d39bab18d6fe
Create Date: 2026-10-08 22:06:39.241213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be7861032b47'
down_revision: Union[str, Sequence[str], None] = 'd39bab18d6fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS danisan_kodu_seq
        START WITH 1
        INCREMENT BY 1;
    """)

    op.execute("""
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
    """)


def downgrade():
    # Mevcut danışan kodlarının sayacını koruyoruz.
    pass
