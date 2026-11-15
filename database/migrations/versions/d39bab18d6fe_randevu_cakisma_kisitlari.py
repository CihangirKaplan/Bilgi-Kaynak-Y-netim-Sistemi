"""Randevu çakışma kısıtları."""

from alembic import op

revision = "d39bab18d6fe"
down_revision = "a98502dae8b4"
branch_labels = None
depends_on = None


def upgrade():
    # EXCLUDE kısıtları için gerekli PostgreSQL eklentisi
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")

    # Aynı psikoloğa çakışan randevu verilmesini engeller.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'psikolog_randevu_cakisma'
                  AND conrelid = 'randevular'::regclass
            ) THEN
                ALTER TABLE randevular
                ADD CONSTRAINT psikolog_randevu_cakisma
                EXCLUDE USING gist (
                    psikolog_id WITH =,
                    tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&
                )
                WHERE (durum = 'PLANLANDI');
            END IF;
        END $$;
    """)

    # Aynı odaya çakışan randevu verilmesini engeller.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'oda_randevu_cakisma'
                  AND conrelid = 'randevular'::regclass
            ) THEN
                ALTER TABLE randevular
                ADD CONSTRAINT oda_randevu_cakisma
                EXCLUDE USING gist (
                    oda_id WITH =,
                    tsrange(baslangic_zamani, bitis_zamani, '[)') WITH &&
                )
                WHERE (durum = 'PLANLANDI');
            END IF;
        END $$;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE randevular
        DROP CONSTRAINT IF EXISTS oda_randevu_cakisma;
    """)

    op.execute("""
        ALTER TABLE randevular
        DROP CONSTRAINT IF EXISTS psikolog_randevu_cakisma;
    """)