"""parola audit ve yabanci anahtar indeks migration birlestirme

Revision ID: 4e17fe8847d8
Revises: 9368bca11c96, a7d3e9c1b254
Create Date: 2026-11-13 16:31:42.449509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e17fe8847d8'
down_revision: Union[str, Sequence[str], None] = ('9368bca11c96', 'a7d3e9c1b254')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
