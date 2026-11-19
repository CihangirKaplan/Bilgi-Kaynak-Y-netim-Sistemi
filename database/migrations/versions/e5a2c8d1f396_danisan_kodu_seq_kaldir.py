"""kullanilmayan danisan_kodu_seq sayacini kaldir

Danisan kodu artik yila gore uretiliyor (DAN-<yil>-<sira>; sira o yilin en buyuk kodunun bir fazlasi) ve kodlar kayit aninda
aynı yil icin kilit altinda uretiliyor; global sayac (danisan_kodu_seq) hicbir yerde kullanilmiyor. Bos kalan sayaci kaldirir.

Geri alma, sayaci yeniden olusturur ve mevcut en buyuk kod numarasina ayarlar (eski davranisla uyumlu). Veriye dokunmaz.

Revision ID: e5a2c8d1f396
Revises: 61d0c93faf24
Create Date: 2026-11-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a2c8d1f396"
down_revision: Union[str, Sequence[str], None] = "61d0c93faf24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("DROP SEQUENCE IF EXISTS danisan_kodu_seq;")


def downgrade():
    op.execute("CREATE SEQUENCE IF NOT EXISTS danisan_kodu_seq START 1;")
    op.execute(
        "SELECT setval('danisan_kodu_seq', GREATEST(COALESCE((SELECT MAX(SUBSTRING(danisan_kod_id FROM '^DAN-[0-9]{4}-([0-9]+)$')::BIGINT) "
        "FROM danisan_kodlari WHERE danisan_kod_id ~ '^DAN-[0-9]{4}-[0-9]+$'), 0), 1), TRUE);"
    )
