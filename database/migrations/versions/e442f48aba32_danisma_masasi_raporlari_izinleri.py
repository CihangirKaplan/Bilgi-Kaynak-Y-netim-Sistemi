"""Danışma Masası Raporları izinleri.

Revision ID: e442f48aba32
Revises: 8a9f73d2460d
"""

from alembic import op

revision = "e442f48aba32"
down_revision = "8a9f73d2460d"
branch_labels = None
depends_on = None


def upgrade():
    # Rapor görüntüleme iznini oluştur.
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama)
        VALUES (
            'DANISMA_OTURUMU_GORUNTULE',
            'Danışma masası görev kayıtlarını ve raporlarını görüntüleme'
        )
        ON CONFLICT (izin_adi)
        DO UPDATE SET aciklama = EXCLUDED.aciklama;
    """)

    # Rapor izni: Memur, Müdür ve Admin.
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE
                WHEN r.rol_adi IN ('MEMUR', 'MUDUR', 'ADMIN')
                THEN 1
                ELSE 0
            END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi = 'DANISMA_OTURUMU_GORUNTULE'
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)

    # Öğrenci görev izni yalnızca öğrenci rolünde kalsın.
    op.execute("""
        UPDATE rol_izinleri AS ri
        SET izin_var = CASE
            WHEN r.rol_adi = 'DANISMA_OGRENCISI'
            THEN 1
            ELSE 0
        END
        FROM roller r, izinler i
        WHERE ri.rol_id = r.rol_id
          AND ri.izin_id = i.izin_id
          AND i.izin_adi = 'DANISMA_OTURUMU_YONET';
    """)


def downgrade():
    # Eklenen rapor izin ilişkilerini kaldır.
    op.execute("""
        DELETE FROM rol_izinleri
        WHERE izin_id IN (
            SELECT izin_id
            FROM izinler
            WHERE izin_adi = 'DANISMA_OTURUMU_GORUNTULE'
        );
    """)

    op.execute("""
        DELETE FROM izinler
        WHERE izin_adi = 'DANISMA_OTURUMU_GORUNTULE';
    """)

    # Önceki migration'daki admin öğrenci iznini geri yükle.
    op.execute("""
        UPDATE rol_izinleri AS ri
        SET izin_var = 1
        FROM roller r, izinler i
        WHERE ri.rol_id = r.rol_id
          AND ri.izin_id = i.izin_id
          AND r.rol_adi = 'ADMIN'
          AND i.izin_adi = 'DANISMA_OTURUMU_YONET';
    """)
