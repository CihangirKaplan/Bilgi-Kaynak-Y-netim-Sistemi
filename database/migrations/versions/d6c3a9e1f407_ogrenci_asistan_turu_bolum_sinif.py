"""ogrenci_turu enum'una ASISTAN eklenir; ogrenciler tablosuna bolum ve sinif sütunları eklenir

Revision ID: d6c3a9e1f407
Revises: a9d3c7e1f452
Create Date: 2026-11-18 13:00:00.000000

Sistemde üç öğrenci türü vardır: Gönüllü, Danışma Masası ve Asistan. "Yeni Öğrenci" penceresi bu üç türü sunuyor ve
Bölüm / Sınıf bilgisini topluyordu; ancak 'ASISTAN' değeri ile ogrenciler.bolum / ogrenciler.sinif sütunları migrasyonlarda
yoktu (yalnızca bazı veritabanlarına elle eklenmişti). Bu migrasyon ikisini şemaya ekler; zaten var olan veritabanlarında
(IF NOT EXISTS) hiçbir şey değişmez.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d6c3a9e1f407"
down_revision: Union[str, Sequence[str], None] = "a9d3c7e1f452"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # PostgreSQL, enum'a değer eklemeyi bir işlemin (transaction) içinde kullanılabilir kılmaz; bu yüzden ayrı işlemde eklenir.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE ogrenci_turu ADD VALUE IF NOT EXISTS 'ASISTAN'")
    op.execute("ALTER TABLE ogrenciler ADD COLUMN IF NOT EXISTS bolum VARCHAR(100)")
    op.execute("ALTER TABLE ogrenciler ADD COLUMN IF NOT EXISTS sinif VARCHAR(20)")


def downgrade():
    # Enum'dan tek değer silmek PostgreSQL'de desteklenmez; sütunlarda veri olabileceği için de silinmez.
    pass
