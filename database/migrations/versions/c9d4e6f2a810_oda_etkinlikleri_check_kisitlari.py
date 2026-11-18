"""Oda etkinlikleri zaman ve katılımcı sayısı kontrolleri.

Revision ID: c9d4e6f2a810
Revises: b3a6e8c9d201
"""

from alembic import op

revision = "c9d4e6f2a810"
down_revision = "b3a6e8c9d201"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "oda_etkinlikleri_zaman_kontrol",
        "oda_etkinlikleri",
        "baslangic_zamani < bitis_zamani",
    )

    op.create_check_constraint(
        "oda_etkinlikleri_katilimci_sayisi_kontrol",
        "oda_etkinlikleri",
        "katilimci_sayisi IS NULL OR katilimci_sayisi >= 0",
    )


def downgrade():
    op.drop_constraint(
        "oda_etkinlikleri_katilimci_sayisi_kontrol",
        "oda_etkinlikleri",
        type_="check",
    )

    op.drop_constraint(
        "oda_etkinlikleri_zaman_kontrol",
        "oda_etkinlikleri",
        type_="check",
    )
