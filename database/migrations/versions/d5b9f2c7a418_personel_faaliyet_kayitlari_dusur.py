"""personel_faaliyet_kayitlari tablosu kaldirildi

Tablo hicbir sunucu/istemci kodunda kullanilmiyordu; personel_id icin yabanci anahtar yoktu ve sutun adlari
ogrenci_faaliyet_takip ile uyumsuzdu. Faaliyet kaydi ogrenci_faaliyet_takip uzerinden tutulur.

Guvenlik: tabloda satir varsa migration hata verip durur ve hicbir sey silmez. Veriyi once yedekleyin ya da tasiyin.
Geri alma (downgrade) tabloyu bos olarak ve eski yapisiyla yeniden olusturur; silinen veri geri gelmez.

Revision ID: d5b9f2c7a418
Revises: c8f2a5d1e704
Create Date: 2026-11-16 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5b9f2c7a418"
down_revision: Union[str, Sequence[str], None] = "c8f2a5d1e704"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.personel_faaliyet_kayitlari') IS NOT NULL THEN
                IF EXISTS (SELECT 1 FROM personel_faaliyet_kayitlari) THEN
                    RAISE EXCEPTION 'personel_faaliyet_kayitlari tablosunda veri var; veri kaybini onlemek icin tablo dusurulmedi. Once yedekleyin ya da tasiyin.';
                END IF;
            END IF;
        END $$;
        """
    )
    op.execute("DROP TABLE IF EXISTS personel_faaliyet_kayitlari")


def downgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS personel_faaliyet_kayitlari (
            kayit_id SERIAL PRIMARY KEY,
            personel_id INTEGER NOT NULL,
            faaliyet_id INTEGER REFERENCES faaliyetler(faaliyet_id),
            birim_id INTEGER REFERENCES faaliyet_birimleri(birim_id),
            miktar INTEGER NOT NULL,
            toplam_puan INTEGER NOT NULL,
            kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute('CREATE INDEX IF NOT EXISTS "ix_personel_faaliyet_kayitlari_birim_id" ON "personel_faaliyet_kayitlari" ("birim_id")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_personel_faaliyet_kayitlari_faaliyet_id" ON "personel_faaliyet_kayitlari" ("faaliyet_id")')
