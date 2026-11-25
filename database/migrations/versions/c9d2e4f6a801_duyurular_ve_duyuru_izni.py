"""Ana panel duyuruları: duyurular tablosu ve DUYURU_YONET izni.

Duyuruları giriş yapmış herkes okur (izin aramaz); yazmak ve kaldırmak DUYURU_YONET ister.
Varsayılan: Admin, Müdür ve Memur açık; diğer roller kapalı (yönetici Rol & İzin Yönetimi'nden değiştirebilir).

Revision ID: c9d2e4f6a801
Revises: a7c3e5b9d014
"""

from alembic import op

revision = "c9d2e4f6a801"
down_revision = "a7c3e5b9d014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS duyurular (
            duyuru_id SERIAL PRIMARY KEY,
            baslik VARCHAR(120) NOT NULL CHECK (length(btrim(baslik)) > 0),
            metin VARCHAR(1000) NOT NULL CHECK (length(btrim(metin)) > 0),
            olusturan_kullanici_id INT REFERENCES kullanicilar(kullanici_id) ON DELETE SET NULL,
            olusturma_zamani TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            son_gecerlilik_tarihi DATE
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_duyurular_olusturma ON duyurular (olusturma_zamani DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_duyurular_olusturan ON duyurular (olusturan_kullanici_id)")      # yabancı anahtar indeksi (silme/güncelleme hızlı kalsın)

    op.get_bind().exec_driver_sql(
        """
        INSERT INTO izinler (izin_adi, aciklama, gorunen_ad)
        VALUES (%s, %s, %s)
        ON CONFLICT (izin_adi) DO NOTHING
        """,
        ("DUYURU_YONET", "Ana panelde duyuru yayınlama ve kaldırma", "Duyuruları Yönet"),
    )

    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id,
               CASE WHEN UPPER(r.rol_adi) IN ('ADMIN', 'MUDUR', 'MEMUR') THEN 1 ELSE 0 END
        FROM roller r CROSS JOIN izinler i
        WHERE i.izin_adi = 'DUYURU_YONET'
        ON CONFLICT (rol_id, izin_id) DO NOTHING
    """)


def downgrade():
    op.execute("DELETE FROM rol_izinleri WHERE izin_id IN (SELECT izin_id FROM izinler WHERE izin_adi = 'DUYURU_YONET')")
    op.execute("DELETE FROM izinler WHERE izin_adi = 'DUYURU_YONET'")
    op.execute("DROP TABLE IF EXISTS duyurular")
