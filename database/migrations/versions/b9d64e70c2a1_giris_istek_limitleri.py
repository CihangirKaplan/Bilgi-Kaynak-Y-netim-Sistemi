"""Giris CAPTCHA ve login istek sinirlari.

Revision ID: b9d64e70c2a1
Revises: a5c7e9d21036
"""

from alembic import op
import sqlalchemy as sa

revision = "b9d64e70c2a1"
down_revision = "a5c7e9d21036"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "giris_istek_limitleri",
        sa.Column(
            "anahtar",
            sa.String(64),
            primary_key=True,
        ),
        sa.Column(
            "pencere_baslangici",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "istek_sayisi",
            sa.Integer(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "istek_sayisi >= 1",
            name="ck_giris_istek_sayisi",
        ),
    )

    op.create_index(
        "ix_giris_istek_pencere",
        "giris_istek_limitleri",
        ["pencere_baslangici"],
    )


def downgrade():
    op.drop_index(
        "ix_giris_istek_pencere",
        table_name="giris_istek_limitleri",
    )
    op.drop_table("giris_istek_limitleri")
