"""kullanilmayan cihaz durumlari (Rezerve, Kullanimda) ve ise yaramayan takip kontrol listesi izni temizligi

1. 'Rezerve' ve 'Kullanimda' cihaz durumlari hicbir yerde kendiliginden atanmiyordu; yalnizca elle secilebiliyor ve secilince cihaz
   rezervasyon icin gorunmez oluyordu. Bu iki durum artik secilemez; sunucu ve istemci bugunku rezervasyonlardan hesaplar.
   Bu durumdaki mevcut cihazlar 'Kullanima_Hazir' yapilir (enum degerleri geriye uyumluluk icin veritabaninda kalir).
2. CIHAZ_TAKIP_KONTROL_LISTESI izni: ilgili sayfa/dugme V1.0 kapsami disinda kaldigindan hicbir seyi acmiyordu; izin ve rol atamalari silinir.

Revision ID: c4e9a7d2b815
Revises: b8d3f5a1c492
Create Date: 2026-11-22 17:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4e9a7d2b815"
down_revision: Union[str, Sequence[str], None] = "b8d3f5a1c492"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("UPDATE cihazlar SET durum = 'Kullanima_Hazir' WHERE durum::text IN ('Rezerve', 'Kullanimda');")
    op.execute("DELETE FROM rol_izinleri WHERE izin_id IN (SELECT izin_id FROM izinler WHERE izin_adi = 'CIHAZ_TAKIP_KONTROL_LISTESI');")
    op.execute("DELETE FROM izinler WHERE izin_adi = 'CIHAZ_TAKIP_KONTROL_LISTESI';")


def downgrade():
    # Silinen izin eski haliyle geri eklenir (Admin, Memur ve Müdür'de açık); cihaz durumları geri alınamaz (hangi cihazın hangi durumda olduğu bilinmez).
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama, gorunen_ad)
        VALUES ('CIHAZ_TAKIP_KONTROL_LISTESI', 'Cihaz takip kontrol listesini yönetme', 'Cihaz Takip Kontrol Listesi')
        ON CONFLICT (izin_adi) DO NOTHING;
    """)
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT r.rol_id, i.izin_id, CASE WHEN UPPER(r.rol_adi) IN ('ADMIN', 'MEMUR', 'MUDUR') THEN 1 ELSE 0 END
        FROM roller r CROSS JOIN izinler i WHERE i.izin_adi = 'CIHAZ_TAKIP_KONTROL_LISTESI'
        ON CONFLICT (rol_id, izin_id) DO NOTHING;
    """)
