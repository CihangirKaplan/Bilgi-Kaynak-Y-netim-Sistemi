"""Oda Etkinlikleri görüntüleme ve yönetme izinleri.

Revision ID: b3a6e8c9d201
Revises: e0f32bef6d16
"""

from alembic import op

revision = "b3a6e8c9d201"
down_revision = "e0f32bef6d16"
branch_labels = None
depends_on = None


IZINLER = (
    (
        "ODA_ETKINLIK_GORUNTULE",
        "Oda etkinliklerini görüntüleme",
        "Oda Etkinliklerini Görüntüle",
    ),
    (
        "ODA_ETKINLIK_YONET",
        "Oda etkinliği ekleme, düzenleme ve iptal etme",
        "Oda Etkinliklerini Yönet",
    ),
)


def upgrade():
    baglanti = op.get_bind()

    for kod, aciklama, gorunen_ad in IZINLER:
        baglanti.exec_driver_sql(
            """
            INSERT INTO izinler (izin_adi, aciklama, gorunen_ad)
            VALUES (%s, %s, %s)
            ON CONFLICT (izin_adi) DO NOTHING
            """,
            (kod, aciklama, gorunen_ad),
        )

    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE
                WHEN UPPER(r.rol_adi) IN ('ADMIN', 'MUDUR', 'MEMUR')
                    THEN 1
                WHEN UPPER(r.rol_adi) IN (
                    'PSIKOLOG', 'DANISMA_OGRENCISI'
                ) AND i.izin_adi = 'ODA_ETKINLIK_GORUNTULE'
                    THEN 1
                ELSE 0
            END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi IN (
            'ODA_ETKINLIK_GORUNTULE',
            'ODA_ETKINLIK_YONET'
        )
        ON CONFLICT (rol_id, izin_id) DO NOTHING
    """)


def downgrade():
    op.execute("""
        DELETE FROM rol_izinleri
        WHERE izin_id IN (
            SELECT izin_id
            FROM izinler
            WHERE izin_adi IN (
                'ODA_ETKINLIK_GORUNTULE',
                'ODA_ETKINLIK_YONET'
            )
        )
    """)

    op.execute("""
        DELETE FROM izinler
        WHERE izin_adi IN (
            'ODA_ETKINLIK_GORUNTULE',
            'ODA_ETKINLIK_YONET'
        )
    """)
