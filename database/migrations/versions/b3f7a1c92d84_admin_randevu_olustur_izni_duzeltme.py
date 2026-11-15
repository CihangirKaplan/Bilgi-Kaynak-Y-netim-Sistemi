"""Admin rolüne RANDEVU_OLUSTUR iznini gerçekten ver

fca7e826535a migrasyonu iki nedenle hiçbir satır eklemiyordu: rol adını 'Admin' diye
arıyordu (kayıtlı ad 'ADMIN') ve izin_var sütununu yazmıyordu (varsayılan 0).

Revision ID: b3f7a1c92d84
Revises: af8cf7431080
Create Date: 2026-11-10

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b3f7a1c92d84"
down_revision: Union[str, Sequence[str], None] = "af8cf7431080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id, 1
        FROM roller r
        CROSS JOIN izinler i
        WHERE r.rol_adi = 'ADMIN' AND i.izin_adi = 'RANDEVU_OLUSTUR'
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET izin_var = 1;
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE rol_izinleri
        SET izin_var = 0
        WHERE rol_id = (SELECT rol_id FROM roller WHERE rol_adi = 'ADMIN')
          AND izin_id = (SELECT izin_id FROM izinler WHERE izin_adi = 'RANDEVU_OLUSTUR');
    """)
