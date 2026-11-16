"""gecici parola suresi: kullanicilar.gecici_parola_bitis

Revision ID: b6d2f8a4c913
Revises: e1a7c4b9d3f6
Create Date: 2026-11-16 12:00:00.000000

Yönetici ya da kurtarma aracı geçici parola verdiğinde (ilk_giris_mi = TRUE) parolanın geçerli olduğu son zaman yazılır; süre dolunca
kullanıcı giriş yapamaz ve yeni geçici parola ister. Süre bilgisi boş olan eski kayıtlar süresiz kalır (geriye uyumlu).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6d2f8a4c913"
down_revision: Union[str, Sequence[str], None] = "e1a7c4b9d3f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS gecici_parola_bitis TIMESTAMP")


def downgrade():
    op.execute("ALTER TABLE kullanicilar DROP COLUMN IF EXISTS gecici_parola_bitis")
