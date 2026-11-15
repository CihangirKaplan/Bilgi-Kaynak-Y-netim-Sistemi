"""bakim_tablosuna_sonraki_tarih_eklendi

Revision ID: ee12c8c2b5fb
Revises: ff7bf0ec6dc0
Create Date: 2026-10-18 01:21:50.049666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee12c8c2b5fb'
down_revision: Union[str, Sequence[str], None] = 'ff7bf0ec6dc0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Veritabanı güncellenirken (upgrade) bu kod çalışacak ve sütunu ekleyecek
    op.execute("ALTER TABLE cihaz_bakimlari ADD COLUMN sonraki_bakim_tarihi DATE;")

def downgrade() -> None:
    # Biri güncellemeyi geri almak isterse (downgrade) bu kod çalışacak ve sütunu silecek
    op.execute("ALTER TABLE cihaz_bakimlari DROP COLUMN sonraki_bakim_tarihi;")