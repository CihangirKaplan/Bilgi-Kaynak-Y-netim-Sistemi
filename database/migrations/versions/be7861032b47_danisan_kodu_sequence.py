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
    # Veritabanı güncellenirken sayacı oluştur
    op.execute("CREATE SEQUENCE danisan_kodu_seq START 1;")

def downgrade():
    # Sürüm geri alınırken sayacı sil
    op.execute("DROP SEQUENCE danisan_kodu_seq;")
