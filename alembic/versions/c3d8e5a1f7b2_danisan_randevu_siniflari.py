"""danisan yas grubu ve terapi turu; randevu gorusme tipi ve terapi turu

Revision ID: c3d8e5a1f7b2
Revises: 4e17fe8847d8
Create Date: 2026-11-14 12:00:00.000000

Danışan: yas_grubu (COCUK / YETISKIN) ve terapi_turu (OYUN_TERAPISI / BIREYSEL_TERAPI). Mevcut danışanlar "belirtilmedi"
(NULL) kalır. Randevu: gorusme_tipi (YUZ_YUZE / ONLINE; mevcutlar YUZ_YUZE) ve terapi_turu (mevcutlar NULL).

Bunlar KAPALI LİSTELİ alanlardır (serbest metin yok); veritabanı CHECK kısıtlarıyla korunur. "terapi" sözcüğü FR-008 koruma
testlerinde klinik terim sayıldığı için, bu iki sütun testlerde açık ve belgelenmiş bir istisnadır.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d8e5a1f7b2"
down_revision: Union[str, Sequence[str], None] = "4e17fe8847d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE danisan_kodlari ADD COLUMN yas_grubu VARCHAR(20)")
    op.execute("ALTER TABLE danisan_kodlari ADD COLUMN terapi_turu VARCHAR(30)")
    op.execute(
        "ALTER TABLE danisan_kodlari ADD CONSTRAINT danisan_kodlari_yas_terapi_gecerli CHECK ("
        "(yas_grubu IS NULL AND terapi_turu IS NULL) "
        "OR (yas_grubu IS NOT NULL AND yas_grubu = \'COCUK\' AND terapi_turu IS NOT NULL AND terapi_turu IN (\'OYUN_TERAPISI\', \'BIREYSEL_TERAPI\')) "
        "OR (yas_grubu IS NOT NULL AND yas_grubu = \'YETISKIN\' AND terapi_turu IS NOT NULL AND terapi_turu = \'BIREYSEL_TERAPI\'))"
    )
    op.execute("ALTER TABLE randevular ADD COLUMN gorusme_tipi VARCHAR(20) NOT NULL DEFAULT \'YUZ_YUZE\'")
    op.execute("ALTER TABLE randevular ADD COLUMN terapi_turu VARCHAR(30)")
    op.execute("ALTER TABLE randevular ADD CONSTRAINT randevular_gorusme_tipi_gecerli CHECK (gorusme_tipi IN (\'YUZ_YUZE\', \'ONLINE\'))")
    op.execute(
        "ALTER TABLE randevular ADD CONSTRAINT randevular_terapi_turu_gecerli "
        "CHECK (terapi_turu IS NULL OR terapi_turu IN (\'OYUN_TERAPISI\', \'BIREYSEL_TERAPI\'))"
    )


def downgrade():
    op.execute("ALTER TABLE randevular DROP CONSTRAINT IF EXISTS randevular_terapi_turu_gecerli")
    op.execute("ALTER TABLE randevular DROP CONSTRAINT IF EXISTS randevular_gorusme_tipi_gecerli")
    op.execute("ALTER TABLE randevular DROP COLUMN IF EXISTS terapi_turu")
    op.execute("ALTER TABLE randevular DROP COLUMN IF EXISTS gorusme_tipi")
    op.execute("ALTER TABLE danisan_kodlari DROP CONSTRAINT IF EXISTS danisan_kodlari_yas_terapi_gecerli")
    op.execute("ALTER TABLE danisan_kodlari DROP COLUMN IF EXISTS terapi_turu")
    op.execute("ALTER TABLE danisan_kodlari DROP COLUMN IF EXISTS yas_grubu")
