"""merge faaliyet puanlari ve denetim kayitlari

Revision ID: dd1703ad70f4
Revises: 9c7e4a21b6d0, f3a9c2e47b18
Create Date: 2026-11-09 14:38:23.342603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd1703ad70f4'
down_revision: Union[str, Sequence[str], None] = ('9c7e4a21b6d0', 'f3a9c2e47b18')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
