"""Audit kayitlari veritabani duzeyinde degistirilemez ve silinemez (FR-045).

denetim_kayitlari tablosunda UPDATE, DELETE ve TRUNCATE tetikleyiciyle engellenir; INSERT etkilenmez.
Uygulama veritabanina yonetici kullanicisiyla baglandigi icin yetki kisitlamasi (REVOKE) yeterli olmaz;
tetikleyici bu kullaniciyi da kapsar. Yalnizca elle calisan gercek PostgreSQL testlerinin temizlik
yapabilmesi icin test veritabani (crkys_alembic_test) kilitten muaftir.

Revision ID: f3a9c2e47b18
Revises: d82c4a71f06b
"""

from alembic import op

revision = "f3a9c2e47b18"
down_revision = "d82c4a71f06b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE OR REPLACE FUNCTION denetim_kaydi_degistirilemez()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            -- Gercek veri tutmayan test veritabani muaftir (testler olusturduklari kayitlari siler).
            IF current_database() = 'crkys_alembic_test' THEN
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                ELSIF TG_OP = 'UPDATE' THEN
                    RETURN NEW;
                END IF;
                RETURN NULL;
            END IF;

            RAISE EXCEPTION
                'denetim_kayitlari tablosundaki kayitlar degistirilemez veya silinemez (%).', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER denetim_kayitlari_degistirilemez
        BEFORE UPDATE OR DELETE ON denetim_kayitlari
        FOR EACH ROW EXECUTE FUNCTION denetim_kaydi_degistirilemez();
    """)
    op.execute("""
        CREATE TRIGGER denetim_kayitlari_bosaltilamaz
        BEFORE TRUNCATE ON denetim_kayitlari
        FOR EACH STATEMENT EXECUTE FUNCTION denetim_kaydi_degistirilemez();
    """)


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS denetim_kayitlari_bosaltilamaz ON denetim_kayitlari;")
    op.execute("DROP TRIGGER IF EXISTS denetim_kayitlari_degistirilemez ON denetim_kayitlari;")
    op.execute("DROP FUNCTION IF EXISTS denetim_kaydi_degistirilemez();")
