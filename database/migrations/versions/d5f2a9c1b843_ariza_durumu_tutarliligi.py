"""cihaz 'Arizali' durumunu acik ariza kayitlariyla tutarli yap

Cihaz durumu iki yerden okunuyordu: Cihaz Envanteri kayitli durum sutununa, Cihaz Uygunlugu ise ariza kayitlarina bakiyordu. 'Arizali'
durumu elle secilebildigi ve bakimdaki cihaza ariza acilinca sutun degismedigi icin ikisi birbirini tutmayabiliyordu: arizasi olan cihaz
"hazir", arizasi olmayan cihaz "arizali" gorunebiliyordu. Artik etkin durum acik ariza kaydindan turetilir ve 'Arizali' elle secilemez.

Bu gecis mevcut tutarsiz kayitlari duzeltir ve her degisikligi denetim kaydina (DEVICE_STATUS_CHANGE) yazar:
1. Sutunu 'Arizali' olup acik arizasi OLMAYAN cihazlar 'Kullanima_Hazir' yapilir.
2. Sutunu 'Kullanima_Hazir' olup acik arizasi OLAN cihazlar 'Arizali' yapilir (bakimda/kalibrasyonda/kullanim disi cihazlara dokunulmaz).

Revision ID: d5f2a9c1b843
Revises: e6a1d4b8c273
Create Date: 2026-11-23 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d5f2a9c1b843"
down_revision: Union[str, Sequence[str], None] = "e6a1d4b8c273"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        WITH duzeltilen AS (
            UPDATE cihazlar c SET durum = 'Kullanima_Hazir'
            WHERE c.durum::text = 'Arizali'
              AND NOT EXISTS (SELECT 1 FROM cihaz_arizalari a WHERE a.cihaz_id = c.cihaz_id AND a.cozuldu_mu IS NOT TRUE)
            RETURNING c.cihaz_id
        )
        INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, ayrinti)
        SELECT NULL, 'DEVICE_STATUS_CHANGE', 'cihazlar', cihaz_id,
               jsonb_build_object('onceki', 'Arizali', 'yeni', 'Kullanima_Hazir', 'neden', 'Acik ariza kaydi yok (migration d5f2a9c1b843)')
        FROM duzeltilen;
    """)
    op.execute("""
        WITH duzeltilen AS (
            UPDATE cihazlar c SET durum = 'Arizali'
            WHERE c.durum::text = 'Kullanima_Hazir'
              AND EXISTS (SELECT 1 FROM cihaz_arizalari a WHERE a.cihaz_id = c.cihaz_id AND a.cozuldu_mu IS NOT TRUE)
            RETURNING c.cihaz_id
        )
        INSERT INTO denetim_kayitlari (kullanici_id, olay_turu, hedef_tablo, hedef_kayit_id, ayrinti)
        SELECT NULL, 'DEVICE_STATUS_CHANGE', 'cihazlar', cihaz_id,
               jsonb_build_object('onceki', 'Kullanima_Hazir', 'yeni', 'Arizali', 'neden', 'Acik ariza kaydi var (migration d5f2a9c1b843)')
        FROM duzeltilen;
    """)


def downgrade():
    # Veri onarimi geri alinamaz (hangi cihazin hangi durumda oldugu denetim kaydinda yazilidir); semada degisiklik yoktur.
    pass
