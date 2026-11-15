"""empty message

Revision ID: 193b128bde5e
Revises: c67347027ab0, f3a9c2e47b18
Create Date: 2026-11-09 12:09:40.470087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '193b128bde5e'
down_revision: Union[str, Sequence[str], None] = ('c67347027ab0', 'f3a9c2e47b18')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
