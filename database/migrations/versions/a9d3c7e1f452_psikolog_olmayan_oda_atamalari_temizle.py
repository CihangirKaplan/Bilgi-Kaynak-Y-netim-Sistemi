"""psikolog olmayan kullanicilarin oda atamalari temizlendi

Psikolog baska bir role gecirilirken oda atamalari kaldirilir. Bu kuraldan once baska role gecmis (ya da elle degistirilmis)
kullanicilarin psikolog_odalar tablosunda kalan atama kayitlari, Oda Yonetimi'ndeki "Psikologlar" sutununda eski psikologun adini
gostermeye ve odanin cihaz rezervasyonuna kapali sayilmasina yol aciyordu.

Yalnizca psikolog_odalar tablosundaki, kullanicisinin rolu psikolog OLMAYAN satirlar silinir. Randevular, danisan kodlari,
kullanicilar ve raporlar etkilenmez (oda bilgisi randevunun kendisinde durur).

Geri alma (downgrade) silinen atamalari geri getiremez; hicbir sey yapmaz.

Revision ID: a9d3c7e1f452
Revises: c5a2e8f1d739
Create Date: 2026-11-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9d3c7e1f452"
down_revision: Union[str, Sequence[str], None] = "c5a2e8f1d739"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
        DELETE FROM psikolog_odalar
        WHERE kullanici_id IN (
            SELECT k.kullanici_id
            FROM kullanicilar k
            JOIN roller r ON r.rol_id = k.rol_id
            WHERE UPPER(r.rol_adi) <> 'PSIKOLOG'
        )
        """
    )


def downgrade():
    # Silinen oda atamalari geri getirilemez.
    pass
