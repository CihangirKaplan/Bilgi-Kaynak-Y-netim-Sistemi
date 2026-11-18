"""alembic head birlestirme: danisan psikolog pasifligi isareti + veri butunlugu kisitlari

#402 (veri butunlugu, e8b4d2f6a193) ve #403 (danisan psikolog pasifligi isareti, ccd4e7b1a925) ayni migration'a
(d6c3a9e1f407) bagli olarak ayni gun birlestirildi; zincir ikiye ayrildi ("Multiple head revisions"). Bu revizyon iki ucu
birlestirir. Sema degistirmez, veriye dokunmaz.

Hangi sirayla uygulanmis olursa olsun (yalnizca biri uygulanmis veritabani da dahil) `alembic upgrade head` eksik olani
uygular ve bu revizyonla tek uca iner.

Revision ID: f3c8a1d7b520
Revises: ccd4e7b1a925, e8b4d2f6a193
Create Date: 2026-11-18 18:00:00.000000

"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "f3c8a1d7b520"
down_revision: Union[str, Sequence[str], None] = ("ccd4e7b1a925", "e8b4d2f6a193")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Iki kolu birlestirir; sema/veri degisikligi yoktur."""
    pass


def downgrade() -> None:
    """Birlestirmeyi geri alir; sema/veri degisikligi yoktur."""
    pass
