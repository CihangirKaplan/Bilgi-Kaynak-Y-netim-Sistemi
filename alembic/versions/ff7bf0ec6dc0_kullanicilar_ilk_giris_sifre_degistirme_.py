"""kullanicilar ilk giris sifre degistirme alani

Revision ID: ff7bf0ec6dc0
Revises: 81f41620df1f
Create Date: 2026-10-15 11:48:38.740247

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff7bf0ec6dc0'
down_revision: Union[str, Sequence[str], None] = '81f41620df1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """İlk girişte şifre değiştirme alanını ekle."""
    op.add_column(
        "kullanicilar",
        sa.Column(
            "ilk_giris_mi",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )
    )

def downgrade() -> None:
    """İlk giriş alanını kaldır."""
    op.drop_column("kullanicilar", "ilk_giris_mi")