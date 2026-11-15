"""Parola sifirlama RBAC izni ve Audit olay turu.

Revision ID: d82c4a71f06b
Revises: b9d64e70c2a1
"""

from alembic import op

revision = "d82c4a71f06b"
down_revision = "b9d64e70c2a1"
branch_labels = None
depends_on = None


def upgrade():
    # Yeni Audit olay türü
    op.execute("""
        ALTER TYPE denetim_olay_turu
        ADD VALUE IF NOT EXISTS 'PASSWORD_RESET';
    """)

    # Yeni RBAC izni
    op.execute("""
        INSERT INTO izinler
            (izin_adi, aciklama, gorunen_ad)
        VALUES (
            'KULLANICI_PAROLA_SIFIRLA',
            'Kullanıcı parolasını yönetici tarafından sıfırlama',
            'Kullanıcı Parola Sıfırla'
        )
        ON CONFLICT (izin_adi)
        DO UPDATE SET
            aciklama = EXCLUDED.aciklama,
            gorunen_ad = EXCLUDED.gorunen_ad;
    """)

    # Yalnızca ADMIN rolüne izin ver.
    op.execute("""
        INSERT INTO rol_izinleri
            (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE
                WHEN r.rol_adi = 'ADMIN' THEN 1
                ELSE 0
            END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi = 'KULLANICI_PAROLA_SIFIRLA'
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET
            izin_var = EXCLUDED.izin_var;
    """)


def downgrade():
    # Önce rol-izin ilişkilerini kaldır.
    op.execute("""
        DELETE FROM rol_izinleri
        WHERE izin_id IN (
            SELECT izin_id
            FROM izinler
            WHERE izin_adi = 'KULLANICI_PAROLA_SIFIRLA'
        );
    """)

    # Ardından yeni izni kaldır.
    op.execute("""
        DELETE FROM izinler
        WHERE izin_adi = 'KULLANICI_PAROLA_SIFIRLA';
    """)

    # PASSWORD_RESET ENUM değeri korunur.
    # PostgreSQL ENUM değerini silmek için türün yeniden
    # oluşturulması gerekir; mevcut Audit kayıtlarını
    # riske atmamak amacıyla otomatik kaldırılmıyor.
