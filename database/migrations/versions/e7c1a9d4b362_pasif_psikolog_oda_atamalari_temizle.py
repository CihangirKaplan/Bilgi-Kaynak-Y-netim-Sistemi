"""pasif psikologlarin oda atamalari temizlendi

Psikolog pasife alinirken artik oda atamalari kaldiriliyor ve aktiflestirirken odalar yeniden seciliyor. Bu migration,
bu degisiklikten ONCE pasife alinmis psikologlarin geride birakilan atama kayitlarini (psikolog_odalar) siler; boylece
aktiflestirilirken odalar yeniden secilir.

Yalnizca psikolog_odalar tablosundaki, kullanicisi pasif olan satirlar silinir. Randevular, danisan kodlari ve raporlar
etkilenmez (oda bilgisi randevunun kendisinde durur).

Geri alma (downgrade) silinen atamalari geri getiremez; hicbir sey yapmaz.

Revision ID: e7c1a9d4b362
Revises: e0f32bef6d16
Create Date: 2026-11-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7c1a9d4b362"
down_revision: Union[str, Sequence[str], None] = "e0f32bef6d16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
        DELETE FROM psikolog_odalar
        WHERE kullanici_id IN (SELECT kullanici_id FROM kullanicilar WHERE aktif_mi = FALSE)
        """
    )


def downgrade():
    # Silinen oda atamalari geri getirilemez; aktiflestirirken odalar yeniden secilir.
    pass
