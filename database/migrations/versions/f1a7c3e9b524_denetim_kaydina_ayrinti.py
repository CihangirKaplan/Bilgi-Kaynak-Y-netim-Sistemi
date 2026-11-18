"""denetim_kayitlari.ayrinti: silinen verinin içeriği ve önceki/yeni değerler

Revision ID: f1a7c3e9b524
Revises: e8b4d2f6a193
Create Date: 2026-11-18 16:00:00.000000

Denetim kaydı şimdiye kadar yalnızca "kim, hangi tabloda hangi kaydı, ne zaman" bilgisini tutuyordu. Kalıcı silmelerde silinen
satırın içeriği hiçbir yerde kalmıyordu (yalnızca yedekte). Bu migrasyon JSONB 'ayrinti' sütunu ekler: silmelerde silinen satırın
içeriği (kişisel veri içeren tablolarda yalnızca kimliksiz alanlar), oda atamalarında önceki/yeni odalar yazılır.
Tablo tetikleyiciyle değiştirilemez olduğu için kayıt sonradan değiştirilemez. Mevcut kayıtlar için sütun boş (NULL) kalır.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f1a7c3e9b524"
down_revision: Union[str, Sequence[str], None] = "e8b4d2f6a193"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE denetim_kayitlari ADD COLUMN IF NOT EXISTS ayrinti JSONB")


def downgrade():
    op.execute("ALTER TABLE denetim_kayitlari DROP COLUMN IF EXISTS ayrinti")
