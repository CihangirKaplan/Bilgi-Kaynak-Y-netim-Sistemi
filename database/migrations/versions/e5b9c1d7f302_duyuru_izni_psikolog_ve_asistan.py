"""Duyuru yayınlama izni (DUYURU_YONET): Psikolog ve Proje Asistanı da yayınlayabilsin.

Duyurular ilk eklendiğinde (c9d2e4f6a801) yalnızca Yönetici, Müdür ve Memur yayınlayabiliyordu. Merkezde duyuruyu yalnızca Danışma Öğrencisi dışındaki
herkesin yayınlaması istendi: bu geçiş Psikolog ve Proje Asistanı için `DUYURU_YONET` iznini açar (Danışma Öğrencisi kapalı kalır). Yönetici izni Rol & İzin
Yönetimi ekranından her zaman değiştirebilir.

Not: Bu geçiş, iki rol için varsayılanı belirler; Rol & İzin Yönetimi'nde bu iznin bilerek kapatılmış olduğu bir kurulumda yeniden açar (önceki değer ayrıca
saklanmaz). Geri alma (downgrade) iki rol için izni yeniden kapatır.

Revision ID: e5b9c1d7f302
Revises: d4a8b6c2e913
"""

from alembic import op

revision = "e5b9c1d7f302"
down_revision = "d4a8b6c2e913"
branch_labels = None
depends_on = None


def _izni_ayarla(deger):
    op.execute(f"""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id, {int(deger)}
        FROM roller r
        CROSS JOIN izinler i
        WHERE UPPER(r.rol_adi) IN ('PSIKOLOG', 'PROJE_ASISTANI')
          AND i.izin_adi = 'DUYURU_YONET'
        ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = EXCLUDED.izin_var
    """)


def upgrade():
    _izni_ayarla(1)


def downgrade():
    _izni_ayarla(0)
