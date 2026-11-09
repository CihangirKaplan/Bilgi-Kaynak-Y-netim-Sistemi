"""Faaliyet kayıtlarının geçmiş puanlarını koru."""

from alembic import op
import sqlalchemy as sa


revision = "9c7e4a21b6d0"
down_revision = "0ddab90bd5a2"
branch_labels = None
depends_on = None


def upgrade():
    # Önce boş sütunu oluşturuyoruz.
    op.add_column(
        "ogrenci_faaliyet_takip",
        sa.Column(
            "kayit_puani",
            sa.Integer(),
            nullable=True
        )
    )

    # Mevcut faaliyet kayıtlarının puanlarını
    # bugünkü faaliyet puanlarıyla sabitliyoruz.
    op.execute("""
        UPDATE ogrenci_faaliyet_takip AS t
        SET kayit_puani = f.puan
        FROM faaliyetler AS f
        WHERE t.faaliyet_id = f.faaliyet_id;
    """)

    # Eski kayıtlar doldurulduktan sonra
    # yeni alanı zorunlu yapıyoruz.
    op.alter_column(
        "ogrenci_faaliyet_takip",
        "kayit_puani",
        existing_type=sa.Integer(),
        nullable=False
    )

    op.create_check_constraint(
        "ck_ogrenci_faaliyet_kayit_puani",
        "ogrenci_faaliyet_takip",
        "kayit_puani >= 0"
    )


def downgrade():
    op.drop_constraint(
        "ck_ogrenci_faaliyet_kayit_puani",
        "ogrenci_faaliyet_takip",
        type_="check"
    )

    op.drop_column(
        "ogrenci_faaliyet_takip",
        "kayit_puani"
    )
