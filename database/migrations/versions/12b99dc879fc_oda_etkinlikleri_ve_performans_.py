"""oda etkinlikleri ve performans indeksleri birlestirme

Revision ID: 12b99dc879fc
Revises: d7a2c5e8f193, e2d1900fe26c
Create Date: 2026-11-19 09:54:31.389453

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12b99dc879fc'
down_revision: Union[str, Sequence[str], None] = ('d7a2c5e8f193', 'e2d1900fe26c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
