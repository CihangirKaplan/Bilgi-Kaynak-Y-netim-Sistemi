"""proje_turleri: cihaz rezervasyonunda seçilebilen proje türleri listesi

Revision ID: c8f2a5d1e704
Revises: b6d2f8a4c913
Create Date: 2026-11-16 15:00:00.000000

Rezervasyon formunda "proje türü" elle yazılmak yerine bu tablodan seçilir; listede olmayan tür formdan eklenir.
`cihaz_rezervasyonlari.proje_turu` sütunu metin olarak kalır (eski kayıtlar ve raporlar değişmez). Mevcut rezervasyonlarda
geçen türler ve birkaç varsayılan tür başlangıç listesine konur. Ad büyük/küçük harf farkı gözetilmeden benzersizdir.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f2a5d1e704"
down_revision: Union[str, Sequence[str], None] = "b6d2f8a4c913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proje_turleri (
            proje_turu_id SERIAL PRIMARY KEY,
            ad VARCHAR(50) NOT NULL,
            aktif_mi BOOLEAN NOT NULL DEFAULT TRUE
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_proje_turleri_ad ON proje_turleri (lower(ad))")
    op.execute(
        """
        INSERT INTO proje_turleri (ad)
        SELECT ad FROM (
            VALUES ('Araştırma'), ('Test'), ('Bakım'), ('Eğitim'), ('Psikoterapi')
        ) AS varsayilan(ad)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO proje_turleri (ad)
        SELECT DISTINCT ON (lower(btrim(proje_turu))) btrim(proje_turu)
        FROM cihaz_rezervasyonlari
        WHERE proje_turu IS NOT NULL AND btrim(proje_turu) <> ''
        ORDER BY lower(btrim(proje_turu)), btrim(proje_turu)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS proje_turleri")
