"""bakım ve kalibrasyon kayıtlarına uyarı süresi eklendi

Revision ID: c4e8a1b7d205
Revises: 1d62d049bc61
Create Date: 2026-11-04 12:10:00.000000

Bakım/kalibrasyon kaydındaki "sonraki tarih" için kaç gün kala dashboard'da ve bildirimde
uyarı verileceği kayıt başına tutulur. Mevcut kayıtlar 30 gün alır (eskiden dashboard listesi
sabit 60, zil sabit 15 gündü; artık ikisi de aynı kural olan kayıttaki uyarı süresine uyar).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1b7d205'
down_revision: Union[str, Sequence[str], None] = '1d62d049bc61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLOLAR = ("cihaz_bakimlari", "cihaz_kalibrasyonlari")


def upgrade() -> None:
    for tablo in TABLOLAR:
        op.add_column(
            tablo,
            sa.Column("uyari_suresi_gun", sa.Integer(), server_default="30", nullable=False),
        )
        op.create_check_constraint(
            f"ck_{tablo}_uyari_suresi_gun", tablo, "uyari_suresi_gun BETWEEN 0 AND 365"
        )


def downgrade() -> None:
    for tablo in TABLOLAR:
        op.drop_constraint(f"ck_{tablo}_uyari_suresi_gun", tablo, type_="check")
        op.drop_column(tablo, "uyari_suresi_gun")
