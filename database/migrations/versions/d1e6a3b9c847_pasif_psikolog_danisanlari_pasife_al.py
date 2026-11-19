"""su an pasif olan psikologlarin aktif danisanlari pasife alindi

Psikolog pasife alinirken kendi danisanlari da pasife aliniyor (ve psikolog yeniden aktif edilince geri aciliyor). Bu migration,
bu kuraldan ONCE pasife alinmis psikologlarin hala aktif gorunen danisanlarini ayni sekilde pasife alir ve "psikolog pasifligi
nedeniyle pasif" diye isaretler; boylece psikolog yeniden aktif edilince bunlar da otomatik geri acilir.

Etkilenen: kullanicisi pasif olan PSIKOLOG rolundeki personelin olusturdugu, aktif ve gelecekte planli randevusu olmayan danisan
kodlari. Randevular, danisan kodlari silinmez; yalnizca aktif_mi ve isaret sutunu degisir. Daha once elle pasife alinmis danisanlar
isaretlenmez.

Geri alma (downgrade) hicbir sey yapmaz: isaretli satirlarin bir kismi calisma zamaninda (psikolog pasife alinirken) isaretlenmis
olabilir; toplu geri acmak yanlis olur.

Revision ID: d1e6a3b9c847
Revises: c2e5a9d4b681
Create Date: 2026-11-18 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e6a3b9c847"
down_revision: Union[str, Sequence[str], None] = "c2e5a9d4b681"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        """
        UPDATE danisan_kodlari d
        SET aktif_mi = FALSE, psikolog_pasifligi_nedeniyle_pasif = TRUE
        FROM personel p
        JOIN kullanicilar k ON k.kullanici_id = p.kullanici_id
        JOIN roller r ON r.rol_id = k.rol_id
        WHERE d.olusturan_psikolog_id = p.personel_id
          AND d.aktif_mi = TRUE
          AND k.aktif_mi = FALSE AND UPPER(r.rol_adi) = 'PSIKOLOG'
          AND NOT EXISTS (
              SELECT 1 FROM randevular x
              WHERE x.danisan_kod_id = d.danisan_kod_id AND x.durum = 'PLANLANDI' AND x.bitis_zamani > NOW()
          )
        """
    )


def downgrade():
    # Isaretli satirlarin bir kismi calisma zamaninda isaretlenmis olabilir; toplu geri acma yapilmaz.
    pass
