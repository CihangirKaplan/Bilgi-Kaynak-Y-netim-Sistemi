"""cihaz rezervasyon cakisma kisiti

Revision ID: 81f41620df1f
Revises: 506031f640f1
Create Date: 2026-10-13 16:11:21.332690

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '81f41620df1f'
down_revision: Union[str, Sequence[str], None] = '506031f640f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.execute("""
    ALTER TABLE cihaz_rezervasyonlari
    ALTER COLUMN cihaz_id SET NOT NULL,
    ALTER COLUMN iptal_edildi_mi SET NOT NULL;
    """)

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")

    op.execute("""
        ALTER TABLE cihaz_rezervasyonlari
        ADD CONSTRAINT cihaz_rezervasyon_cakisma
        EXCLUDE USING gist (
            cihaz_id WITH =,
            tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&
        )
        WHERE (iptal_edildi_mi = FALSE);
    """)

    op.execute("""
        ALTER TABLE cihaz_rezervasyonlari
        ADD CONSTRAINT cihaz_rezervasyon_zaman_kontrol
        CHECK (baslangic_zamani < bitis_zamani);
    """)


def downgrade() -> None:
    """Eklenen kısıtları ve NOT NULL kurallarını kaldırır."""

    op.execute("""
        ALTER TABLE cihaz_rezervasyonlari
        DROP CONSTRAINT IF EXISTS cihaz_rezervasyon_zaman_kontrol;
    """)

    op.execute("""
        ALTER TABLE cihaz_rezervasyonlari
        DROP CONSTRAINT IF EXISTS cihaz_rezervasyon_cakisma;
    """)

    op.execute("""
        ALTER TABLE cihaz_rezervasyonlari
        ALTER COLUMN cihaz_id DROP NOT NULL,
        ALTER COLUMN iptal_edildi_mi DROP NOT NULL;
    """)
