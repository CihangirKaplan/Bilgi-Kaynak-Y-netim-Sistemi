"""danisma tek acik oturum

Revision ID: c01930448638
Revises: ee12c8c2b5fb
Create Date: 2026-10-21 11:05:48.583221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c01930448638'
down_revision: Union[str, Sequence[str], None] = 'ee12c8c2b5fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX uq_danisma_tek_acik_oturum
        ON danisma_masasi_oturumlari (ogrenci_id)
        WHERE bitis_zamani IS NULL;
    """)

def downgrade():
    op.execute("""
        DROP INDEX IF EXISTS uq_danisma_tek_acik_oturum;
    """)