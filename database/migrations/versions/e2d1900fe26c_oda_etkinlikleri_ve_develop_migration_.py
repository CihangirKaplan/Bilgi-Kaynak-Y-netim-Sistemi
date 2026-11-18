"""oda etkinlikleri ve develop migration zinciri birlestirme

Revision ID: e2d1900fe26c
Revises: c2e5a9d4b681, d7e5a1b9c302
Create Date: 2026-11-18 20:14:45.719882

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2d1900fe26c'
down_revision: Union[str, Sequence[str], None] = ('c2e5a9d4b681', 'd7e5a1b9c302')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
