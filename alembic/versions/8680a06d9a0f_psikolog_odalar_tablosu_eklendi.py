"""psikolog_odalar_tablosu_eklendi

Revision ID: 8680a06d9a0f
Revises: fca7e826535a
Create Date: 2026-11-06 11:06:27.107068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8680a06d9a0f'
down_revision: Union[str, Sequence[str], None] = 'fca7e826535a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Tabloyu oluşturma işlemi
    op.create_table(
        'psikolog_odalar',
        sa.Column('kullanici_id', sa.Integer(), nullable=False),
        sa.Column('oda_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['kullanici_id'], ['kullanicilar.kullanici_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['oda_id'], ['odalar.oda_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('kullanici_id', 'oda_id')
    )

def downgrade():
    # Geri alma (rollback) işlemi
    op.drop_table('psikolog_odalar')