"""roller_tablosuna_aktif_mi_eklendi

Revision ID: 1d62d049bc61
Revises: 74fe75570ae7
Create Date: 2026-10-30 15:51:25.563927

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d62d049bc61'
down_revision: Union[str, Sequence[str], None] = '74fe75570ae7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 'roller' tablosuna 'aktif_mi' sütununu ekler, varsayılan olarak True (true) yapar.
    op.add_column('roller', sa.Column('aktif_mi', sa.Boolean(), server_default='true', nullable=True))

def downgrade():
    # İşlemi geri almak gerekirse bu sütunu siler.
    op.drop_column('roller', 'aktif_mi')
