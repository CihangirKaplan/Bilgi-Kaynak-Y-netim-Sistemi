"""Oda etkinlikleri için günlük kullanım aralıkları.

Revision ID: d7e5a1b9c302
Revises: c9d4e6f2a810
"""

from alembic import op
import sqlalchemy as sa

revision = "d7e5a1b9c302"
down_revision = "c9d4e6f2a810"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oda_etkinlik_gunleri",
        sa.Column(
            "gun_id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "etkinlik_id",
            sa.Integer(),
            sa.ForeignKey(
                "oda_etkinlikleri.etkinlik_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "baslangic_zamani",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "bitis_zamani",
            sa.DateTime(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "bitis_zamani > baslangic_zamani",
            name="oda_etkinlik_gunleri_zaman_check",
        ),
        sa.CheckConstraint(
            "baslangic_zamani::date = "
            "(bitis_zamani - INTERVAL '1 microsecond')::date",
            name="oda_etkinlik_gunleri_ayni_gun_check",
        ),
        sa.UniqueConstraint(
            "etkinlik_id",
            "baslangic_zamani",
            name="uq_oda_etkinlik_gun_baslangic",
        ),
    )

    op.create_index(
        "ix_oda_etkinlik_gunleri_etkinlik",
        "oda_etkinlik_gunleri",
        ["etkinlik_id"],
    )

    op.create_index(
        "ix_oda_etkinlik_gunleri_zaman",
        "oda_etkinlik_gunleri",
        ["baslangic_zamani", "bitis_zamani"],
    )

    # Mevcut etkinlikleri koruyarak günlük dilimlere ayır.
    # Geçmişte mesai dışı kaydedilmiş saatler de kaybolmaz.
    op.execute("""
        INSERT INTO oda_etkinlik_gunleri (
            etkinlik_id,
            baslangic_zamani,
            bitis_zamani
        )
        SELECT
            e.etkinlik_id,
            GREATEST(
                e.baslangic_zamani,
                gun.gun_baslangici
            ),
            LEAST(
                e.bitis_zamani,
                gun.gun_baslangici + INTERVAL '1 day'
            )
        FROM oda_etkinlikleri e
        CROSS JOIN LATERAL generate_series(
            date_trunc('day', e.baslangic_zamani),
            date_trunc(
                'day',
                e.bitis_zamani - INTERVAL '1 microsecond'
            ),
            INTERVAL '1 day'
        ) AS gun(gun_baslangici)
        WHERE e.bitis_zamani > e.baslangic_zamani
    """)


def downgrade():
    # Ana etkinlik kayıtları korunur.
    op.drop_index(
        "ix_oda_etkinlik_gunleri_zaman",
        table_name="oda_etkinlik_gunleri",
    )
    op.drop_index(
        "ix_oda_etkinlik_gunleri_etkinlik",
        table_name="oda_etkinlik_gunleri",
    )
    op.drop_table("oda_etkinlik_gunleri")
