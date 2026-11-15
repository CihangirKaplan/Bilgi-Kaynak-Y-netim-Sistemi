"""danisan_kodlarina_olusturan_psikolog_eklendi

Revision ID: c67347027ab0
Revises: 8680a06d9a0f
Create Date: 2026-11-06 11:12:30.039491

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c67347027ab0'
down_revision: Union[str, Sequence[str], None] = '8680a06d9a0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # danisan_kodlari tablosuna olusturan_psikolog_id sütununu ekliyoruz
    op.add_column('danisan_kodlari', sa.Column('olusturan_psikolog_id', sa.Integer(), nullable=True))
    # Personel tablosuna yabancı anahtar (foreign key) bağı kuruyoruz
    op.create_foreign_key(
        'fk_danisankodlari_personel', 
        'danisan_kodlari', 'personel', 
        ['olusturan_psikolog_id'], ['personel_id'], 
        ondelete='SET NULL'
    )

def downgrade():
    # Geri alma (rollback) durumunda yapılacaklar
    op.drop_constraint('fk_danisankodlari_personel', 'danisan_kodlari', type_='foreign key')
    op.drop_column('danisan_kodlari', 'olusturan_psikolog_id')
