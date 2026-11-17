"""yonetim raporlari ve cihaz migration birlestirme

Revision ID: e0f32bef6d16
Revises: d7e9a2b4c601, f2b6d4a8c1e3
Create Date: 2026-11-17 22:14:13.078663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0f32bef6d16'
down_revision: Union[str, Sequence[str], None] = ('d7e9a2b4c601', 'f2b6d4a8c1e3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
