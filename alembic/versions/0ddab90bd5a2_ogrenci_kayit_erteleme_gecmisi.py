"""Gönüllü öğrenci kayıt erteleme geçmişi."""

from alembic import op
import sqlalchemy as sa

revision = "0ddab90bd5a2"
down_revision = "d82c4a71f06b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ogrenci_kayit_erteleme_gecmisi",
        sa.Column(
            "erteleme_id",
            sa.Integer(),
            primary_key=True
        ),
        sa.Column(
            "ogrenci_id",
            sa.Integer(),
            sa.ForeignKey(
                "ogrenciler.ogrenci_id",
                ondelete="SET NULL"
            ),
            nullable=True
        ),
        sa.Column(
            "ogrenci_numarasi",
            sa.String(length=15),
            nullable=False
        ),
        sa.Column(
            "yeni_uyari_tarihi",
            sa.Date(),
            nullable=False
        ),
        sa.Column(
            "erteleyen_kullanici_id",
            sa.Integer(),
            sa.ForeignKey(
                "kullanicilar.kullanici_id",
                ondelete="SET NULL"
            )
        ),
        sa.Column(
            "olusturulma_tarihi",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text(
                "CURRENT_TIMESTAMP"
            )
        )
    )

    op.create_index(
        "ix_ogr_erteleme_ogrenci_id",
        "ogrenci_kayit_erteleme_gecmisi",
        ["ogrenci_id"]
    )


def downgrade():
    op.drop_index(
        "ix_ogr_erteleme_ogrenci_id",
        table_name="ogrenci_kayit_erteleme_gecmisi"
    )

    op.drop_table(
        "ogrenci_kayit_erteleme_gecmisi"
    )
