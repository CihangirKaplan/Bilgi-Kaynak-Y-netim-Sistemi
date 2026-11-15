"""danisan_kodu_seq_eklendi

Revision ID: 0f2eccb5df5d
Revises: 1d62d049bc61
Create Date: 2026-11-04 10:22:18.514484

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f2eccb5df5d'
down_revision: Union[str, Sequence[str], None] = '1d62d049bc61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
