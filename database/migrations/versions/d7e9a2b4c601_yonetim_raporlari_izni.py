"""Yönetim raporları görüntüleme izni.

Revision ID: d7e9a2b4c601
Revises: c8f2a5d1e704
"""

from alembic import op

revision = "d7e9a2b4c601"
down_revision = "c8f2a5d1e704"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama)
        VALUES (
            'YONETIM_RAPORLARI_GORUNTULE',
            'Merkezin yönetim raporlarını ve istatistiklerini görüntüleme'
        )
        ON CONFLICT (izin_adi)
        DO UPDATE SET aciklama = EXCLUDED.aciklama;
    """)

    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE
                WHEN UPPER(r.rol_adi) IN ('MUDUR', 'ADMIN')
                THEN 1
                ELSE 0
            END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi = 'YONETIM_RAPORLARI_GORUNTULE'
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)


def downgrade():
    op.execute("""
        DELETE FROM rol_izinleri
        WHERE izin_id IN (
            SELECT izin_id
            FROM izinler
            WHERE izin_adi = 'YONETIM_RAPORLARI_GORUNTULE'
        );
    """)

    op.execute("""
        DELETE FROM izinler
        WHERE izin_adi = 'YONETIM_RAPORLARI_GORUNTULE';
    """)
