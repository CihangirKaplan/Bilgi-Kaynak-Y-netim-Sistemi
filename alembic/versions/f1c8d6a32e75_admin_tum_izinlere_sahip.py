"""ADMIN rolünü tüm izinlerde açık yap (onarım)

Projede ADMIN, tüm izinlere sahip tam yetkili roldür (izin_duzenle ADMIN'den izin kaldırmayı yasaklar;
sıfırdan kurulan veritabanlarında ADMIN her izinde açıktır). Ancak rol adı 'ADMIN' yerine 'Admin' gibi
yazılmış eski kurulumlarda, adı büyük harfle arayan migrasyonlar (örn. KULLANICI_PAROLA_SIFIRLA) ADMIN'e izin
VEREMEDİ; izin tabloya girdi ama kimseye verilmedi. Rol adları #282'de düzeltildi, ancak o ana kadar yanlış
yazılmış izin satırları kendiliğinden düzelmez.

Bu migrasyon ADMIN'in kapalı ya da eksik izinlerini açar. Zaten doğru olan veritabanlarında (CI, sıfırdan
kurulanlar) hiçbir satırı değiştirmez. Diğer roller etkilenmez.

Revision ID: f1c8d6a32e75
Revises: d41c7e0a95b3
Create Date: 2026-11-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1c8d6a32e75"
down_revision: Union[str, Sequence[str], None] = "d41c7e0a95b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Yalnızca ADMIN için; yalnızca kapalı ya da eksik satırlar yazılır (doğru olanlara dokunulmaz).
ADMIN_ONARIM_SORGUSU = """
    INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
    SELECT r.rol_id, i.izin_id, 1
    FROM roller r
    CROSS JOIN izinler i
    WHERE UPPER(r.rol_adi) = 'ADMIN'
    ON CONFLICT (rol_id, izin_id)
    DO UPDATE SET izin_var = 1
    WHERE rol_izinleri.izin_var IS DISTINCT FROM 1
"""


def upgrade() -> None:
    op.execute(sa.text(ADMIN_ONARIM_SORGUSU))


def downgrade() -> None:
    # Bilerek geri alınmaz: ADMIN'den izin almak sistemden kilitlenme riski taşır.
    pass
