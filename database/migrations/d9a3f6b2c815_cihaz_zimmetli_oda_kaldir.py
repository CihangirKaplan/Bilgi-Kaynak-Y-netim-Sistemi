"""cihazlar.zimmetli_oda_id sütunu kaldırılır

Revision ID: d9a3f6b2c815
Revises: d5b9f2c7a418
Create Date: 2026-11-17 10:00:00.000000

"Zimmetli oda" cihazın sabit bulunduğu odayı tutuyordu ama hiçbir yerde gerçek bir işe yaramıyordu ve kafa karıştırıyordu.
Rezervasyon sırasında kullanılacak oda zaten `cihaz_rezervasyonlari.kullanilacak_oda_id` alanında seçilir. Sütun silinince
ona bağlı yabancı anahtar ve indeks de (ix_cihazlar_zimmetli_oda_id) silinir. Silinen değerler geri yüklenemez; geri alma
(downgrade) sütunu boş olarak geri ekler.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9a3f6b2c815"
down_revision: Union[str, Sequence[str], None] = "d5b9f2c7a418"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE cihazlar DROP COLUMN IF EXISTS zimmetli_oda_id")


def downgrade():
    op.execute("ALTER TABLE cihazlar ADD COLUMN IF NOT EXISTS zimmetli_oda_id INT REFERENCES odalar(oda_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cihazlar_zimmetli_oda_id ON cihazlar (zimmetli_oda_id)")
