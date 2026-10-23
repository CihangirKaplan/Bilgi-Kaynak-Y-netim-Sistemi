"""iki migration kolunu birlestir

Revision ID: 6b426e93cd9d
Revises: 7cd575b80a8d, c01930448638
Create Date: 2026-10-22 11:42:31.003127

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b426e93cd9d'
down_revision: Union[str, Sequence[str], None] = ('7cd575b80a8d', 'c01930448638')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
