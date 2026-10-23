"""kalibrasyon_baslangic_ve_bitis_tarihleri_eklendi

Revision ID: 56d233060538
Revises: f7b0f6ef02e9
Create Date: 2026-10-23 09:57:08.007242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56d233060538'
down_revision: Union[str, Sequence[str], None] = 'f7b0f6ef02e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # İleri sarma: Sütunları ekle
    op.add_column('cihaz_kalibrasyonlari', sa.Column('kalibrasyon_baslangic_tarihi', sa.Date(), nullable=True))
    op.add_column('cihaz_kalibrasyonlari', sa.Column('kalibrasyon_bitis_tarihi', sa.Date(), nullable=True))

def downgrade() -> None:
    # Geri sarma: Sütunları sil (hata olursa geri dönmek için)
    op.drop_column('cihaz_kalibrasyonlari', 'kalibrasyon_bitis_tarihi')
    op.drop_column('cihaz_kalibrasyonlari', 'kalibrasyon_baslangic_tarihi')