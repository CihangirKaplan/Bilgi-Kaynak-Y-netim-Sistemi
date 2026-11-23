"""faaliyet kayitlarindan kullanilmayan onay sutunu (onaylandi_mi) kaldirma

ogrenci_faaliyet_takip.onaylandi_mi hicbir yerde 'onayli' yapilmiyordu (uygulamada faaliyet kaydi icin bir onay adimi yoktur);
her kayit sonsuza kadar 'onay bekliyor' gorunuyordu. Sutun ve ona bagli raporlama alanlari kaldirildi.
Danisma masasi gorevlerinin onayi (danisma_masasi_oturumlari.onaylandi_mi) ayri bir sureclir ve degismez.

Revision ID: e6a1d4b8c273
Revises: c4e9a7d2b815
Create Date: 2026-11-23 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e6a1d4b8c273"
down_revision: Union[str, Sequence[str], None] = "c4e9a7d2b815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE ogrenci_faaliyet_takip DROP COLUMN IF EXISTS onaylandi_mi;")


def downgrade():
    # Sutun eski haliyle geri eklenir; tum kayitlar 'onaylanmamis' (FALSE) olur (eski degerler zaten hep FALSE'tu).
    op.execute("ALTER TABLE ogrenci_faaliyet_takip ADD COLUMN IF NOT EXISTS onaylandi_mi BOOLEAN NOT NULL DEFAULT FALSE;")
