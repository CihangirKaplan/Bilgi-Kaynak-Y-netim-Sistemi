"""danisma masasi yonetimi izinleri

Revision ID: 8a9f73d2460d
Revises: 6b426e93cd9d
Create Date: 2026-10-22 11:42:31.229090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a9f73d2460d'
down_revision: Union[str, Sequence[str], None] = '6b426e93cd9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade() -> None:
    # Yönetim iznini oluştur.
    op.execute("""
        INSERT INTO izinler (izin_adi, aciklama)
        VALUES (
            'DANISMA_OTURUMU_YONETIM',
            'Danışma masası öğrenci oturumlarını görüntüleme, düzenleme ve onaylama'
        )
        ON CONFLICT (izin_adi)
        DO UPDATE SET aciklama = EXCLUDED.aciklama;
    """)

    # Yeni yönetim izni yalnızca memur ve admine verilir.
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE
                WHEN r.rol_adi IN ('MEMUR', 'ADMIN') THEN 1
                ELSE 0
            END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi = 'DANISMA_OTURUMU_YONETIM'
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)

    # Öğrenci oturum izni: öğrenci ve tam yetkili admin.
    # Memur ve müdürün eski erişimleri kaldırılır.
    op.execute("""
        INSERT INTO rol_izinleri (rol_id, izin_id, izin_var)
        SELECT
            r.rol_id,
            i.izin_id,
            CASE
                WHEN r.rol_adi IN ('DANISMA_OGRENCISI', 'ADMIN') THEN 1
                ELSE 0
            END
        FROM roller r
        CROSS JOIN izinler i
        WHERE i.izin_adi = 'DANISMA_OTURUMU_YONET'
        ON CONFLICT (rol_id, izin_id)
        DO UPDATE SET izin_var = EXCLUDED.izin_var;
    """)


def downgrade() -> None:
    # Yeni yönetim izninin rol eşleşmelerini sil.
    op.execute("""
        DELETE FROM rol_izinleri
        WHERE izin_id IN (
            SELECT izin_id FROM izinler
            WHERE izin_adi = 'DANISMA_OTURUMU_YONETIM'
        );
    """)

    op.execute("""
        DELETE FROM izinler
        WHERE izin_adi = 'DANISMA_OTURUMU_YONETIM';
    """)

    # Önceki başlangıç yetkilerini geri yükle.
    op.execute("""
        UPDATE rol_izinleri ri
        SET izin_var = CASE
            WHEN r.rol_adi IN (
                'MEMUR', 'MUDUR', 'DANISMA_OGRENCISI', 'ADMIN'
            ) THEN 1
            ELSE 0
        END
        FROM roller r, izinler i
        WHERE ri.rol_id = r.rol_id
          AND ri.izin_id = i.izin_id
          AND i.izin_adi = 'DANISMA_OTURUMU_YONET';
    """)
