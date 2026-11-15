"""terapi turu danisandan kalkar (yalnizca randevuda tutulur)

Revision ID: e1a7c4b9d3f6
Revises: c3d8e5a1f7b2
Create Date: 2026-11-14 15:00:00.000000

Terapi türü her randevuda değişebilen bir bilgidir; danışana bağlı tutulmaz. danisan_kodlari.terapi_turu sütunu ve yaş grubu-terapi
uyum kısıtı kaldırılır; yaş grubu için yalnızca kapalı liste kısıtı kalır. randevular.terapi_turu aynen durur.
Downgrade: sütun yeniden eklenir; yaş grubu bilinen danışanlara nötr değer (BIREYSEL_TERAPI) yazılır (eski kısıt NULL kabul etmez).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a7c4b9d3f6"
down_revision: Union[str, Sequence[str], None] = "c3d8e5a1f7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE danisan_kodlari DROP CONSTRAINT IF EXISTS danisan_kodlari_yas_terapi_gecerli")
    op.execute("ALTER TABLE danisan_kodlari DROP COLUMN IF EXISTS terapi_turu")
    op.execute(
        "ALTER TABLE danisan_kodlari ADD CONSTRAINT danisan_kodlari_yas_grubu_gecerli "
        "CHECK (yas_grubu IS NULL OR yas_grubu IN (\'COCUK\', \'YETISKIN\'))"
    )


def downgrade():
    op.execute("ALTER TABLE danisan_kodlari DROP CONSTRAINT IF EXISTS danisan_kodlari_yas_grubu_gecerli")
    op.execute("ALTER TABLE danisan_kodlari ADD COLUMN terapi_turu VARCHAR(30)")
    op.execute("UPDATE danisan_kodlari SET terapi_turu = \'BIREYSEL_TERAPI\' WHERE yas_grubu IS NOT NULL")
    op.execute(
        "ALTER TABLE danisan_kodlari ADD CONSTRAINT danisan_kodlari_yas_terapi_gecerli CHECK ("
        "(yas_grubu IS NULL AND terapi_turu IS NULL) "
        "OR (yas_grubu IS NOT NULL AND yas_grubu = \'COCUK\' AND terapi_turu IS NOT NULL AND terapi_turu IN (\'OYUN_TERAPISI\', \'BIREYSEL_TERAPI\')) "
        "OR (yas_grubu IS NOT NULL AND yas_grubu = \'YETISKIN\' AND terapi_turu IS NOT NULL AND terapi_turu = \'BIREYSEL_TERAPI\'))"
    )
