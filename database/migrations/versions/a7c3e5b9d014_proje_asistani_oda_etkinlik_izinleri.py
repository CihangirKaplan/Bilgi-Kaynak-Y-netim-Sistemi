"""Proje Asistanı'na Oda Etkinlikleri görüntüleme ve yönetme izinlerini ver.

Oda Etkinlikleri izinleri ilk eklendiğinde (b3a6e8c9d201) yalnızca Yönetici, Müdür ve Memur yönetebilir; Psikolog ve Danışma Öğrencisi görüntüleyebilirdi.
Proje Asistanı'nın bu izinlerden yoksun kalması için belgelenmiş bir gerekçe yoktu: etkinlikleri düzenleyen merkez personeli arasında yer alıyor ve odaların
doluluğunu (Oda Kullanımı) zaten görüyor. Bu geçiş, Proje Asistanı için hem `ODA_ETKINLIK_GORUNTULE` hem `ODA_ETKINLIK_YONET` iznini açar; böylece menüde
"Oda Etkinlikleri" sayfası çıkar ve etkinlik ekleyip düzenleyebilir/iptal edebilir. Yönetici izni Rol & İzin Yönetimi ekranından her zaman değiştirebilir.

Not: Bu geçiş, Proje Asistanı için bu iki iznin varsayılanını belirler; Rol & İzin Yönetimi'nde bu iznin bilerek kapatılmış olduğu bir kurulumda yeniden açar
(önceki değer ayrıca saklanmaz). Geri alma (downgrade) iki izni yeniden kapatır.

Revision ID: a7c3e5b9d014
Revises: f4c8a2e6b917
"""

from alembic import op

revision = "a7c3e5b9d014"
down_revision = "f4c8a2e6b917"
branch_labels = None
depends_on = None

IZINLER = ("ODA_ETKINLIK_GORUNTULE", "ODA_ETKINLIK_YONET")


def _izinleri_ayarla(deger):
    op.execute(f"""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id, {int(deger)}
        FROM roller r
        CROSS JOIN izinler i
        WHERE UPPER(r.rol_adi) = 'PROJE_ASISTANI'
          AND i.izin_adi IN ('ODA_ETKINLIK_GORUNTULE', 'ODA_ETKINLIK_YONET')
        ON CONFLICT (rol_id, izin_id) DO UPDATE SET izin_var = EXCLUDED.izin_var
    """)


def upgrade():
    _izinleri_ayarla(1)


def downgrade():
    _izinleri_ayarla(0)
