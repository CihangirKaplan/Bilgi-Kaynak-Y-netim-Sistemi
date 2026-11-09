"""admin_randevu_olustur_yetkisi_eklendi

Revision ID: fca7e826535a
Revises: 0f2eccb5df5d
Create Date: 2026-11-04 10:30:03.562193

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = 'fca7e826535a'
down_revision: Union[str, Sequence[str], None] = '0f2eccb5df5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Sistem Admin rolünün ID'sini bul
    # RANDEVU_OLUSTUR izninin ID'sini bul
    # Eğer bu eşleşme rol_izinleri tablosunda yoksa ekle
    op.execute(text("""
        INSERT INTO rol_izinleri (rol_id, izin_id)
        SELECT r.rol_id, i.izin_id
        FROM roller r, izinler i
        WHERE r.rol_adi = 'Admin' AND i.izin_adi = 'RANDEVU_OLUSTUR'
        ON CONFLICT DO NOTHING;
    """))

def downgrade():
    # Eğer sürüm geri alınırsa, bu yetkiyi kaldır
    op.execute(text("""
        DELETE FROM rol_izinleri
        WHERE rol_id = (SELECT rol_id FROM roller WHERE rol_adi = 'Admin')
        AND izin_id = (SELECT izin_id FROM izinler WHERE izin_adi = 'RANDEVU_OLUSTUR');
    """))
