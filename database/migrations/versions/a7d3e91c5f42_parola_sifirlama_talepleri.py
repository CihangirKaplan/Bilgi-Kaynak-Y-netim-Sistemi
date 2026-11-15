"""Parola sifirlama talepleri: kullanici yoneticiye bildirir, yonetici bildirimden gorur.

Her kullanici icin ayni anda en fazla bir ACIK talep bulunabilir (kismi tekil indeks). Talep, yonetici
parolayi sifirlayinca TAMAMLANDI, bildirimi kapatinca KAPATILDI olur.

Revision ID: a7d3e91c5f42
Revises: f3a9c2e47b18
"""

from alembic import op

revision = "a7d3e91c5f42"
down_revision = "f3a9c2e47b18"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE parola_sifirlama_talepleri (
            talep_id SERIAL PRIMARY KEY,
            kullanici_id INT NOT NULL REFERENCES kullanicilar(kullanici_id),
            talep_zamani TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            durum VARCHAR(12) NOT NULL DEFAULT 'ACIK'
                CHECK (durum IN ('ACIK', 'TAMAMLANDI', 'KAPATILDI')),
            kapanis_zamani TIMESTAMP,
            kapatan_kullanici_id INT REFERENCES kullanicilar(kullanici_id),
            CONSTRAINT parola_talep_kapanis_tutarli CHECK (
                (durum = 'ACIK' AND kapanis_zamani IS NULL)
                OR (durum <> 'ACIK' AND kapanis_zamani IS NOT NULL)
            )
        );
    """)
    op.execute("""
        CREATE UNIQUE INDEX parola_sifirlama_acik_talep_tekil
        ON parola_sifirlama_talepleri (kullanici_id)
        WHERE durum = 'ACIK';
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS parola_sifirlama_acik_talep_tekil;")
    op.execute("DROP TABLE IF EXISTS parola_sifirlama_talepleri;")
