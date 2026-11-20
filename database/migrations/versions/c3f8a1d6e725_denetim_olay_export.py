"""denetim olay turu: EXPORT (liste Excel aktarimi) eklendi

Revision ID: c3f8a1d6e725
Revises: b9d4f7a2c613
Create Date: 2026-11-20 10:00:00.000000

Cihaz Envanteri, Ogrenciler ve Danisanlar listelerinden Excel'e aktarim yapildiginda kimin, ne zaman, kac satir
aktardigi denetim kaydina EXPORT olayi olarak yazilir.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c3f8a1d6e725'
down_revision: Union[str, Sequence[str], None] = 'b9d4f7a2c613'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # PostgreSQL ENUM'a deger eklemeyi transaction icinde reddeder; once aktif islem bitirilir.
    op.execute("COMMIT")
    op.execute("ALTER TYPE denetim_olay_turu ADD VALUE IF NOT EXISTS 'EXPORT'")


def downgrade():
    # PostgreSQL ENUM'dan tek bir deger silmeyi desteklemez; geri alma bilerek bos birakilir (EXPORT kayitlari kalir).
    pass
