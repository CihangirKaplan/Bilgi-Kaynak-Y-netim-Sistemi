"""bakim ve kalibrasyon kayitlari icin ayri goruntuleme izinleri

BAKIM_KAYITLARI_GORUNTULE ve KALIBRASYON_KAYITLARI_GORUNTULE: kayitlari yalnizca gorme yetkisi. Mevcut *_YONET izni kayit ekleme,
duzenleme ve silmeyi saglar. Hicbir rol yetki kaybetmesin diye, kendi rolunde *_YONET izni acik olan her role karsilik gelen
goruntuleme izni de acik olarak eklenir; digerlerinde kapali baslar (yonetici Rol-Izin ekranindan istedigi role verir).
Yeniden calistirilirsa var olan secimlere dokunmaz.

Revision ID: b8d3f5a1c492
Revises: a7c3e91d4b52
Create Date: 2026-11-22 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b8d3f5a1c492"
down_revision: Union[str, Sequence[str], None] = "a7c3e91d4b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama, gorunen_ad) VALUES
          ('BAKIM_KAYITLARI_GORUNTULE', 'Bakım kayıtlarını görüntüleme (düzenleme yetkisi vermez)', 'Bakım Kayıtları Görüntüle'),
          ('KALIBRASYON_KAYITLARI_GORUNTULE', 'Kalibrasyon kayıtlarını görüntüleme (düzenleme yetkisi vermez)', 'Kalibrasyon Kayıtları Görüntüle')
        ON CONFLICT (izin_adi) DO NOTHING;
    """)
    # Görüntüleme izni, aynı rolde karşılık gelen *_YONET açıksa açık başlar; böylece hiçbir rol mevcut erişimini kaybetmez.
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, yeni.izin_id,
               COALESCE((SELECT ri.izin_var FROM rol_izinleri ri JOIN izinler y ON y.izin_id = ri.izin_id
                         WHERE ri.rol_id = r.rol_id AND y.izin_adi = 'BAKIM_KAYITLARI_YONET'), 0)
        FROM roller r CROSS JOIN izinler yeni
        WHERE yeni.izin_adi = 'BAKIM_KAYITLARI_GORUNTULE'
        ON CONFLICT (rol_id, izin_id) DO NOTHING;
    """)
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, yeni.izin_id,
               COALESCE((SELECT ri.izin_var FROM rol_izinleri ri JOIN izinler y ON y.izin_id = ri.izin_id
                         WHERE ri.rol_id = r.rol_id AND y.izin_adi = 'KALIBRASYON_KAYITLARI_YONET'), 0)
        FROM roller r CROSS JOIN izinler yeni
        WHERE yeni.izin_adi = 'KALIBRASYON_KAYITLARI_GORUNTULE'
        ON CONFLICT (rol_id, izin_id) DO NOTHING;
    """)


def downgrade():
    op.execute("""
        DELETE FROM rol_izinleri WHERE izin_id IN (
            SELECT izin_id FROM izinler WHERE izin_adi IN ('BAKIM_KAYITLARI_GORUNTULE', 'KALIBRASYON_KAYITLARI_GORUNTULE'));
    """)
    op.execute("DELETE FROM izinler WHERE izin_adi IN ('BAKIM_KAYITLARI_GORUNTULE', 'KALIBRASYON_KAYITLARI_GORUNTULE');")
