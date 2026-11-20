"""oturum surumu (cikista token iptali) ve denetimde istemci adresi

1. kullanicilar.token_surumu: cikis yapilinca artar; jetonlar (token) olusturuldugu andaki surumu tasir, surum degisince gecersiz olur.
2. denetim_kayitlari.istemci_adresi: isteği yapan istemcinin adresi. Sunucu her baglantiya `tkys.istemci_adresi` oturum
   ayarini koyar; INSERT oncesi tetikleyici bu ayari sutuna yazar (denetim kaydi yazan her kod yolu otomatik kapsanir).
3. LOGOUT ve VIEW denetim olaylari.
(Kullanici adinin buyuk/kucuk harfsiz tekilligi veritabaninda zaten ux_kullanicilar_kullanici_adi_ci ile saglaniyor.)

Revision ID: f4b7c2e9a186
Revises: c3f8a1d6e725
Create Date: 2026-11-20 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f4b7c2e9a186"
down_revision: Union[str, Sequence[str], None] = "c3f8a1d6e725"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS token_surumu integer NOT NULL DEFAULT 0;")
    op.execute("ALTER TABLE denetim_kayitlari ADD COLUMN IF NOT EXISTS istemci_adresi varchar(45);")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION denetim_istemci_adresi_yaz() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.istemci_adresi IS NULL THEN
                NEW.istemci_adresi := NULLIF(current_setting('tkys.istemci_adresi', true), '');
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS denetim_istemci_adresi_tetikleyici ON denetim_kayitlari;")
    op.execute(
        "CREATE TRIGGER denetim_istemci_adresi_tetikleyici BEFORE INSERT ON denetim_kayitlari "
        "FOR EACH ROW EXECUTE FUNCTION denetim_istemci_adresi_yaz();"
    )
    # PostgreSQL ENUM'a deger eklemeyi transaction icinde reddeder; once aktif islem bitirilir.
    op.execute("COMMIT")
    op.execute("ALTER TYPE denetim_olay_turu ADD VALUE IF NOT EXISTS 'LOGOUT'")
    op.execute("ALTER TYPE denetim_olay_turu ADD VALUE IF NOT EXISTS 'VIEW'")


def downgrade():
    # ENUM degerleri (LOGOUT, VIEW) PostgreSQL'de tek tek silinemez; kalir. Diger her sey geri alinir.
    op.execute("DROP TRIGGER IF EXISTS denetim_istemci_adresi_tetikleyici ON denetim_kayitlari;")
    op.execute("DROP FUNCTION IF EXISTS denetim_istemci_adresi_yaz();")
    op.execute("ALTER TABLE denetim_kayitlari DROP COLUMN IF EXISTS istemci_adresi;")
    op.execute("ALTER TABLE kullanicilar DROP COLUMN IF EXISTS token_surumu;")
