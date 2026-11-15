"""cihaz bakim baslangic ve bitis tarihleri

Revision ID: f7b0f6ef02e9
Revises: e442f48aba32
Create Date: 2026-10-22 22:54:09.657501

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7b0f6ef02e9'
down_revision: Union[str, Sequence[str], None] = 'e442f48aba32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cihaz bakimlarina baslangic ve bitis tarihlerini ekle."""

    op.add_column(
        "cihaz_bakimlari",
        sa.Column(
            "bakim_baslangic_tarihi",
            sa.Date(),
            nullable=True
        )
    )

    op.add_column(
        "cihaz_bakimlari",
        sa.Column(
            "bakim_bitis_tarihi",
            sa.Date(),
            nullable=True
        )
    )


def downgrade() -> None:
    """Eklenen bakim tarihi sutunlarini kaldir."""

    op.drop_column(
        "cihaz_bakimlari",
        "bakim_bitis_tarihi"
    )

    op.drop_column(
        "cihaz_bakimlari",
        "bakim_baslangic_tarihi"
    )
