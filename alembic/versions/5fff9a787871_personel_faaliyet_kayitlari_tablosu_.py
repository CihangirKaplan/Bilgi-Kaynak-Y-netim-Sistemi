"""personel_faaliyet_kayitlari_tablosu_eklendi

Revision ID: 5fff9a787871
Revises: ee12c8c2b5fb
Create Date: 2026-10-20 12:06:52.065775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5fff9a787871'
down_revision: Union[str, Sequence[str], None] = 'ee12c8c2b5fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Tabloyu oluşturma komutu (İleri sarma)
    op.create_table(
        'personel_faaliyet_kayitlari',
        sa.Column('kayit_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('personel_id', sa.Integer(), nullable=False),
        sa.Column('faaliyet_id', sa.Integer(), sa.ForeignKey('faaliyetler.faaliyet_id'), nullable=True),
        sa.Column('birim_id', sa.Integer(), sa.ForeignKey('faaliyet_birimleri.birim_id'), nullable=True),
        sa.Column('miktar', sa.Integer(), nullable=False),
        sa.Column('toplam_puan', sa.Integer(), nullable=False),
        sa.Column('kayit_tarihi', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'))
    )

def downgrade():
    # İşlemi geri alma komutu (Geri sarma)
    op.drop_table('personel_faaliyet_kayitlari')
