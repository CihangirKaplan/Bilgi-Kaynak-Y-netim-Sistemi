"""ariza kaydina cozum notu: ne yapilarak cozuldugu kaydedilir

cihaz_arizalari.cozum_notu: arizayi cozen kisinin yazdigi kisa aciklama (en cok 500 karakter). Eski kayitlarda bos kalir.
Ariza yeniden acilirsa sunucu notu da temizler (cozum_tarihi ile ayni davranis).

Revision ID: a7c3e91d4b52
Revises: f4b7c2e9a186
Create Date: 2026-11-22 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a7c3e91d4b52"
down_revision: Union[str, Sequence[str], None] = "f4b7c2e9a186"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE cihaz_arizalari ADD COLUMN IF NOT EXISTS cozum_notu varchar(500);")


def downgrade():
    op.execute("ALTER TABLE cihaz_arizalari DROP COLUMN IF EXISTS cozum_notu;")
