"""guncel_veritabani_degisimleri

Revision ID: 506031f640f1
Revises: be7861032b47
Create Date: 2026-10-12 15:38:18.105017

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '506031f640f1'
down_revision: Union[str, Sequence[str], None] = 'be7861032b47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade() -> None:
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama)
        VALUES
            ('ODA_EKLE', 'Sisteme yeni oda ekleme'),
            ('ODA_DUZENLE', 'Mevcut oda bilgilerini düzenleme')
        ON CONFLICT (izin_adi) DO NOTHING;
    """)

    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id, 1
        FROM roller r
        CROSS JOIN izinler i
        WHERE r.rol_adi IN ('ADMIN', 'MEMUR', 'MUDUR')
          AND i.izin_adi IN ('ODA_EKLE', 'ODA_DUZENLE')
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET izin_var = 1;
    """)


def downgrade() -> None:
    # İzinleri silmek mevcut yetkilendirme kayıtlarını
    # etkileyebileceğinden otomatik geri alma yapılmıyor.
    raise NotImplementedError(
        "Oda izinlerinin otomatik geri alınması desteklenmiyor."
    )
    
    