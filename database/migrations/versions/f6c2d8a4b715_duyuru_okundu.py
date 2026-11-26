"""Duyuruyu "okundu" işaretleme: kullanıcı başına gizleme (duyuru silinmez).

Her kullanıcı bir duyuruyu KENDİ ekranında okundu işaretleyip gizleyebilir; duyuru diğer kullanıcılar için yayında kalır ve silinmez. Okundu bilgisi
duyuru kaldırılınca (ya da kullanıcı silinince) kendiliğinden temizlenir.

Revision ID: f6c2d8a4b715
Revises: e5b9c1d7f302
"""

from alembic import op

revision = "f6c2d8a4b715"
down_revision = "e5b9c1d7f302"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS duyuru_okundu (
            duyuru_id INT NOT NULL REFERENCES duyurular(duyuru_id) ON DELETE CASCADE,
            kullanici_id INT NOT NULL REFERENCES kullanicilar(kullanici_id) ON DELETE CASCADE,
            okundu_zamani TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (duyuru_id, kullanici_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_duyuru_okundu_kullanici ON duyuru_okundu (kullanici_id)")      # yabancı anahtar indeksi (kullanıcının okuduklarını bulmak için)


def downgrade():
    op.execute("DROP TABLE IF EXISTS duyuru_okundu")
