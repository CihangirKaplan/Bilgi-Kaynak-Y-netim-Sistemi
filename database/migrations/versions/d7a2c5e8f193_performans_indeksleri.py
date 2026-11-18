"""Tarih sütunları için performans indeksleri

Revision ID: d7a2c5e8f193
Revises: c2e5a9d4b681
Create Date: 2026-11-18 18:00:00.000000

Yabancı anahtar sütunlarının indeksleri a7d3e9c1b254 ile eklenmişti; tarih aralığı/sıralama sorgularının sütunları indekssizdi:
- denetim_kayitlari: tablo her giriş ve işlemle büyür; denetim ekranı "en yeni önce" sıralayıp sayfalar (ORDER BY
  olusturulma_tarihi DESC, denetim_id DESC) ve tarih aralığı süzer.
- randevular.baslangic_zamani: bugün ve sonrası / tarih aralığı sorguları (planlı randevu, doluluk, rapor).
- ogrenci_faaliyet_takip.faaliyet_tarihi: faaliyet listesi ve dönem raporları (BETWEEN, MAX).
Yalnızca sorgu hızlanır; veri ve davranış değişmez.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d7a2c5e8f193"
down_revision: Union[str, Sequence[str], None] = "c2e5a9d4b681"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_denetim_kayitlari_tarih "
        "ON denetim_kayitlari (olusturulma_tarihi DESC, denetim_id DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_randevular_baslangic_zamani ON randevular (baslangic_zamani)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_ogrenci_faaliyet_takip_faaliyet_tarihi "
        "ON ogrenci_faaliyet_takip (faaliyet_tarihi)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_ogrenci_faaliyet_takip_faaliyet_tarihi")
    op.execute("DROP INDEX IF EXISTS ix_randevular_baslangic_zamani")
    op.execute("DROP INDEX IF EXISTS ix_denetim_kayitlari_tarih")
