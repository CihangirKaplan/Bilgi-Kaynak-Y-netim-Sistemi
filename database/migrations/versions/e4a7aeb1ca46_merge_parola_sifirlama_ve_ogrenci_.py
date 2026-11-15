"""merge parola sifirlama ve ogrenci yonetimi

Revision ID: e4a7aeb1ca46
Revises: dd1703ad70f4, a7d3e91c5f42
Create Date: 2026-11-09 15:06:15.851609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a7aeb1ca46'
down_revision: Union[str, Sequence[str], None] = ('dd1703ad70f4', 'a7d3e91c5f42')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
