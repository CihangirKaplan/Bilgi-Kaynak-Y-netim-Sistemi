"""Danışma Masası izinlerini düzelt (idempotent onarım migration'ı).

Elle yönetilen veritabanlarında DANISMA_OTURUMU_GORUNTULE / DANISMA_OTURUMU_YONETIM
izinleri eksik kalabiliyor ve Raporlar ekranı 403 veriyor. Bu migration izinleri
yoksa oluşturur, varsa doğru değere çeker; tekrar çalıştırmak güvenlidir.

Revision ID: a3c9d17e5b42
Revises: 56d233060538
"""

from alembic import op

revision = "a3c9d17e5b42"
down_revision = "56d233060538"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama) VALUES
          ('DANISMA_OTURUMU_GORUNTULE', 'Danışma masası raporlarını görüntüleme'),
          ('DANISMA_OTURUMU_YONETIM', 'Danışma masası öğrenci oturumlarını görüntüleme, düzenleme ve onaylama')
        ON CONFLICT (izin_adi) DO UPDATE SET aciklama = EXCLUDED.aciklama;
    """)

    # Raporlar: Memur, Müdür, Admin
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id,
               CASE WHEN r.rol_adi IN ('MEMUR', 'MUDUR', 'ADMIN') THEN 1 ELSE 0 END
        FROM roller r CROSS JOIN izinler i
        WHERE i.izin_adi = 'DANISMA_OTURUMU_GORUNTULE'
        ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)

    # Yönetim: Memur, Admin
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id,
               CASE WHEN r.rol_adi IN ('MEMUR', 'ADMIN') THEN 1 ELSE 0 END
        FROM roller r CROSS JOIN izinler i
        WHERE i.izin_adi = 'DANISMA_OTURUMU_YONETIM'
        ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)

    # Öğrenci görev izni: yalnızca Danışma Öğrencisi ve Admin
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id,
               CASE WHEN r.rol_adi IN ('DANISMA_OGRENCISI', 'ADMIN') THEN 1 ELSE 0 END
        FROM roller r CROSS JOIN izinler i
        WHERE i.izin_adi = 'DANISMA_OTURUMU_YONET'
        ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)


def downgrade():
    # Önceki migration'lar bu izinleri zaten yönetir; onarım migration'ı geri alınırken
    # izinler silinmez (aksi halde çalışan sistemde 403 oluşur).
    pass