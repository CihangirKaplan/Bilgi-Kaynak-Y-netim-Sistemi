"""Giris CAPTCHA dogrulama kayitlari.

Revision ID: a5c7e9d21036
Revises: c4e8a1b7d205
"""

from alembic import op
import sqlalchemy as sa

revision = "a5c7e9d21036"
down_revision = "c4e8a1b7d205"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "giris_captcha_kodlari",
        sa.Column(
            "captcha_id", sa.String(32),
            primary_key=True,
        ),
        sa.Column(
            "kod_ozeti", sa.String(64),
            nullable=False,
        ),
        sa.Column(
            "gecerlilik_sonu",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "olusturulma_tarihi",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_giris_captcha_gecerlilik",
        "giris_captcha_kodlari",
        ["gecerlilik_sonu"],
    )


def downgrade():
    op.drop_index(
        "ix_giris_captcha_gecerlilik",
        table_name="giris_captcha_kodlari",
    )
    op.drop_table("giris_captcha_kodlari")
