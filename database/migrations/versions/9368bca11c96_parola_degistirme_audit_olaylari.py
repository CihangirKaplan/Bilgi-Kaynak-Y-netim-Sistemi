"""parola degistirme audit olaylari

Revision ID: 9368bca11c96
Revises: b5e2c8d9a1f3
Create Date: 2026-11-13 16:06:31.767810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9368bca11c96'
down_revision: Union[str, Sequence[str], None] = 'b5e2c8d9a1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        ALTER TYPE denetim_olay_turu
        ADD VALUE IF NOT EXISTS 'PASSWORD_CHANGE';
    """)

    op.execute("""
        ALTER TYPE denetim_olay_turu
        ADD VALUE IF NOT EXISTS 'PASSWORD_CHANGE_FAILED';
    """)


def downgrade():
    # PostgreSQL ENUM değerlerini kaldırmak mevcut
    # audit kayıtlarını riske atabileceğinden korunur.
    pass
