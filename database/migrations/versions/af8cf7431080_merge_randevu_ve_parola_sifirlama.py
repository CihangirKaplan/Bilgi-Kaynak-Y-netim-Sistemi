"""merge randevu ve parola sifirlama

Revision ID: af8cf7431080
Revises: 193b128bde5e, e4a7aeb1ca46
Create Date: 2026-11-10 10:59:04.212511

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af8cf7431080'
down_revision: Union[str, Sequence[str], None] = ('193b128bde5e', 'e4a7aeb1ca46')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
