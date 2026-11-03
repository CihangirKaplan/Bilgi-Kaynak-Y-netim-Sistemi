"""roller tablosuna gorunen_ad ekle

Revision ID: 6c3b4cc159c2
Revises: b7e41c9d2a60
Create Date: 2026-10-26 11:45:02.982551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c3b4cc159c2'
down_revision: Union[str, Sequence[str], None] = 'b7e41c9d2a60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roller", sa.Column("gorunen_ad", sa.String(100), nullable=True))
    op.execute("""
        UPDATE roller SET gorunen_ad = CASE rol_adi
            WHEN 'PSIKOLOG' THEN 'Psikolog'
            WHEN 'MEMUR' THEN 'Memur'
            WHEN 'MUDUR' THEN 'Müdür'
            WHEN 'DANISMA_OGRENCISI' THEN 'Danışma Öğrencisi'
            WHEN 'PROJE_ASISTANI' THEN 'Proje Asistanı'
            WHEN 'ADMIN' THEN 'Sistem Admin'
        END
    """)


def downgrade() -> None:
    op.drop_column("roller", "gorunen_ad")
