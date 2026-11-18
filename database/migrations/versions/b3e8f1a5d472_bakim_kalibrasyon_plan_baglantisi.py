"""Bakım ve kalibrasyon kayıtlarına plan bağlantısı (plan_id)

Revision ID: b3e8f1a5d472
Revises: e7c1a9d4b362
Create Date: 2026-11-17 18:00:00.000000

Bakım/kalibrasyon formları kaydın hangi plana ait olduğunu (plan_id) gönderiyor, ancak yalnızca planın "sonraki tarihi"
ilerletiliyor, bağlantı saklanmıyordu; hangi kaydın hangi planı yerine getirdiği sonradan görülemiyordu. Bu migrasyon iki
tabloya plan_id sütunu ekler. Plan silinirse kayıtlar silinmez, yalnızca bağlantı boşalır (ON DELETE SET NULL).
Mevcut kayıtlar plansız (NULL) kalır.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3e8f1a5d472"
down_revision: Union[str, Sequence[str], None] = "e7c1a9d4b362"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLOLAR = ("cihaz_bakimlari", "cihaz_kalibrasyonlari")


def upgrade():
    for tablo in TABLOLAR:
        op.execute(
            f"ALTER TABLE {tablo} ADD COLUMN plan_id INT "
            f"REFERENCES cihaz_bakim_planlari(plan_id) ON DELETE SET NULL"
        )
        op.execute(f"CREATE INDEX ix_{tablo}_plan_id ON {tablo} (plan_id)")


def downgrade():
    for tablo in TABLOLAR:
        op.execute(f"DROP INDEX IF EXISTS ix_{tablo}_plan_id")
        op.execute(f"ALTER TABLE {tablo} DROP COLUMN IF EXISTS plan_id")
