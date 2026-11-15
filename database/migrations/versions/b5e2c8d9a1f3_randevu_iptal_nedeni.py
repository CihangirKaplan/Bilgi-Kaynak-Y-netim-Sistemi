"""randevu iptal nedeni ve notu

Revision ID: b5e2c8d9a1f3
Revises: f1c8d6a32e75
Create Date: 2026-11-13 12:00:00.000000

Randevu iptal edilirken hazır listeden neden (zorunlu) ve kısa not (isteğe bağlı; "Diğer" için zorunlu) saklanır.
Not, danışan kodlu tabloda bilinçli olarak açılmış TEK serbest metin alanıdır: en çok 100 karakter, arayüzde
"kişisel bilgi yazmayın" uyarısı vardır ve FR-008 koruma testlerinde açık bir istisna olarak tanımlıdır.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5e2c8d9a1f3"
down_revision: Union[str, Sequence[str], None] = "f1c8d6a32e75"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEDENLER = ("DANISAN_TALEBI", "PSIKOLOG_MAZERETI", "ODA_EKIPMAN_SORUNU", "HATALI_KAYIT", "DIGER")


def upgrade():
    op.execute("ALTER TABLE randevular ADD COLUMN iptal_nedeni VARCHAR(30)")
    op.execute("ALTER TABLE randevular ADD COLUMN iptal_notu VARCHAR(100)")
    liste = ", ".join(f"\'{n}\'" for n in NEDENLER)
    op.execute(f"ALTER TABLE randevular ADD CONSTRAINT randevular_iptal_nedeni_gecerli CHECK (iptal_nedeni IS NULL OR iptal_nedeni IN ({liste}))")
    op.execute("ALTER TABLE randevular ADD CONSTRAINT randevular_iptal_nedeni_yalniz_iptalde CHECK (iptal_nedeni IS NULL OR durum = \'IPTAL_EDILDI\')")
    op.execute("ALTER TABLE randevular ADD CONSTRAINT randevular_iptal_notu_nedene_bagli CHECK (iptal_notu IS NULL OR iptal_nedeni IS NOT NULL)")
    op.execute("ALTER TABLE randevular ADD CONSTRAINT randevular_diger_icin_not_zorunlu CHECK (iptal_nedeni IS DISTINCT FROM \'DIGER\' OR (iptal_notu IS NOT NULL AND btrim(iptal_notu) <> \'\'))")


def downgrade():
    for kisit in ("randevular_diger_icin_not_zorunlu", "randevular_iptal_notu_nedene_bagli",
                  "randevular_iptal_nedeni_yalniz_iptalde", "randevular_iptal_nedeni_gecerli"):
        op.execute(f"ALTER TABLE randevular DROP CONSTRAINT IF EXISTS {kisit}")
    op.execute("ALTER TABLE randevular DROP COLUMN IF EXISTS iptal_notu")
    op.execute("ALTER TABLE randevular DROP COLUMN IF EXISTS iptal_nedeni")
