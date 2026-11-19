"""oda etkinlikleri ve develop migration son birlestirme

Revision ID: 61d0c93faf24
Revises: 33138e85f1ff, a4c9e2d7b315
Create Date: 2026-11-19 10:18:56.235745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '61d0c93faf24'
down_revision: Union[str, Sequence[str], None] = ('33138e85f1ff', 'a4c9e2d7b315')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
