"""Öğrenci kaydını kalıcı silme izni (10 yıllık saklama süresi sonunda imha).

Önceden silme, öğrenci listeleme/ekleme iznine (FAALIYET_KAYITLARI_DUZENLE) bağlıydı. Kalıcı ve geri alınamaz olduğu için
ayrı bir izne alınır; Admin ve Müdür'e verilir, diğer rollere verilmez.

Revision ID: f4c8a2e6b917
Revises: d5f2a9c1b843
"""

from alembic import op

revision = "f4c8a2e6b917"
down_revision = "d5f2a9c1b843"
branch_labels = None
depends_on = None

IZIN = "OGRENCI_KAYDI_SIL"


def upgrade():
    baglanti = op.get_bind()
    baglanti.exec_driver_sql(
        """
        INSERT INTO izinler (izin_adi, aciklama, gorunen_ad)
        VALUES (%s, %s, %s)
        ON CONFLICT (izin_adi) DO NOTHING
        """,
        (IZIN, "Öğrenci kaydını kalıcı silme (10 yıllık saklama süresi sonunda)", "Öğrenci Kaydını Kalıcı Sil"),
    )

    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE WHEN UPPER(r.rol_adi) IN ('ADMIN', 'MUDUR') THEN 1 ELSE 0 END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi = 'OGRENCI_KAYDI_SIL'
        ON CONFLICT (rol_id, izin_id) DO NOTHING
    """)


def downgrade():
    op.execute("""
        DELETE FROM rol_izinleri
        WHERE izin_id IN (SELECT izin_id FROM izinler WHERE izin_adi = 'OGRENCI_KAYDI_SIL')
    """)
    op.execute("DELETE FROM izinler WHERE izin_adi = 'OGRENCI_KAYDI_SIL'")
