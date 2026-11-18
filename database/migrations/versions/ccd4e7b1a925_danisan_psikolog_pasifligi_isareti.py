"""danisan_kodlari: psikolog pasifligi nedeniyle pasif isareti

Psikolog pasife alinirken kendi danisanlari da pasife alinir; psikolog yeniden aktif edilince yalnizca BU YUZDEN pasife
alinmis danisanlar geri acilir (daha once elle pasife alinmis danisanlar pasif kalir). Bunu ayirt etmek icin danisan_kodlari
tablosuna isaret sutunu eklenir. Mevcut kayitlar icin varsayilan false'tur; veriye dokunulmaz.

Geri alma (downgrade) sutunu siler.

Revision ID: ccd4e7b1a925
Revises: d6c3a9e1f407
Create Date: 2026-11-18 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ccd4e7b1a925"
down_revision: Union[str, Sequence[str], None] = "d6c3a9e1f407"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE danisan_kodlari ADD COLUMN IF NOT EXISTS psikolog_pasifligi_nedeniyle_pasif BOOLEAN NOT NULL DEFAULT FALSE")


def downgrade():
    op.execute("ALTER TABLE danisan_kodlari DROP COLUMN IF EXISTS psikolog_pasifligi_nedeniyle_pasif")
