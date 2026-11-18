"""Kullanılmayan giris_captcha_kodlari tablosunu kaldır; iki migration ucunu birleştir

Revision ID: c2e5a9d4b681
Revises: f1a7c3e9b524, f3c8a1d7b520
Create Date: 2026-11-18 17:00:00.000000

1. giris_captcha_kodlari: tabloyu kullanan hiçbir kod ve ekran yok (masaüstü istemcide CAPTCHA yok; korumayı hesap kilidi ve
   IP bazlı giriş sınırı sağlıyor). Kullanılmayan tablo kaldırılır. Tablo hiç yazılmadığı için veri kaybı olmaz.
2. #404 (f1a7c3e9b524) ve #405 (f3c8a1d7b520) paralel birleştirildiği için zincir yine iki uçluydu; bu revizyon ikisini
   tek uca bağlar.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c2e5a9d4b681"
down_revision: Union[str, Sequence[str], None] = ("f1a7c3e9b524", "f3c8a1d7b520")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("DROP TABLE IF EXISTS giris_captcha_kodlari")


def downgrade():
    op.execute(
        """
        CREATE TABLE giris_captcha_kodlari (
            captcha_id VARCHAR(32) PRIMARY KEY,
            kod_ozeti VARCHAR(64) NOT NULL,
            gecerlilik_sonu TIMESTAMP WITH TIME ZONE NOT NULL,
            olusturulma_tarihi TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX ix_giris_captcha_gecerlilik ON giris_captcha_kodlari (gecerlilik_sonu)")
