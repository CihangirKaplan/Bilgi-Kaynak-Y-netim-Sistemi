"""oda etkinlikleri ve psikolog danisan migration birlestirme

Revision ID: 33138e85f1ff
Revises: 12b99dc879fc, d1e6a3b9c847
Create Date: 2026-11-19 10:02:28.047240

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33138e85f1ff'
down_revision: Union[str, Sequence[str], None] = ('12b99dc879fc', 'd1e6a3b9c847')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
