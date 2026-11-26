"""Denetim kayıtlarında "kullanıcının son girişi" sorgusu için kısmi indeks.

Yetki Raporu her kullanıcı için `MAX(olusturulma_tarihi) ... WHERE kullanici_id = ? AND olay_turu = 'LOGIN'` çalıştırır. Bu indeks olmadan
sorgu, denetim tablosunun tamamını tarihe göre gezip süzüyordu: 1 milyon kayıtta (yaklaşık 10 yıllık kullanım) rapor 4 saniyeyi buldu.
Kısmi indeksle aynı sorgu milisaniyenin altında çalışır; indeks yalnızca LOGIN satırlarını içerdiği için küçüktür ve yazmayı yavaşlatmaz.

Revision ID: d4a8b6c2e913
Revises: c9d2e4f6a801
"""

from alembic import op

revision = "d4a8b6c2e913"
down_revision = "c9d2e4f6a801"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_denetim_login_kullanici_tarih
        ON denetim_kayitlari (kullanici_id, olusturulma_tarihi DESC)
        WHERE olay_turu = 'LOGIN'
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_denetim_login_kullanici_tarih")
